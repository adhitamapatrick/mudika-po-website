"""
Database connection.

The app stores everything (pickup dates, menu items, images, orders, settings)
in a SQLite database:

  * On your computer it is a normal file: instance/mudika.sqlite3
  * On Cloudflare it is a D1 database (Cloudflare's hosted SQLite).

Both speak the same SQL, so the rest of the app only uses the four small
methods below (all / first / run / batch) and works the same in both places.
"""

import sqlite3
from pathlib import Path

from . import PROJECT_DIR, config

LOCAL_DATABASE_FILE = PROJECT_DIR / "instance" / "mudika.sqlite3"


### Tables ###
# Each statement is run once when the app starts ("IF NOT EXISTS" means it is
# safe to run again). To add a column later, add a new ALTER TABLE statement at
# the end of this list instead of editing the CREATE TABLE lines.

SCHEMA = [
    # Small key/value settings editable on the admin page (e-transfer email, contact info, ...)
    """
    CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    # One row per pickup date (YYYY-MM-DD)
    """
    CREATE TABLE IF NOT EXISTS pickup_dates (
        pickup_date      TEXT PRIMARY KEY,
        close_order_date TEXT NOT NULL,
        pickup_location  TEXT NOT NULL DEFAULT ''
    )
    """,
    # Menu items belong to one pickup date. Prices are stored in cents to avoid rounding issues.
    """
    CREATE TABLE IF NOT EXISTS menu_items (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        pickup_date TEXT NOT NULL REFERENCES pickup_dates(pickup_date) ON DELETE CASCADE,
        name        TEXT NOT NULL,
        vendor      TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        details     TEXT NOT NULL DEFAULT '',
        qty_min     INTEGER,
        qty_max     INTEGER,
        qty_ordered INTEGER NOT NULL DEFAULT 0,
        image_id    TEXT
    )
    """,
    # Uploaded menu pictures (stored in the database so they survive redeploys)
    """
    CREATE TABLE IF NOT EXISTS images (
        id           TEXT PRIMARY KEY,
        content_type TEXT NOT NULL,
        data_base64  TEXT NOT NULL
    )
    """,
    # One row per submitted order
    """
    CREATE TABLE IF NOT EXISTS orders (
        id              TEXT PRIMARY KEY,
        reference       TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        pickup_date     TEXT NOT NULL,
        customer_name   TEXT NOT NULL,
        customer_phone  TEXT NOT NULL,
        payment_method  TEXT NOT NULL,
        additional_info TEXT NOT NULL DEFAULT '',
        total_cents     INTEGER NOT NULL,
        sheet_synced    INTEGER NOT NULL DEFAULT 0
    )
    """,
    # The items inside each order (name and price are copied so old orders stay correct)
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id         TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        menu_item_id     INTEGER,
        item_name        TEXT NOT NULL,
        unit_price_cents INTEGER NOT NULL,
        quantity         INTEGER NOT NULL,
        line_total_cents INTEGER NOT NULL
    )
    """,
    # Safety net: if two people order the last item at the same moment, the
    # second order is rejected instead of selling more than the maximum.
    """
    CREATE TRIGGER IF NOT EXISTS menu_items_stock_guard
    BEFORE UPDATE OF qty_ordered ON menu_items
    WHEN NEW.qty_max IS NOT NULL AND NEW.qty_ordered > NEW.qty_max
    BEGIN
        SELECT RAISE(ABORT, 'SOLD_OUT');
    END
    """,
]


### Local database (your computer) ###


class LocalDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def all(self, sql, *params):
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def first(self, sql, *params):
        rows = self.all(sql, *params)
        return rows[0] if rows else None

    def run(self, sql, *params):
        """Run one INSERT/UPDATE/DELETE. Returns the new row id for inserts."""
        connection = self._connect()
        try:
            with connection:
                return connection.execute(sql, params).lastrowid
        finally:
            connection.close()

    def batch(self, statements):
        """Run several statements together: either all of them succeed, or none do."""
        connection = self._connect()
        try:
            with connection:
                for sql, params in statements:
                    connection.execute(sql, params)
        finally:
            connection.close()


### Cloudflare D1 database ###


class CloudflareDatabase:
    def __init__(self, binding):
        self.binding = binding

    @staticmethod
    def _wait(awaitable):
        # Flask is synchronous, but D1 calls are asynchronous. run_sync waits for them.
        from pyodide.ffi import run_sync

        return run_sync(awaitable)

    def _statement(self, sql, params):
        statement = self.binding.prepare(sql)
        return statement.bind(*params) if params else statement

    def all(self, sql, *params):
        result = self._wait(self._statement(sql, params).all())
        return [dict(row) for row in result.results]

    def first(self, sql, *params):
        row = self._wait(self._statement(sql, params).first())
        return dict(row) if row is not None else None

    def run(self, sql, *params):
        result = self._wait(self._statement(sql, params).run())
        return result.meta.last_row_id

    def batch(self, statements):
        prepared = [self._statement(sql, params) for sql, params in statements]
        self._wait(self.binding.batch(prepared))


### Picking the right database ###

_local_database = None
_schema_ready = False


def get_db():
    """Return the database for this request (D1 on Cloudflare, SQLite file locally)."""
    global _local_database, _schema_ready

    env = config.worker_env()
    if env is not None:
        db = CloudflareDatabase(env.DB)
    else:
        if _local_database is None:
            _local_database = LocalDatabase(LOCAL_DATABASE_FILE)
        db = _local_database

    if not _schema_ready:
        db.batch([(statement, ()) for statement in SCHEMA])
        _schema_ready = True
    return db


def is_sold_out_error(error):
    """True if the database refused an order because an item ran out (see the trigger above)."""
    return "SOLD_OUT" in str(error)
