"""
Cloudflare entry point. Cloudflare runs this file (see "main" in wrangler.jsonc).
To run the site on your own computer, use `python app.py` instead.
"""

from workers import wsgi

from mudika import apply_cloudflare_settings, config, create_app

app = create_app()
_settings_applied = False


def application(environ, start_response):
    """Give the app Cloudflare's secrets and database before handling each request."""
    global _settings_applied
    config.use_worker_env(environ["workers.env"])
    if not _settings_applied:
        apply_cloudflare_settings(app)
        _settings_applied = True
    return app(environ, start_response)


Default = wsgi.entrypoint(application)
