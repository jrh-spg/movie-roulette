# Movie Roulette

A tiny Flask + uWSGI app that picks a random movie from your Jellyfin
server. Hit **Spin** to get a random title with its poster, overview,
genres, rating, runtime, and a link to open it in Jellyfin and play it.

## How it works

- `app/jellyfin.py` talks to the Jellyfin REST API:
  - `GET /Items?...&SortBy=Random&Limit=1` to ask Jellyfin itself to pick a
    random movie from across the whole server, which is far cheaper than
    fetching every movie and picking one client-side.
  - `GET /Items/{id}/Images/Primary` to fetch the poster, which the app
    proxies to the browser so your Jellyfin API key never reaches the
    client.
  - `GET /System/Info/Public` to look up the server's GUID, used to build a
    `.../web/#/details?id=<id>&serverId=<id>` link to the movie's details
    page in Jellyfin's web client (where Play is one click away).
- `app/routes.py` exposes:
  - `GET /` — the HTML page with the Spin button.
  - `GET /api/random` — JSON for a random movie.
  - `GET /poster/<id>` — proxied poster image.
  - `GET /healthz` — basic health check.
- `wsgi.py` / `uwsgi.ini` run the app under uWSGI's built-in HTTP server on
  port 5000 inside the container.

## Setup

### 1. Create a Jellyfin API key

In Jellyfin: **Dashboard → Advanced → API Keys → +** (give it any name, e.g.
`movie-roulette`). Copy the generated key.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
JELLYFIN_URL=http://<your-jellyfin-host>:8096
JELLYFIN_API_KEY=<the key you generated>
```

`JELLYFIN_USER_ID` is optional — only set it if you want queries scoped to a
specific Jellyfin user account instead of the whole server. You can find a
user's GUID in the URL of their profile page in the Jellyfin dashboard.

> **Note:** If Jellyfin runs in its own Docker Compose stack, make sure
> `JELLYFIN_URL` is reachable from this container (e.g. the host's LAN IP,
> or put both stacks on the same Docker network and use the Jellyfin service
> name as the hostname).

### 3. Run it

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
python wsgi.py
```

This runs Flask's dev server on port 5000 with debug/auto-reload enabled.
