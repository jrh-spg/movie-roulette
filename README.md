# Movie Roulette

A tiny Flask + uWSGI app that picks a random movie from your Jellyfin
server. Pick a genre (or leave it on **All Genres**) and hit **Spin** to
get a random title with its poster, overview, director, starring cast,
genres, rating, runtime, a link to open it in Jellyfin and play it, a link
to its IMDb page, and a row of "You might also like" suggestions pulled
from TMDb.

## How it works

- `app/jellyfin.py` talks to the Jellyfin REST API:
  - `GET /Items?...&SortBy=Random&Limit=1` to ask Jellyfin itself to pick a
    random movie from across the whole server, which is far cheaper than
    fetching every movie and picking one client-side. An optional `Genres`
    filter restricts this to a single genre.
  - `GET /Genres?IncludeItemTypes=Movie&Recursive=true` to list every genre
    present across the movie library, used to populate the genre dropdown.
  - `GET /Items?Ids=<id>` to look up one specific movie by id (used for the
    shareable per-movie link below).
  - `GET /Items?SearchTerm=<title>` to check whether a TMDb "similar movies"
    suggestion is already in the library (requiring an exact,
    case-insensitive title match, preferring one matching `year` too) so
    that suggestion can link straight to Jellyfin instead of TMDb.
  - `GET /Items/{id}/Images/Primary` to fetch the poster, which the app
    proxies to the browser so your Jellyfin API key never reaches the
    client.
  - `GET /System/Info/Public` to look up the server's GUID, used to build a
    `.../web/#/details?id=<id>&serverId=<id>` link to the movie's details
    page in Jellyfin's web client (where Play is one click away).
- `app/tmdb.py` talks to [The Movie Database (TMDb)](https://www.themoviedb.org/)
  API for "You might also like" suggestions, deliberately kept independent
  of the Jellyfin library so recommendations aren't limited to what's
  already on the server:
  - `GET /find/<imdb_id>?external_source=imdb_id` to resolve the spun
    movie's IMDb id (from Jellyfin) to a TMDb id, falling back to
    `GET /search/movie?query=<title>&year=<year>` for the rare movie
    Jellyfin couldn't match to an IMDb id.
  - `GET /movie/<id>/recommendations`, topped up with
    `GET /movie/<id>/similar` if that doesn't return enough results.
- `app/static/app.js` makes the "Play in Jellyfin" button try to switch to
  the official iOS app first (`org.jellyfin.expo://`) on iOS devices,
  falling back to the web client link above after ~1.5s if the app isn't
  installed. There's no official deep link scheme that can jump straight to
  a specific item for an arbitrary self-hosted server (see
  [jellyfin-ios#466](https://github.com/jellyfin/jellyfin-ios/issues/466)),
  so this only switches to the app rather than opening this exact movie.
  Android has no equivalent scheme at all, so it always uses the web link.
- `app/routes.py` exposes:
  - `GET /` — the HTML page with the genre dropdown and Spin button.
  - `GET /api/random?genre=<name>` — JSON for a random movie, optionally
    restricted to one genre. Omit `genre` (or leave it empty) for all movies.
  - `GET /api/genres` — JSON array of genre names for the dropdown.
  - `GET /api/similar?imdb_id=<id>&title=<title>&year=<year>` — JSON array
    of up to 4 TMDb movies similar to the given one, for the "You might
    also like" row. `imdb_id` is preferred; `title`/`year` are a fallback
    used when a movie has no IMDb id. Each result includes a `jellyfin_url`
    if that suggestion is already in the library, so the frontend can link
    there instead of TMDb.
  - `GET /movie/<id>` — a stable, shareable page for one movie, with Open
    Graph/Twitter Card meta tags populated from that movie's poster, title,
    and overview so pasting the link into Discord or sharing it on Facebook
    shows a rich preview card instead of a bare URL.
  - `GET /poster/<id>` — proxied poster image.
  - `GET /healthz` — basic health check.
- `wsgi.py` / `uwsgi.ini` run the app under uWSGI's built-in HTTP server on
  port 5000 inside the container.

## Setup

### 1. Create a Jellyfin API key

In Jellyfin: **Dashboard → Advanced → API Keys → +** (give it any name, e.g.
`movie-roulette`). Copy the generated key.

### 2. Create a TMDb API key

Sign up at [themoviedb.org](https://www.themoviedb.org/), then grab the
"API Key (v3 auth)" value from **Settings → API**. This powers the "You
might also like" suggestions; without it, that row is simply omitted.

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
JELLYFIN_URL=http://<your-jellyfin-host>:8096
JELLYFIN_API_KEY=<the key you generated>
TMDB_API_KEY=<the key you generated>
```

`JELLYFIN_USER_ID` is optional — only set it if you want queries scoped to a
specific Jellyfin user account instead of the whole server. You can find a
user's GUID in the URL of their profile page in the Jellyfin dashboard.

> **Note:** If Jellyfin runs in its own Docker Compose stack, make sure
> `JELLYFIN_URL` is reachable from this container (e.g. the host's LAN IP,
> or put both stacks on the same Docker network and use the Jellyfin service
> name as the hostname).

### 4. Run it

```bash
docker compose up --build -d
```

Open **http://localhost:8154**.

### Logs / troubleshooting

```bash
docker compose logs -f
```

If the page shows an error or spinning returns one, double-check
`JELLYFIN_URL`/`JELLYFIN_API_KEY` and that the container can reach Jellyfin
(e.g. `docker compose exec movie-roulette curl -I $JELLYFIN_URL`).

## Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export JELLYFIN_URL=http://localhost:8096
export JELLYFIN_API_KEY=changeme
export TMDB_API_KEY=changeme
python wsgi.py
```

This runs Flask's dev server on port 5000 with debug/auto-reload enabled.
