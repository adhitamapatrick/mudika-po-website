"""
Run the website on your own computer:

    python app.py

then open http://127.0.0.1:5000 (admin page: http://127.0.0.1:5000/admin).
Settings come from the `.env` file in this folder (copy `.env.example` to start).
Data is saved in instance/mudika.sqlite3.
"""

import os
import secrets
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "src"))  # the app's code lives in src/mudika


def load_env_file(path):
    """Read KEY=value lines from .env into environment variables (lines starting with # are ignored)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(PROJECT_DIR / ".env")

# Without FLASK_SECRET_KEY in .env, use a temporary one (you'll be logged out when the app restarts)
os.environ.setdefault("FLASK_SECRET_KEY", secrets.token_hex(32))

from mudika import create_app  # noqa: E402  (must come after loading .env)

app = create_app()

if __name__ == "__main__":
    if not os.environ.get("ADMIN_PASSWORD"):
        print("Tip: set ADMIN_PASSWORD in your .env file to be able to log in to /admin.")
    app.run(debug=True)
