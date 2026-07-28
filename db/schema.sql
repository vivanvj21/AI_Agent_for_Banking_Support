-- Autonomous Bank Assistant — SQLite schema
-- Deliberately small and normalized enough to demo real query logic.

DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS cards;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id       TEXT PRIMARY KEY,      -- e.g. 'U1001'
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    pin_hash      TEXT NOT NULL,         -- sha256 of a 4-digit demo PIN, never store plaintext
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT DEFAULT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE accounts (
    account_id    TEXT PRIMARY KEY,      -- e.g. 'A2001'
    user_id       TEXT NOT NULL,
    account_type  TEXT NOT NULL CHECK (account_type IN ('checking','savings','credit')),
    balance_paise INTEGER NOT NULL,      -- stored in integer minor units (paise / cents)
    currency      TEXT NOT NULL DEFAULT 'INR',
    is_active     INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE cards (
    card_id       TEXT PRIMARY KEY,      -- e.g. 'C3001'
    account_id    TEXT NOT NULL,
    last4         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','locked','reported_lost')),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,     -- e.g. 'T900001'
    account_id     TEXT NOT NULL,
    txn_type       TEXT NOT NULL CHECK (txn_type IN ('deposit','withdrawal','purchase','transfer','fee','interest')),
    amount_paise   INTEGER NOT NULL,     -- stored in integer minor units (negative = money out, positive = money in)
    merchant       TEXT,
    timestamp      TEXT NOT NULL,
    flagged_fraud  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

CREATE INDEX idx_accounts_user_id ON accounts(user_id);
CREATE INDEX idx_cards_account_id ON cards(account_id);
CREATE INDEX idx_transactions_account_id ON transactions(account_id);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);

-- ─────────────────────────────────────────────────────────────
-- Memory: conversation sessions + messages.
--
-- One row per session (a CLI run, or a Streamlit browser session).
-- user_id starts NULL and is filled in once verify_gate succeeds,
-- which is what lets a later session look up "your previous chats"
-- for a given user rather than just the current process's memory.
-- ─────────────────────────────────────────────────────────────

CREATE TABLE sessions (
    session_id      TEXT PRIMARY KEY,     -- uuid4 hex
    user_id         TEXT,                 -- NULL until verified; FK to users
    channel         TEXT NOT NULL DEFAULT 'cli',  -- 'cli' | 'streamlit'
    created_at      TEXT NOT NULL,
    last_active_at  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    turn          INTEGER NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content       TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_messages_session_id ON messages(session_id);
