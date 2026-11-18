"""Thin wrapper around the parts of The Movie Database (TMDb) API used to
suggest movies similar to the one that was spun. Deliberately kept separate
from app/jellyfin.py: these suggestions draw on TMDb's full catalog (and its
genre/collaborative-filtering recommendations), not just whatever happens to
already be on the Jellyfin server."""

import requests

API_BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w185"


class TMDbError(Exception):
    """Raised when a request to TMDb fails or returns an unexpected response."""


class TMDbClient:
    def __init__(self, api_key, timeout=10):
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path, params=None):
        if not self.api_key:
            raise TMDbError("TMDB_API_KEY must be configured.")
        params = dict(params or {})
        params["api_key"] = self.api_key
        try:
            resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise TMDbError(f"TMDb request to {path} failed: {exc}") from exc
        return resp.json()

    def _find_movie_id(self, imdb_id=None, title=None, year=None):
        """Resolve a TMDb movie id. Prefers an exact IMDb id match (Jellyfin
        already gives us this for most movies); falls back to a title/year
        search for the rare item Jellyfin couldn't match to an IMDb id."""
        if imdb_id:
            data = self._get(f"/find/{imdb_id}", params={"external_source": "imdb_id"})
            results = data.get("movie_results") or []
            if results:
                return results[0]["id"]

        if title:
            params = {"query": title}
            if year:
                params["year"] = year
            results = self._get("/search/movie", params=params).get("results") or []
            if results:
                return results[0]["id"]

        return None

    def get_similar_movies(self, imdb_id=None, title=None, year=None, limit=5):
        """Return up to `limit` movies similar to the given one. Prefers
        TMDb's "recommendations" (collaborative filtering), topping up with
        its genre/keyword-based "similar movies" endpoint if that isn't
        enough to fill `limit`."""
        movie_id = self._find_movie_id(imdb_id=imdb_id, title=title, year=year)
        if not movie_id:
            return []

        results = self._get(f"/movie/{movie_id}/recommendations").get("results") or []
        if len(results) < limit:
            seen_ids = {result["id"] for result in results}
            more = self._get(f"/movie/{movie_id}/similar").get("results") or []
            results += [result for result in more if result["id"] not in seen_ids]

        return [self._format_result(result) for result in results[:limit]]

    @staticmethod
    def _format_result(result):
        poster_path = result.get("poster_path")
        release_date = result.get("release_date") or ""
        year_str = release_date[:4]
        return {
            "title": result.get("title"),
            "year": int(year_str) if year_str.isdigit() else None,
            "overview": result.get("overview"),
            "rating": result.get("vote_average"),
            "poster_url": f"{POSTER_BASE_URL}{poster_path}" if poster_path else None,
            "tmdb_url": f"https://www.themoviedb.org/movie/{result.get('id')}",
        }
