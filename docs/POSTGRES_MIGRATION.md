# PostgreSQL Migration Guide

This architectural document outlines the strategy, schema mappings, database changes, and data migration paths required to transition the Autonomous Bank Assistant from SQLite to a production-grade PostgreSQL database.

---

## 1. Dialect & Type Schema Mapping

PostgreSQL enforces strict types and schema definitions compared to SQLite. The table below outlines how SQLite datatypes map to PostgreSQL equivalents:

| SQLite Datatype | PostgreSQL Datatype | Description |
| :--- | :--- | :--- |
| `TEXT` | `VARCHAR(N)` or `TEXT` | Map strings, user IDs, emails. |
| `INTEGER` | `BIGINT` or `INTEGER` | Map ID fields, timestamps, failed counters, and financial amounts stored in minor units (`balance_paise`, `amount_paise`). |
| `REAL` | *(deprecated)* | Legacy floating-point storage replaced with `INTEGER`/`BIGINT` minor units. |
| `DATETIME` | `TIMESTAMP WITH TIME ZONE` | Map transaction timestamps and lock periods. |

---

## 2. DDL Schema Translation (SQLite to PostgreSQL)

Below is the translated DDL translation template for the `users` table:

### SQLite (Current)
```sql
CREATE TABLE users (
    user_id       TEXT PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    pin_hash      TEXT NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT DEFAULT NULL,
    created_at    TEXT NOT NULL
);
```

### PostgreSQL (Target)
```sql
CREATE TABLE users (
    user_id       VARCHAR(50) PRIMARY KEY,
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    pin_hash      VARCHAR(255) NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until  TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Code Modifications (Connection Layer)

Currently, `db/connection.py` uses python's standard `sqlite3` library. To support PostgreSQL:

1. **Install PostgreSQL Client**:
   Add `psycopg2-binary` or `asyncpg` to `requirements.txt`.
2. **Refactor `db/connection.py`**:
   Replace `get_connection` SQLite connection factory with a PostgreSQL connection pool:
   ```python
   import psycopg2
   from psycopg2.pool import SimpleConnectionPool

   _pool = None

   def get_connection():
       global _pool
       if _pool is None:
           _pool = SimpleConnectionPool(
               minconn=1,
               maxconn=20,
               dsn=os.environ.get("DATABASE_URL")
           )
       return _pool.getconn()
   ```

---

## 4. Migration Execution Strategy

To migrate live data from `bank.db` to a target PostgreSQL database:

### Tool Option: pgloader
`pgloader` is the recommended open-source migration tool for moving schemas and data from SQLite to PostgreSQL:
```bash
pgloader db/bank.db postgresql:///bank_db
```

### Script Option: Custom Python ETL
Alternatively, write a Python migration script `db/migrate_to_postgres.py` using sqlite3 and psycopg2 to read all records in batches and execute `INSERT INTO ... ON CONFLICT DO NOTHING` statements on PostgreSQL.
