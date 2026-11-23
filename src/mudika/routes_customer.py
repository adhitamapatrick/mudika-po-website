"""Customer pages: the order form, submitting an order, and the receipt page."""

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, session, url_for

from . import models, sheets
from .database import is_sold_out_error
from .helpers import (
    ADDITIONAL_INFO_MAX_LENGTH,
    PAYMENT_METHODS,
    is_valid_phone,
    parse_date,
    payment_label,
    pretty_date,
    today_in_toronto,
)

bp = Blueprint("customer", __name__)


### Helpers for this page ###


def _active_schedule():
    """Return (settings, pickup schedule) for the date shown to customers. Schedule may be None."""
    settings = models.get_settings()
    schedule = models.get_pickup_date(settings["active_pickup_date"]) if settings["active_pickup_date"] else None
    return settings, schedule


def _orders_are_closed(schedule):
    close_date = parse_date(schedule["close_order_date"])
    return close_date is not None and today_in_toronto() > close_date


### Order form (main page) ###


@bp.route("/")
def home():
    settings, schedule = _active_schedule()
    menu = models.list_menu_items(schedule["pickup_date"]) if schedule else []
    return render_template(
        "home.html",
        settings=settings,
        schedule=schedule,
        menu=menu,
        orders_closed=bool(schedule) and _orders_are_closed(schedule),
        pretty_date=pretty_date,
        additional_info_max_length=ADDITIONAL_INFO_MAX_LENGTH,
    )


### Submitting an order ###


@bp.route("/order", methods=["POST"])
def submit_order():
    settings, schedule = _active_schedule()
    if not schedule:
        flash("Orders are not open right now.", "error")
        return redirect(url_for("customer.home"))
    if _orders_are_closed(schedule):
        flash("Sorry, orders for this pickup date are closed.", "error")
        return redirect(url_for("customer.home"))

    # 1. Check the customer's details
    customer = {
        "name": request.form.get("customer_name", "").strip(),
        "phone": request.form.get("customer_phone", "").strip(),
        "payment_method": request.form.get("payment_method", ""),
        "additional_info": request.form.get("additional_info", "").strip()[:ADDITIONAL_INFO_MAX_LENGTH],
    }
    if not customer["name"] or not is_valid_phone(customer["phone"]) or customer["payment_method"] not in PAYMENT_METHODS:
        flash("Enter your name, a valid 10-digit phone number, and choose a payment method.", "error")
        return redirect(url_for("customer.home"))

    # 2. Read the quantity for each menu item (form fields are named quantity_<item id>)
    chosen_items = []
    for item in models.list_menu_items(schedule["pickup_date"]):
        try:
            quantity = int(request.form.get(f"quantity_{item['id']}", "0") or 0)
        except ValueError:
            quantity = -1
        if quantity < 0:
            flash("Please enter valid quantities.", "error")
            return redirect(url_for("customer.home"))
        if quantity == 0:
            continue
        if item["qty_remaining"] is not None and quantity > item["qty_remaining"]:
            flash(f"Only {item['qty_remaining']} {item['name']} left. Please adjust your order.", "error")
            return redirect(url_for("customer.home"))
        if item["qty_min"] and quantity < item["qty_min"]:
            flash(f"The minimum order for {item['name']} is {item['qty_min']}.", "error")
            return redirect(url_for("customer.home"))
        chosen_items.append((item, quantity))

    if not chosen_items:
        flash("Choose at least one item before submitting your order.", "error")
        return redirect(url_for("customer.home"))

    # 3. Save the order in the database
    try:
        order_id = models.create_order(schedule["pickup_date"], customer, chosen_items)
    except Exception as error:
        if is_sold_out_error(error):
            flash("Sorry, one of your items just sold out. Please review the menu and try again.", "error")
        else:
            flash("Your order could not be saved. Please try again.", "error")
        return redirect(url_for("customer.home"))

    # 4. Copy it to the Google Sheet (if this fails, the order is still saved)
    sheets.copy_orders_to_sheet([models.get_order(order_id)])

    session["last_order_id"] = order_id
    return redirect(url_for("customer.order_confirmation"))


### Receipt page ###


@bp.route("/order/confirmation")
def order_confirmation():
    order = models.get_order(session.get("last_order_id", ""))
    if not order:
        flash("We couldn't find your receipt. Please contact us if you need your order details.", "error")
        return redirect(url_for("customer.home"))

    settings = models.get_settings()
    schedule = models.get_pickup_date(order["pickup_date"])
    return render_template(
        "order_success.html",
        order=order,
        schedule=schedule,
        settings=settings,
        payment_label=payment_label(order["payment_method"], settings["etransfer_email"]),
        pretty_date=pretty_date,
    )


### Menu pictures ###


@bp.route("/images/<image_id>")
def menu_image(image_id):
    image = models.get_image(image_id)
    if not image:
        abort(404)
    content_type, data = image
    return Response(data, content_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
