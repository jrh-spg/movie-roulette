"""Flask application factory."""

import os

from flask import Flask

from .jellyfin import JellyfinClient


def create_app():
    app = Flask(__name__)

    app.config["JELLYFIN_URL"] = os.environ.get("JELLYFIN_URL", "").rstrip("/")
    app.config["JELLYFIN_API_KEY"] = os.environ.get("JELLYFIN_API_KEY", "")
    app.config["JELLYFIN_USER_ID"] = os.environ.get("JELLYFIN_USER_ID") or None

    if not app.config["JELLYFIN_URL"] or not app.config["JELLYFIN_API_KEY"]:
        app.logger.warning(
            "JELLYFIN_URL and/or JELLYFIN_API_KEY are not set; "
            "the app will not be able to reach Jellyfin until they are configured."
        )

    app.jellyfin = JellyfinClient(
        base_url=app.config["JELLYFIN_URL"],
        api_key=app.config["JELLYFIN_API_KEY"],
        user_id=app.config["JELLYFIN_USER_ID"],
    )

    from .routes import bp

    app.register_blueprint(bp)

    return app
