"""Thin wrapper around the parts of the Jellyfin REST API this app needs."""

import requests

# Extra metadata fields to request alongside each movie item. ProviderIds
# carries external ids (IMDb, TMDb, ...) used to link out to IMDb. People
# carries cast/crew, used to show the starring actors.
MOVIE_FIELDS = "Overview,Genres,ProductionYear,CommunityRating,OfficialRating,RunTimeTicks,ProviderIds,People"


class JellyfinError(Exception):
    """Raised when a request to Jellyfin fails or returns an unexpected response."""


class JellyfinClient:
    def __init__(self, base_url, api_key, user_id=None, timeout=10):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self.timeout = timeout
        self._server_id = None

    def _headers(self):
        # Some Jellyfin versions reject a bare X-Emby-Token header and
        # require the full MediaBrowser authorization scheme instead, so we
        # send both for broad compatibility.
        auth = (
            f'MediaBrowser Token="{self.api_key}", Client="movie-roulette", '
            'Device="movie-roulette", DeviceId="movie-roulette", Version="1.0.0"'
        )
        return {"X-Emby-Token": self.api_key, "Authorization": auth}

    def _items_path(self):
        # If a specific Jellyfin user is configured, scope queries to that
        # user (required for things like per-user playback state). Otherwise
        # fall back to the server-wide /Items endpoint.
        return f"/Users/{self.user_id}/Items" if self.user_id else "/Items"

    def _get(self, path, params=None, stream=False):
        if not self.base_url or not self.api_key:
            raise JellyfinError("JELLYFIN_URL and JELLYFIN_API_KEY must be configured.")
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(
                url, headers=self._headers(), params=params, timeout=self.timeout, stream=stream
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise JellyfinError(f"Jellyfin request to {path} failed: {exc}") from exc
        return resp

    def get_random_movie(self, genre=None):
        """Ask Jellyfin to pick a single random movie from across the whole
        server, optionally restricted to a single genre."""
        params = {
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "SortBy": "Random",
            "Limit": 1,
            "Fields": MOVIE_FIELDS,
        }
        if genre:
            params["Genres"] = genre
        items = self._get(self._items_path(), params=params).json().get("Items", [])
        return items[0] if items else None

    def get_genres(self):
        """Return the sorted list of genre names across all movies on the server."""
        params = {
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "SortBy": "SortName",
        }
        if self.user_id:
            params["UserId"] = self.user_id
        items = self._get("/Genres", params=params).json().get("Items", [])
        return [item["Name"] for item in items if item.get("Name")]

    def get_movie_by_id(self, item_id):
        """Look up a single movie by id (used for shareable per-movie links)."""
        params = {"Ids": item_id, "Fields": MOVIE_FIELDS}
        items = self._get(self._items_path(), params=params).json().get("Items", [])
        return items[0] if items else None

    def find_movie_by_title(self, title, year=None):
        """Look up a movie already in the library by title (used to check
        whether a TMDb "similar movies" suggestion is already available in
        Jellyfin). Requires an exact, case-insensitive title match to avoid
        linking to an unrelated movie that merely shares a search term;
        prefers a match on `year` when more than one movie shares a title."""
        params = {
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "SearchTerm": title,
            "Fields": "ProductionYear",
            "Limit": 10,
        }
        items = self._get(self._items_path(), params=params).json().get("Items", [])
        normalized_title = title.strip().lower()
        matches = [item for item in items if (item.get("Name") or "").strip().lower() == normalized_title]
        if not matches:
            return None
        if year:
            exact_year_match = next((item for item in matches if item.get("ProductionYear") == year), None)
            if exact_year_match:
                return exact_year_match
        return matches[0]

    def get_image(self, item_id, image_type="Primary"):
        """Fetch raw image bytes + content type for an item, for proxying to the browser."""
        resp = self._get(f"/Items/{item_id}/Images/{image_type}", stream=True)
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")

    def get_server_id(self):
        """Return the server's GUID (needed to build web client deep links), cached after first call."""
        if self._server_id is None:
            self._server_id = self._get("/System/Info/Public").json().get("Id")
        return self._server_id

    def get_item_web_url(self, item_id):
        """Build a link to the item's details page in the Jellyfin web client, Play button included."""
        server_id = self.get_server_id()
        url = f"{self.base_url}/web/#/details?id={item_id}"
        if server_id:
            url += f"&serverId={server_id}"
        return url
