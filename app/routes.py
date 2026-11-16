"""HTTP routes for Movie Roulette."""

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, url_for

from .jellyfin import JellyfinError

bp = Blueprint("main", __name__)


def _format_movie(item):
    runtime_ticks = item.get("RunTimeTicks")
    # Jellyfin reports runtime in 100-nanosecond ticks.
    runtime_minutes = int(runtime_ticks / 600_000_000) if runtime_ticks else None
    has_image = "Primary" in (item.get("ImageTags") or {})

    try:
        play_url = current_app.jellyfin.get_item_web_url(item.get("Id"))
    except JellyfinError:
        play_url = None

    return {
        "id": item.get("Id"),
        "name": item.get("Name"),
        "year": item.get("ProductionYear"),
        "overview": item.get("Overview"),
        "genres": item.get("Genres", []),
        "rating": item.get("CommunityRating"),
        "official_rating": item.get("OfficialRating"),
        "runtime_minutes": runtime_minutes,
        "has_image": has_image,
        "play_url": play_url,
        # Stable, shareable link to this movie (used for Discord/Facebook
        # previews) with Open Graph tags describing the movie itself.
        "share_url": url_for("main.movie_share", item_id=item.get("Id"), _external=True),
    }


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/random")
def api_random():
    try:
        item = current_app.jellyfin.get_random_movie()
    except JellyfinError as exc:
        return jsonify({"error": str(exc)}), 502
    if not item:
        return jsonify({"error": "No movies found on the server."}), 404
    return jsonify(_format_movie(item))


@bp.route("/movie/<item_id>")
def movie_share(item_id):
    """Shareable, server-rendered page for a single movie with Open Graph tags
    so pasting this link into Discord/Facebook shows a rich preview card."""
    try:
        item = current_app.jellyfin.get_movie_by_id(item_id)
    except JellyfinError as exc:
        current_app.logger.error(str(exc))
        abort(502)
    if not item:
        abort(404)

    movie = _format_movie(item)
    poster_url = url_for("main.poster", item_id=item_id, _external=True) if movie["has_image"] else None
    return render_template("share.html", movie=movie, poster_url=poster_url)


@bp.route("/poster/<item_id>")
def poster(item_id):
    try:
        content, content_type = current_app.jellyfin.get_image(item_id)
    except JellyfinError:
        abort(404)
    return Response(content, content_type=content_type)


@bp.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})

