"""
Seeds db/bank.db with small, deterministic synthetic data:
- 8 users, 1-2 accounts each, 1 card per checking/credit account
- ~30 transactions per account, with a handful flagged as fraud patterns
  (reusing the same "5 fraud pattern" idea from the Transaction Fraud Detector
  project: large odd-hour purchase, rapid repeat charges, foreign merchant,
  round-number structuring, sudden balance drain)

Run: python db/seed_synthetic_data.py
"""

import argparse
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as a standalone script from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))


random.seed(42)

DB_PATH = Path(__file__).parent / "bank.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

FIRST_NAMES = ["Aarav", "Vishnu", "Priya", "Kabir", "Ananya", "Rohan", "Meera", "Dev"]
LAST_NAMES = ["Sharma", "Reddy", "Iyer", "Nair", "Gupta", "Rao", "Menon", "Kumar"]
MERCHANTS = [
    "Amazon",
    "Swiggy",
    "Zomato",
    "BigBasket",
    "Uber",
    "IRCTC",
    "Flipkart",
    "Netflix",
]
FOREIGN_MERCHANTS = ["AliExpress-CN", "Steam-LU", "UnknownVendor-RU"]


def hash_pin(pin: str) -> str:
    """Hash a PIN using the same algorithm as tools/account_tools.py.

    Importing at call-time (rather than module import time) avoids a circular
    import during the very first ``ensure_database`` call that happens before
    sys.path has been fully configured in some test environments.
    """
    from tools.account_tools import hash_pin as _hash_pin

    return _hash_pin(pin)


def build_schema(conn):
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())


def seed_users(conn, n=8):
    users = []
    for i in range(1, n + 1):
        uid = f"U100{i}"
        first = FIRST_NAMES[i - 1]
        last = LAST_NAMES[i - 1]
        email = f"{first.lower()}.{last.lower()}@example.com"
        pin = f"{1000 + i * 111}"  # deterministic demo PIN, e.g. 1111, 1222...
        created = (
            datetime.now(timezone.utc) - timedelta(days=random.randint(200, 1200))
        ).isoformat()
        users.append((uid, first, last, email, hash_pin(pin), created))
        print(f"  {uid}: {first} {last} — demo PIN {pin}")
    conn.executemany(
        "INSERT INTO users (user_id, first_name, last_name, email, pin_hash, created_at) "
        "VALUES (?,?,?,?,?,?)",
        users
    )
    return [u[0] for u in users]


def seed_accounts_and_cards(conn, user_ids):
    accounts = []
    cards = []
    acc_counter = 2001
    from utils.money import to_paise

    card_counter = 3001
    for uid in user_ids:
        types = random.sample(
            ["checking", "savings", "credit"], k=random.choice([2, 3])
        )
        for t in types:
            aid = f"A{acc_counter}"
            acc_counter += 1
            if t == "checking":
                balance_paise = to_paise(random.uniform(5000, 80000))
            elif t == "savings":
                balance_paise = to_paise(random.uniform(20000, 500000))
            else:  # credit — balance represents amount owed, positive = owed
                balance_paise = to_paise(random.uniform(0, 60000))
            accounts.append((aid, uid, t, balance_paise, "INR", 1))

            if t in ("checking", "credit"):
                cid = f"C{card_counter}"
                card_counter += 1
                last4 = f"{random.randint(1000,9999)}"
                cards.append((cid, aid, last4, "active"))

    conn.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?)", accounts)
    conn.executemany("INSERT INTO cards VALUES (?,?,?,?)", cards)
    return [a[0] for a in accounts]


def seed_transactions(conn, account_ids, per_account=(15, 30)):
    from utils.money import to_paise

    txns = []
    txn_counter = 900001
    now = datetime.now(timezone.utc)

    for aid in account_ids:
        n = random.randint(*per_account)
        for _ in range(n):
            days_ago = random.randint(0, 180)
            ts = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            txn_type = random.choice(
                ["deposit", "withdrawal", "purchase", "transfer", "fee", "interest"]
            )
            merchant = random.choice(MERCHANTS) if txn_type == "purchase" else None
            flagged = 0

            if txn_type == "deposit":
                amount_paise = to_paise(random.uniform(500, 20000))
            elif txn_type in ("withdrawal", "purchase"):
                amount_paise = -to_paise(random.uniform(50, 5000))
            elif txn_type == "transfer":
                amount_paise = to_paise(random.uniform(-10000, 10000))
            elif txn_type == "fee":
                amount_paise = -to_paise(random.uniform(10, 200))
            else:  # interest
                amount_paise = to_paise(random.uniform(1, 50))

            # Inject occasional fraud-pattern transactions (~4% of rows)
            if random.random() < 0.04:
                pattern = random.choice(
                    ["odd_hour_large", "foreign_merchant", "structuring"]
                )
                if pattern == "odd_hour_large":
                    ts = ts.replace(hour=random.choice([1, 2, 3, 4]))
                    amount_paise = -to_paise(random.uniform(20000, 90000))
                    txn_type, merchant = "purchase", random.choice(MERCHANTS)
                elif pattern == "foreign_merchant":
                    txn_type, merchant = "purchase", random.choice(FOREIGN_MERCHANTS)
                    amount_paise = -to_paise(random.uniform(5000, 40000))
                else:  # structuring: suspiciously round numbers just under typical thresholds
                    txn_type, merchant = "withdrawal", None
                    amount_paise = -to_paise(random.choice([9999, 9500, 9900]))
                flagged = 1

            txns.append(
                (
                    f"T{txn_counter}",
                    aid,
                    txn_type,
                    amount_paise,
                    merchant,
                    ts.isoformat(),
                    flagged,
                )
            )
            txn_counter += 1

    conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?)", txns)
    return len(txns)


def main():
    parser = argparse.ArgumentParser(description="Seed the demo banking database.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and recreate db/bank.db before seeding. Never use with production data.",
    )
    args = parser.parse_args()

    if DB_PATH.exists() and not args.force:
        print(f"Database already exists at {DB_PATH}; preserving existing data.")
        print("Use --force to delete and recreate the demo database.")
        return

    if DB_PATH.exists() and args.force:
        DB_PATH.unlink()
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    build_schema(conn)

    print("Seeding users...")
    user_ids = seed_users(conn)

    print("Seeding accounts + cards...")
    account_ids = seed_accounts_and_cards(conn, user_ids)

    print("Seeding transactions...")
    n_txns = seed_transactions(conn, account_ids)

    conn.commit()
    conn.close()

    print(
        f"\nDone. {len(user_ids)} users, {len(account_ids)} accounts, "
        f"{n_txns} transactions -> {DB_PATH}"
    )


if __name__ == "__main__":
    main()
