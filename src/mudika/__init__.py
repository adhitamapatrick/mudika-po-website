"""
Mudika PO website.

Folder guide:
  config.py           settings and secrets (admin password, sheet link, ...)
  database.py         the database connection and table definitions
  models.py           all reading/writing of data
  helpers.py          small shared helpers (dates, money, validation)
  sheets.py           copying orders to the Google Sheet
  routes_customer.py  customer pages (order form, receipt)
  routes_admin.py     admin pages (/admin)
  templates/          the HTML pages
"""

import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask

from . import config

# The project folder (two levels above this file). Falls back safely on Cloudflare,
# where the code runs from a different folder layout.
_here = Path(__file__).resolve()
PROJECT_DIR = _here.parents[2] if len(_here.parents) > 2 else _here.parent


def create_app():
    app = Flask(
        __name__,
        # CSS, JavaScript and the logo. On Cloudflare these are served directly from public/.
        static_folder=str(PROJECT_DIR / "public" / "static"),
        static_url_path="/static",
    )

    ### Security settings ###
    app.config.update(
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,         # largest upload/form allowed
        SESSION_COOKIE_HTTPONLY=True,               # page scripts can't read the login cookie
        SESSION_COOKIE_SAMESITE="Lax",              # other websites can't submit forms as you
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    )
    app.secret_key = config.get_setting("FLASK_SECRET_KEY") or secrets.token_hex(32)

    ### Template helpers ###
    from .helpers import parse_contacts

    app.jinja_env.filters["contacts"] = parse_contacts

    ### Pages ###
    from . import routes_admin, routes_customer

    app.register_blueprint(routes_customer.bp)
    app.register_blueprint(routes_admin.bp)
    return app


def apply_cloudflare_settings(app):
    """Called on Cloudflare once the secrets are available (see src/worker.py)."""
    secret_key = config.get_setting("FLASK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Add a FLASK_SECRET_KEY secret in Cloudflare (see README).")
    app.secret_key = secret_key
    app.config["SESSION_COOKIE_SECURE"] = True  # login cookie only travels over https
