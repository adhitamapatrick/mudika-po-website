"""Admin pages (everything under /admin). All of them require the admin password."""

import hmac

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from . import config, models, sheets
from .helpers import dollars_to_cents, parse_date, parse_optional_int

bp = Blueprint("admin", __name__, url_prefix="/admin")

PICKUP_LOCATIONS = (
    "St. Josephine Bakhita Parish, Mississauga",
    "Our Lady of Parish, Scarborough",
    "St. Helen's Parish, Toronto",
)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 1_500_000  # pictures are shrunk in the browser first (see admin_image_resize.js)


### Login / logout ###


@bp.before_request
def require_login():
    """Send anyone who isn't logged in to the password page."""
    if request.endpoint in ("admin.login", "admin.logout"):
        return None
    if not session.get("is_admin"):
        return redirect(url_for("admin.login", next=request.path))
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    admin_password = config.get_setting("ADMIN_PASSWORD")
    if request.method == "POST":
        typed = request.form.get("password", "")
        if admin_password and hmac.compare_digest(typed.encode(), admin_password.encode()):
            session.clear()
            session["is_admin"] = True
            session.permanent = True
            next_page = request.args.get("next", "")
            # Only allow redirects back into the admin area
            return redirect(next_page if next_page.startswith("/admin") else url_for("admin.dates"))
        flash("Wrong password.", "error")
    return render_template("admin_login.html", password_configured=bool(admin_password))


@bp.route("/logout", methods=["POST"])
def logout():
    session.pop("is_admin", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("admin.login"))


### Pickup dates list + site settings ###


@bp.route("/", methods=["GET", "POST"])
def dates():
    if request.method == "POST":
        pickup_date = request.form.get("pickup_date", "")
        if not parse_date(pickup_date):
            flash("Choose a valid pickup date.", "error")
            return redirect(url_for("admin.dates"))
        models.create_pickup_date(pickup_date)
        if not models.get_settings()["active_pickup_date"]:
            models.save_setting("active_pickup_date", pickup_date)
        return redirect(url_for("admin.manage_date", pickup_date=pickup_date))

    return render_template(
        "admin_dates.html",
        pickup_dates=[row["pickup_date"] for row in models.list_pickup_dates()],
        settings=models.get_settings(),
        sheets_configured=sheets.sheets_configured(),
        unsynced_count=models.count_unsynced_orders(),
    )


@bp.route("/settings", methods=["POST"])
def update_settings():
    email = request.form.get("etransfer_email", "").strip()
    if email and ("@" not in email or " " in email):
        flash("Enter a valid e-transfer email.", "error")
        return redirect(url_for("admin.dates"))
    models.save_setting("etransfer_email", email)
    models.save_setting("contact_info", request.form.get("contact_info", "").strip())
    flash("Settings were saved.", "success")
    return redirect(url_for("admin.dates"))


@bp.route("/sheet-sync", methods=["POST"])
def sync_sheet():
    pending = models.list_unsynced_orders()
    copied = sheets.copy_orders_to_sheet(pending)
    if pending and copied == 0:
        flash("Couldn't reach the Google Sheet. Check the sheet settings and try again.", "error")
    else:
        flash(f"Copied {copied} order(s) to the Google Sheet.", "success")
    return redirect(url_for("admin.dates"))


### One pickup date: schedule + menu ###


def _load_date_or_redirect(pickup_date):
    schedule = models.get_pickup_date(pickup_date)
    if not schedule:
        flash("That pickup date does not exist.", "error")
    return schedule


@bp.route("/<pickup_date>")
def manage_date(pickup_date):
    schedule = _load_date_or_redirect(pickup_date)
    if not schedule:
        return redirect(url_for("admin.dates"))
    return render_template(
        "admin.html",
        schedule=schedule,
        active_pickup_date=models.get_settings()["active_pickup_date"],
        menu=models.list_menu_items(pickup_date),
        pickup_locations=PICKUP_LOCATIONS,
    )


@bp.route("/<pickup_date>/activate", methods=["POST"])
def activate_date(pickup_date):
    if _load_date_or_redirect(pickup_date):
        models.save_setting("active_pickup_date", pickup_date)
        flash("This menu is now active on the customer page.", "success")
    return redirect(url_for("admin.manage_date", pickup_date=pickup_date))


@bp.route("/<pickup_date>/delete", methods=["POST"])
def delete_date(pickup_date):
    all_dates = [row["pickup_date"] for row in models.list_pickup_dates()]
    if pickup_date not in all_dates:
        flash("That pickup date does not exist.", "error")
    elif len(all_dates) == 1:
        flash("Keep at least one pickup date.", "error")
    else:
        models.delete_pickup_date(pickup_date)
        if models.get_settings()["active_pickup_date"] == pickup_date:
            models.save_setting("active_pickup_date", max(d for d in all_dates if d != pickup_date))
        flash(f"Pickup date {pickup_date} was removed.", "success")
    return redirect(url_for("admin.dates"))


@bp.route("/<pickup_date>/schedule", methods=["POST"])
def update_schedule(pickup_date):
    if not _load_date_or_redirect(pickup_date):
        return redirect(url_for("admin.dates"))

    close_order_date = request.form.get("close_order_date", "")
    pickup_location = request.form.get("pickup_location", "")
    close_date = parse_date(close_order_date)
    if not close_date or close_date > parse_date(pickup_date) or pickup_location not in PICKUP_LOCATIONS:
        flash("Choose a valid close date and pickup location.", "error")
    else:
        models.update_pickup_schedule(pickup_date, close_order_date, pickup_location)
        flash("Pickup schedule was updated.", "success")
    return redirect(url_for("admin.manage_date", pickup_date=pickup_date))


### Menu items ###


def _read_menu_form(existing=None):
    """Check the menu item form and return clean values. Raises ValueError with a friendly message."""
    form = request.form
    fields = {
        "name": form.get("menu_name", "").strip(),
        "vendor": form.get("vendor_name", "").strip(),
        "details": form.get("details", "").strip(),
    }
    if not fields["name"] or not fields["vendor"]:
        raise ValueError("Menu name and vendor are required.")

    fields["price_cents"] = dollars_to_cents(form.get("price", ""))
    try:
        fields["qty_min"] = parse_optional_int(form.get("qty_min"))
        fields["qty_max"] = parse_optional_int(form.get("qty_max"))
        fields["qty_ordered"] = parse_optional_int(form.get("qty_ordered")) or 0
    except ValueError as error:
        raise ValueError("Quantities must be whole numbers, 0 or more.") from error

    if fields["qty_max"] is not None:
        if fields["qty_min"] is not None and fields["qty_max"] < fields["qty_min"]:
            raise ValueError("Maximum quantity can't be less than the minimum.")
        if fields["qty_ordered"] > fields["qty_max"]:
            raise ValueError("Maximum quantity can't be less than the total already ordered.")

    fields["image_id"] = existing["image_id"] if existing else None
    image = request.files.get("image")
    if image and image.filename:
        if image.mimetype not in ALLOWED_IMAGE_TYPES:
            raise ValueError("Upload a JPG, PNG, or WebP image.")
        data = image.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("That picture is too large. Please use one under 1.5 MB.")
        fields["image_id"] = models.save_image(image.mimetype, data)
    return fields


@bp.route("/<pickup_date>/menu/add", methods=["POST"])
def add_menu_item(pickup_date):
    if not _load_date_or_redirect(pickup_date):
        return redirect(url_for("admin.dates"))
    try:
        fields = _read_menu_form()
    except ValueError as error:
        flash(str(error), "error")
    else:
        models.add_menu_item(pickup_date, fields)
        flash(f"{fields['name']} was added.", "success")
    return redirect(url_for("admin.manage_date", pickup_date=pickup_date))


@bp.route("/<pickup_date>/menu/<int:item_id>/update", methods=["POST"])
def update_menu_item(pickup_date, item_id):
    item = models.get_menu_item(item_id, pickup_date)
    if not item:
        flash("That menu item no longer exists.", "error")
        return redirect(url_for("admin.manage_date", pickup_date=pickup_date))
    try:
        fields = _read_menu_form(existing=item)
    except ValueError as error:
        flash(str(error), "error")
    else:
        models.update_menu_item(item_id, fields, old_image_id=item["image_id"])
        flash(f"{fields['name']} was updated.", "success")
    return redirect(url_for("admin.manage_date", pickup_date=pickup_date))


@bp.route("/<pickup_date>/menu/<int:item_id>/delete", methods=["POST"])
def delete_menu_item(pickup_date, item_id):
    item = models.get_menu_item(item_id, pickup_date)
    if not item:
        flash("That menu item no longer exists.", "error")
    else:
        models.delete_menu_item(item)
        flash(f"{item['name']} was removed from this pickup date.", "success")
    return redirect(url_for("admin.manage_date", pickup_date=pickup_date))
