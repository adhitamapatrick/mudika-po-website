import json
import math
import os
import re
import secrets
import threading
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "instance"
DATA_FILE = DATA_DIR / "menu.json"
UPLOAD_DIR = PROJECT_DIR / "static" / "uploads"
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
SPREADSHEET_ID = "1BBk_33lKRMkxpFKyY3-lx-mpGxGWiPG7kBVqNNoNnoA"
DATA_LOCK = threading.Lock()

DEFAULT_SITE_DATA = {
    "pickup_date": date.today().isoformat(),
    "menu": [
        {'Menu Name': 'Nasi Goreng', 'Price': 10.50, 'Vendor Name': 'Indonesian Kitchen', 'Picture URL': 'https://example.com/nasi-goreng.jpg'},
        {'Menu Name': 'Mie Ayam', 'Price': 9, 'Vendor Name': 'Noodle House', 'Picture URL': 'https://example.com/mie-ayam.jpg'},
        {'Menu Name': 'Sate Ayam', 'Price': 12, 'Vendor Name': 'Satay Corner', 'Picture URL': 'https://example.com/sate-ayam.jpg'},
        {'Menu Name': 'Pastel Goreng', 'Price': '10 per pack', 'Vendor Name': 'Bistro Komodo', 'Picture URL': 'https://example.com/pastel.jpg'}
    ],
}


def load_site_data():
    if not DATA_FILE.exists():
        pickup_date = DEFAULT_SITE_DATA["pickup_date"]
        return {
            "active_pickup_date": pickup_date,
            "pickup_dates": {pickup_date: {"menu": list(DEFAULT_SITE_DATA["menu"])}},
        }

    with DATA_FILE.open(encoding="utf-8") as data_file:
        site_data = json.load(data_file)

    if "pickup_dates" in site_data:
        return site_data

    pickup_date = site_data.get("pickup_date", DEFAULT_SITE_DATA["pickup_date"])
    return {
        "active_pickup_date": pickup_date,
        "pickup_dates": {pickup_date: {"menu": site_data.get("menu", [])}},
    }


def save_site_data(site_data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as data_file:
        json.dump(site_data, data_file, indent=2)


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def item_unit_price(value):
    price_text = str(value).strip()
    try:
        return Decimal(price_text)
    except InvalidOperation:
        match = re.search(r"-?\d+(?:\.\d+)?", price_text)
        if not match:
            raise ValueError("Menu item has an invalid price.")
        return Decimal(match.group())


def append_order_rows_to_sheet(rows):
    credentials_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_file:
        raise RuntimeError("Google Sheets credentials are not configured.")

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(
        credentials_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    worksheet = os.environ.get("GOOGLE_SHEETS_WORKSHEET")
    if not worksheet:
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID,
            fields="sheets.properties.title",
        ).execute()
        worksheet = spreadsheet["sheets"][0]["properties"]["title"]

    escaped_worksheet = worksheet.replace("'", "''")
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{escaped_worksheet}'!A:G",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


def parse_menu_item(form, image, existing=None):
    menu_name = form.get("menu_name", "").strip()
    vendor_name = form.get("vendor_name", "").strip()
    details = form.get("details", "").strip()

    if not menu_name or not vendor_name:
        raise ValueError("Menu name and vendor are required.")

    try:
        price = float(form.get("price", ""))
        min_value = form.get("qty_min", "").strip()
        qty_min = int(min_value) if min_value else None
        qty_ordered = int(form.get("qty_ordered", existing.get("Qty Ordered", 0) if existing else 0))
        max_value = form.get("qty_max", "").strip()
        qty_max = int(max_value) if max_value else None
        if not math.isfinite(price) or price < 0 or qty_ordered < 0:
            raise ValueError
        if qty_min is not None and qty_min < 0:
            raise ValueError
        if qty_max is not None and qty_max < 0:
            raise ValueError
        if qty_max is not None and ((qty_min is not None and qty_max < qty_min) or qty_ordered > qty_max):
            raise ValueError
    except ValueError as error:
        raise ValueError("Enter a valid price and quantity range. Maximum must cover the ordered quantity.") from error

    image_url = existing.get("Picture URL", "") if existing else ""
    if image and image.filename:
        if not allowed_image(image.filename):
            raise ValueError("Upload a JPG, PNG, or WebP image.")
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        extension = image.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid4().hex}.{extension}"
        image.save(UPLOAD_DIR / secure_filename(filename))
        image_url = url_for("static", filename=f"uploads/{filename}")

    return {
        "Menu Name": menu_name,
        "Price": price,
        "Vendor Name": vendor_name,
        "Qty Min": qty_min,
        "Qty Max": qty_max,
        "Qty Ordered": qty_ordered,
        "Picture URL": image_url,
        "Details": details,
    }


@app.route("/")
def home():
    site_data = load_site_data()
    pickup_date_key = site_data["active_pickup_date"]
    pickup_date = date.fromisoformat(pickup_date_key)
    menu = []
    for item in site_data["pickup_dates"][pickup_date_key]["menu"]:
        menu_item = dict(item)
        ordered = int(menu_item.get("Qty Ordered", 0))
        maximum = menu_item.get("Qty Max")
        menu_item["Qty Remaining"] = max(0, int(maximum) - ordered) if maximum is not None else None
        menu.append(menu_item)

    return render_template(
        "home.html",
        menu=menu,
        pickup_date=pickup_date.strftime("%A, %b %d, %Y").replace(" 0", " "),
    )


@app.route("/order", methods=["POST"])
def submit_order():
    customer_name = request.form.get("customer_name", "").strip()
    customer_email = request.form.get("customer_email", "").strip()
    if not customer_name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", customer_email):
        flash("Enter your name and a valid email address to submit your order.", "error")
        return redirect(url_for("home"))

    with DATA_LOCK:
        site_data = load_site_data()
        pickup_date = site_data["active_pickup_date"]
        menu = site_data["pickup_dates"][pickup_date]["menu"]
        requested_quantities = []
        total_quantity = 0

        try:
            for index, item in enumerate(menu):
                quantity = int(request.form.get(f"quantity_{index}", "0"))
                ordered = int(item.get("Qty Ordered", 0))
                maximum = item.get("Qty Max")
                remaining = max(0, int(maximum) - ordered) if maximum is not None else None
                if quantity < 0 or (remaining is not None and quantity > remaining):
                    raise ValueError
                requested_quantities.append(quantity)
                total_quantity += quantity
        except ValueError:
            flash("The order exceeds the remaining quantity. Please review the menu and try again.", "error")
            return redirect(url_for("home"))

        if total_quantity == 0:
            flash("Choose at least one item before submitting your order.", "error")
            return redirect(url_for("home"))

        submitted_date = date.today()
        order_method = f"Web form - {submitted_date.strftime('%m %d')}"
        order_rows = []
        try:
            for item, quantity in zip(menu, requested_quantities):
                if quantity == 0:
                    continue
                line_total = (item_unit_price(item["Price"]) * quantity).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                order_rows.append([
                    customer_name,
                    item["Menu Name"],
                    quantity,
                    "",
                    "",
                    order_method,
                    float(line_total),
                ])
            append_order_rows_to_sheet(order_rows)
        except Exception:
            app.logger.exception("Unable to append submitted order to Google Sheets")
            flash("Your order could not be saved to the order spreadsheet. Please try again.", "error")
            return redirect(url_for("home"))

        for item, quantity in zip(menu, requested_quantities):
            item["Qty Ordered"] = int(item.get("Qty Ordered", 0)) + quantity
        save_site_data(site_data)

    flash("Your order has been submitted.", "success")
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        pickup_date = request.form.get("pickup_date", "")
        try:
            date.fromisoformat(pickup_date)
        except ValueError:
            flash("Choose a valid pickup date.", "error")
            return redirect(url_for("admin"))

        with DATA_LOCK:
            site_data = load_site_data()
            site_data["pickup_dates"].setdefault(pickup_date, {"menu": []})
            if not site_data.get("active_pickup_date"):
                site_data["active_pickup_date"] = pickup_date
            save_site_data(site_data)
        return redirect(url_for("admin_manage_date", pickup_date=pickup_date))

    site_data = load_site_data()
    return render_template(
        "admin_dates.html",
        pickup_dates=sorted(site_data["pickup_dates"], reverse=True),
        active_pickup_date=site_data["active_pickup_date"],
    )


@app.route("/admin/<pickup_date>")
def admin_manage_date(pickup_date):
    try:
        date.fromisoformat(pickup_date)
    except ValueError:
        flash("Choose a valid pickup date.", "error")
        return redirect(url_for("admin"))

    site_data = load_site_data()
    if pickup_date not in site_data["pickup_dates"]:
        flash("That pickup date does not exist yet.", "error")
        return redirect(url_for("admin"))

    menu = []
    for item in site_data["pickup_dates"][pickup_date]["menu"]:
        menu_item = dict(item)
        maximum = menu_item.get("Qty Max")
        menu_item["Qty Remaining"] = (
            max(0, int(maximum) - int(menu_item.get("Qty Ordered", 0)))
            if maximum is not None else None
        )
        menu.append(menu_item)

    return render_template(
        "admin.html",
        pickup_date=pickup_date,
        active_pickup_date=site_data["active_pickup_date"],
        menu=menu,
    )


@app.route("/admin/<pickup_date>/activate", methods=["POST"])
def admin_activate_date(pickup_date):
    with DATA_LOCK:
        site_data = load_site_data()
        if pickup_date not in site_data["pickup_dates"]:
            flash("That pickup date does not exist.", "error")
            return redirect(url_for("admin"))
        site_data["active_pickup_date"] = pickup_date
        save_site_data(site_data)
    flash("This menu is now active on the customer page.", "success")
    return redirect(url_for("admin_manage_date", pickup_date=pickup_date))


@app.route("/admin/<pickup_date>/menu/add", methods=["POST"])
def admin_add_menu_item(pickup_date):
    try:
        menu_item = parse_menu_item(request.form, request.files.get("image"))
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin_manage_date", pickup_date=pickup_date))

    with DATA_LOCK:
        site_data = load_site_data()
        if pickup_date not in site_data["pickup_dates"]:
            flash("That pickup date does not exist.", "error")
            return redirect(url_for("admin"))
        site_data["pickup_dates"][pickup_date]["menu"].append(menu_item)
        save_site_data(site_data)
    flash(f"{menu_item['Menu Name']} was added.", "success")
    return redirect(url_for("admin_manage_date", pickup_date=pickup_date))


@app.route("/admin/<pickup_date>/menu/<int:item_index>/update", methods=["POST"])
def admin_update_menu_item(pickup_date, item_index):
    site_data = load_site_data()
    if pickup_date not in site_data["pickup_dates"]:
        flash("That pickup date does not exist.", "error")
        return redirect(url_for("admin"))
    menu = site_data["pickup_dates"][pickup_date]["menu"]
    if item_index >= len(menu):
        flash("That menu item no longer exists.", "error")
        return redirect(url_for("admin_manage_date", pickup_date=pickup_date))

    try:
        menu_item = parse_menu_item(
            request.form,
            request.files.get("image"),
            existing=menu[item_index],
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin_manage_date", pickup_date=pickup_date))

    with DATA_LOCK:
        site_data = load_site_data()
        menu = site_data["pickup_dates"][pickup_date]["menu"]
        if item_index >= len(menu):
            flash("That menu item no longer exists.", "error")
            return redirect(url_for("admin_manage_date", pickup_date=pickup_date))
        menu[item_index] = menu_item
        save_site_data(site_data)
    flash(f"{menu_item['Menu Name']} was updated.", "success")
    return redirect(url_for("admin_manage_date", pickup_date=pickup_date))


@app.route("/admin/<pickup_date>/menu/<int:item_index>/delete", methods=["POST"])
def admin_delete_menu_item(pickup_date, item_index):
    with DATA_LOCK:
        site_data = load_site_data()
        if pickup_date not in site_data["pickup_dates"]:
            flash("That pickup date does not exist.", "error")
            return redirect(url_for("admin"))
        menu = site_data["pickup_dates"][pickup_date]["menu"]
        if item_index >= len(menu):
            flash("That menu item no longer exists.", "error")
        else:
            deleted_name = menu.pop(item_index)["Menu Name"]
            save_site_data(site_data)
            flash(f"{deleted_name} was removed from this pickup date.", "success")
    return redirect(url_for("admin_manage_date", pickup_date=pickup_date))

    return render_template("admin.html", pickup_date=site_data["pickup_date"])

if __name__ == "__main__":
    app.run(debug=True)