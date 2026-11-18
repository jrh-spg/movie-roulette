"""HTTP routes for Movie Roulette."""

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, url_for

from .jellyfin import JellyfinError
from .tmdb import TMDbError

bp = Blueprint("main", __name__)

# How many top-billed cast members to show as "Starring".
MAX_CAST_MEMBERS = 5

# How many "similar movies" suggestions to show.
MAX_SIMILAR_MOVIES = 4


def _format_movie(item):
    runtime_ticks = item.get("RunTimeTicks")
    # Jellyfin reports runtime in 100-nanosecond ticks.
    runtime_minutes = int(runtime_ticks / 600_000_000) if runtime_ticks else None
    has_image = "Primary" in (item.get("ImageTags") or {})

    try:
        play_url = current_app.jellyfin.get_item_web_url(item.get("Id"))
    except JellyfinError:
        play_url = None

    # ProviderIds keys are case-insensitive in Jellyfin ("Imdb" normally, but
    # be lenient since this varies by metadata plugin/version).
    provider_ids = item.get("ProviderIds") or {}
    imdb_id = next((v for k, v in provider_ids.items() if k.lower() == "imdb"), None)
    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None

    # People is already ordered by billing; keep the top-billed actors only.
    cast = [
        person.get("Name")
        for person in item.get("People", [])
        if person.get("Type") == "Actor" and person.get("Name")
    ][:MAX_CAST_MEMBERS]
    directors = [
        person.get("Name")
        for person in item.get("People", [])
        if person.get("Type") == "Director" and person.get("Name")
    ]

    return {
        "id": item.get("Id"),
        "name": item.get("Name"),
        "year": item.get("ProductionYear"),
        "overview": item.get("Overview"),
        "genres": item.get("Genres", []),
        "cast": cast,
        "directors": directors,
        "rating": item.get("CommunityRating"),
        "official_rating": item.get("OfficialRating"),
        "runtime_minutes": runtime_minutes,
        "has_image": has_image,
        "play_url": play_url,
        "imdb_id": imdb_id,
        "imdb_url": imdb_url,
        # Stable, shareable link to this movie (used for Discord/Facebook
        # previews) with Open Graph tags describing the movie itself.
        "share_url": url_for("main.movie_share", item_id=item.get("Id"), _external=True),
    }


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/random")
def api_random():
    genre = request.args.get("genre") or None
    try:
        item = current_app.jellyfin.get_random_movie(genre=genre)
    except JellyfinError as exc:
        return jsonify({"error": str(exc)}), 502
    if not item:
        message = (
            f'No movies found for genre "{genre}".' if genre else "No movies found on the server."
        )
        return jsonify({"error": message}), 404
    return jsonify(_format_movie(item))


@bp.route("/api/genres")
def api_genres():
    try:
        genres = current_app.jellyfin.get_genres()
    except JellyfinError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(genres)


@bp.route("/api/similar")
def api_similar():
    """Movies similar to a given one, sourced from TMDb rather than the
    Jellyfin library, so suggestions aren't limited to what's already on the
    server. Takes the spun movie's own identifying info as query params
    (imdb_id/title/year) instead of a Jellyfin item id so it doesn't need a
    second round-trip to Jellyfin."""
    imdb_id = request.args.get("imdb_id") or None
    title = request.args.get("title") or None
    year = request.args.get("year") or None
    if not imdb_id and not title:
        return jsonify({"error": "imdb_id or title is required."}), 400

    try:
        results = current_app.tmdb.get_similar_movies(
            imdb_id=imdb_id, title=title, year=year, limit=MAX_SIMILAR_MOVIES
        )
    except TMDbError as exc:
        return jsonify({"error": str(exc)}), 502

    for result in results:
        # If a suggestion is already in the Jellyfin library, prefer linking
        # there over TMDb so the user can play it directly. A lookup failure
        # just means we fall back to the TMDb link, not a broken response.
        try:
            jellyfin_item = current_app.jellyfin.find_movie_by_title(result["title"], result["year"])
        except JellyfinError:
            jellyfin_item = None
        if jellyfin_item:
            try:
                result["jellyfin_url"] = current_app.jellyfin.get_item_web_url(jellyfin_item.get("Id"))
            except JellyfinError:
                pass

    return jsonify(results)


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

