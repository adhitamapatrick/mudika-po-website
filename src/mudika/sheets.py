"""
Copying orders to the Google Sheet.

The database is the real record of every order. After an order is saved, a copy
is sent to a small Google Apps Script attached to the spreadsheet (see
google-apps-script/Code.gs), which adds the rows. If the sheet can't be reached,
the order is still safe in the database, and an admin can press
"Copy missing orders to Google Sheet" on the admin page later.

Needs two settings: SHEETS_WEBHOOK_URL and SHEETS_WEBHOOK_SECRET.
"""

import json
import logging

from . import config, models
from .helpers import parse_date

log = logging.getLogger(__name__)

# Column order in the sheet. A-G match the original layout (D and E left blank).
SHEET_COLUMNS = [
    "Customer name",       # A
    "Menu item",           # B
    "Quantity",            # C
    "",                    # D
    "",                    # E
    "Order method",        # F  e.g. "Web form - 11 22"
    "Line total ($)",      # G
    "Phone",               # H
    "Payment",             # I
    "Additional info",     # J
    "Pickup date",         # K
    "Order reference",     # L
]


def sheets_configured():
    return bool(config.get_setting("SHEETS_WEBHOOK_URL") and config.get_setting("SHEETS_WEBHOOK_SECRET"))


def order_to_rows(order):
    """One sheet row per item in the order."""
    submitted = parse_date(order["created_at"][:10])
    order_method = f"Web form - {submitted.strftime('%m %d')}" if submitted else "Web form"
    payment = "E-transfer" if order["payment_method"] == "etransfer" else "Cash"
    return [
        [
            order["customer_name"],
            item["item_name"],
            item["quantity"],
            "",
            "",
            order_method,
            item["line_total_cents"] / 100,
            order["customer_phone"],
            payment,
            order["additional_info"],
            order["pickup_date"],
            order["reference"],
        ]
        for item in order["items"]
    ]


def _post_json(url, payload):
    """Send JSON and return the decoded JSON reply. Uses `requests` if installed (needed on Cloudflare)."""
    body = json.dumps(payload)
    try:
        import requests
    except ImportError:
        requests = None

    if requests is not None:
        response = requests.post(url, data=body, headers={"Content-Type": "application/json"}, timeout=15)
        response.raise_for_status()
        return response.json()

    from urllib.request import Request, urlopen

    request = Request(url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def copy_orders_to_sheet(orders):
    """
    Send orders to the Google Sheet and mark them as copied.
    Returns how many orders were copied. Never raises: problems are logged.
    """
    if not orders or not sheets_configured():
        return 0

    rows = [row for order in orders for row in order_to_rows(order)]
    try:
        reply = _post_json(
            config.get_setting("SHEETS_WEBHOOK_URL"),
            {"secret": config.get_setting("SHEETS_WEBHOOK_SECRET"), "rows": rows},
        )
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "unknown error"))
    except Exception:
        log.exception("Could not copy orders to the Google Sheet")
        return 0

    for order in orders:
        models.mark_order_synced(order["id"])
    return len(orders)
