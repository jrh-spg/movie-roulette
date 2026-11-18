"""Flask application factory."""

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .jellyfin import JellyfinClient
from .tmdb import TMDbClient


def create_app():
    app = Flask(__name__)

    # Trust X-Forwarded-Proto/Host from a reverse proxy (e.g. one terminating
    # HTTPS in front of this app) so generated absolute URLs - used in Open
    # Graph tags for Discord/Facebook link previews - have the right scheme
    # and host instead of always reporting http://<internal-host>.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)

    app.config["JELLYFIN_URL"] = os.environ.get("JELLYFIN_URL", "").rstrip("/")
    app.config["JELLYFIN_API_KEY"] = os.environ.get("JELLYFIN_API_KEY", "")
    app.config["JELLYFIN_USER_ID"] = os.environ.get("JELLYFIN_USER_ID") or None
    app.config["TMDB_API_KEY"] = os.environ.get("TMDB_API_KEY", "")

    if not app.config["JELLYFIN_URL"] or not app.config["JELLYFIN_API_KEY"]:
        app.logger.warning(
            "JELLYFIN_URL and/or JELLYFIN_API_KEY are not set; "
            "the app will not be able to reach Jellyfin until they are configured."
        )

    if not app.config["TMDB_API_KEY"]:
        app.logger.warning(
            "TMDB_API_KEY is not set; \"similar movies\" suggestions will be unavailable."
        )

    app.jellyfin = JellyfinClient(
        base_url=app.config["JELLYFIN_URL"],
        api_key=app.config["JELLYFIN_API_KEY"],
        user_id=app.config["JELLYFIN_USER_ID"],
    )

    app.tmdb = TMDbClient(api_key=app.config["TMDB_API_KEY"])

    from .routes import bp

    app.register_blueprint(bp)

    return app
