"""
Settings and secrets.

The app reads its secrets (admin password, Flask secret key, Google Sheet link)
from one of two places:

  * On your computer (`python app.py`): from environment variables, which
    app.py loads from the `.env` file in the project folder.
  * On Cloudflare: from the Worker's "Variables and Secrets", which Cloudflare
    hands to us with every request (see src/worker.py).

Everything else in the app calls `get_setting("NAME")` and doesn't need to
care which one it is.
"""

import os

### Cloudflare environment (set by src/worker.py on every request) ###

_worker_env = None


def use_worker_env(env):
    """Remember Cloudflare's environment object so settings and the database can use it."""
    global _worker_env
    _worker_env = env


def worker_env():
    """Return Cloudflare's environment object, or None when running on your computer."""
    return _worker_env


def running_on_cloudflare():
    return _worker_env is not None


### Reading a setting ###


def get_setting(name, default=None):
    """Return a secret/variable by name, from Cloudflare if available, otherwise from the environment."""
    if _worker_env is not None:
        value = getattr(_worker_env, name, None)
        if isinstance(value, str) and value != "":
            return value
    value = os.environ.get(name)
    if value:
        return value
    return default
