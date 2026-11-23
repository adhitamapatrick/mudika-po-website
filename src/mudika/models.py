"""
All reading and writing of data lives here, so the page code (routes_*.py)
never has to write SQL itself.
"""

import base64
import secrets

from .database import get_db
from .helpers import cents_to_dollars, now_in_toronto

### Settings (editable on the admin "Settings" section) ###

DEFAULT_SETTINGS = {
    "active_pickup_date": "",
    "etransfer_email": "",
    "contact_info": "",
}


def get_settings():
    settings = dict(DEFAULT_SETTINGS)
    for row in get_db().all("SELECT key, value FROM settings"):
        settings[row["key"]] = row["value"]
    return settings


def save_setting(key, value):
    get_db().run(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        key,
        value,
    )


### Pickup dates ###


def list_pickup_dates():
    return get_db().all("SELECT * FROM pickup_dates ORDER BY pickup_date DESC")


def get_pickup_date(pickup_date):
    return get_db().first("SELECT * FROM pickup_dates WHERE pickup_date = ?", pickup_date)


def create_pickup_date(pickup_date):
    get_db().run(
        "INSERT OR IGNORE INTO pickup_dates (pickup_date, close_order_date) VALUES (?, ?)",
        pickup_date,
        pickup_date,
    )


def update_pickup_schedule(pickup_date, close_order_date, pickup_location):
    get_db().run(
        "UPDATE pickup_dates SET close_order_date = ?, pickup_location = ? WHERE pickup_date = ?",
        close_order_date,
        pickup_location,
        pickup_date,
    )


def delete_pickup_date(pickup_date):
    """Delete a pickup date, its menu items and their pictures. Past orders are kept."""
    get_db().batch([
        ("DELETE FROM images WHERE id IN (SELECT image_id FROM menu_items WHERE pickup_date = ?)", (pickup_date,)),
        ("DELETE FROM menu_items WHERE pickup_date = ?", (pickup_date,)),
        ("DELETE FROM pickup_dates WHERE pickup_date = ?", (pickup_date,)),
    ])


### Menu items ###


def _with_display_fields(item):
    """Add values the templates need (price as '10.50', how many are left, picture link)."""
    item["price"] = cents_to_dollars(item["price_cents"])
    item["qty_remaining"] = (
        max(0, item["qty_max"] - item["qty_ordered"]) if item["qty_max"] is not None else None
    )
    item["image_url"] = f"/images/{item['image_id']}" if item["image_id"] else ""
    return item


def list_menu_items(pickup_date):
    rows = get_db().all("SELECT * FROM menu_items WHERE pickup_date = ? ORDER BY id", pickup_date)
    return [_with_display_fields(row) for row in rows]


def get_menu_item(item_id, pickup_date):
    row = get_db().first(
        "SELECT * FROM menu_items WHERE id = ? AND pickup_date = ?", item_id, pickup_date
    )
    return _with_display_fields(row) if row else None


def add_menu_item(pickup_date, fields):
    get_db().run(
        "INSERT INTO menu_items (pickup_date, name, vendor, price_cents, details, qty_min, qty_max, image_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        pickup_date,
        fields["name"],
        fields["vendor"],
        fields["price_cents"],
        fields["details"],
        fields["qty_min"],
        fields["qty_max"],
        fields["image_id"],
    )


def update_menu_item(item_id, fields, old_image_id=None):
    statements = [(
        "UPDATE menu_items SET name = ?, vendor = ?, price_cents = ?, details = ?, "
        "qty_min = ?, qty_max = ?, qty_ordered = ?, image_id = ? WHERE id = ?",
        (
            fields["name"],
            fields["vendor"],
            fields["price_cents"],
            fields["details"],
            fields["qty_min"],
            fields["qty_max"],
            fields["qty_ordered"],
            fields["image_id"],
            item_id,
        ),
    )]
    if old_image_id and old_image_id != fields["image_id"]:
        statements.append(("DELETE FROM images WHERE id = ?", (old_image_id,)))
    get_db().batch(statements)


def delete_menu_item(item):
    statements = [("DELETE FROM menu_items WHERE id = ?", (item["id"],))]
    if item["image_id"]:
        statements.append(("DELETE FROM images WHERE id = ?", (item["image_id"],)))
    get_db().batch(statements)


### Menu pictures ###


def save_image(content_type, data):
    image_id = secrets.token_hex(12)
    get_db().run(
        "INSERT INTO images (id, content_type, data_base64) VALUES (?, ?, ?)",
        image_id,
        content_type,
        base64.b64encode(data).decode("ascii"),
    )
    return image_id


def get_image(image_id):
    row = get_db().first("SELECT content_type, data_base64 FROM images WHERE id = ?", image_id)
    if not row:
        return None
    return row["content_type"], base64.b64decode(row["data_base64"])


### Orders ###


def create_order(pickup_date, customer, items):
    """
    Save an order and add its quantities to each menu item's "ordered" count.

    `items` is a list of (menu_item, quantity). Everything is saved in one batch,
    so if an item sold out a moment ago, nothing is saved and the database raises
    a SOLD_OUT error (see database.is_sold_out_error).
    """
    order_id = secrets.token_urlsafe(16)
    reference = secrets.token_hex(3).upper()  # short code customers can quote, e.g. "7F3A1C"
    total_cents = sum(item["price_cents"] * quantity for item, quantity in items)

    statements = [(
        "INSERT INTO orders (id, reference, created_at, pickup_date, customer_name, customer_phone, "
        "payment_method, additional_info, total_cents) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            order_id,
            reference,
            now_in_toronto().isoformat(timespec="seconds"),
            pickup_date,
            customer["name"],
            customer["phone"],
            customer["payment_method"],
            customer["additional_info"],
            total_cents,
        ),
    )]
    for item, quantity in items:
        statements.append((
            "INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price_cents, quantity, line_total_cents) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, item["id"], item["name"], item["price_cents"], quantity, item["price_cents"] * quantity),
        ))
        statements.append((
            "UPDATE menu_items SET qty_ordered = qty_ordered + ? WHERE id = ?",
            (quantity, item["id"]),
        ))

    get_db().batch(statements)
    return order_id


def get_order(order_id):
    """Return an order with its items, or None."""
    db = get_db()
    order = db.first("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        return None
    order["items"] = db.all("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", order_id)
    for item in order["items"]:
        item["line_total"] = cents_to_dollars(item["line_total_cents"])
    order["total"] = cents_to_dollars(order["total_cents"])
    return order


def list_unsynced_orders():
    """Orders that haven't been copied to the Google Sheet yet (oldest first)."""
    rows = get_db().all("SELECT id FROM orders WHERE sheet_synced = 0 ORDER BY created_at")
    return [get_order(row["id"]) for row in rows]


def count_unsynced_orders():
    return get_db().first("SELECT COUNT(*) AS count FROM orders WHERE sheet_synced = 0")["count"]


def mark_order_synced(order_id):
    get_db().run("UPDATE orders SET sheet_synced = 1 WHERE id = ?", order_id)
