"""Thin wrapper around the parts of the Jellyfin REST API this app needs."""

import requests


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

    def get_random_movie(self):
        """Ask Jellyfin to pick a single random movie from across the whole server."""
        params = {
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "SortBy": "Random",
            "Limit": 1,
            "Fields": "Overview,Genres,ProductionYear,CommunityRating,OfficialRating,RunTimeTicks",
        }
        items = self._get(self._items_path(), params=params).json().get("Items", [])
        return items[0] if items else None

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
