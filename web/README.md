# LinkedIn Scraper Web UI

Web interface for managing LinkedIn scraping operations. Built with FastAPI + React.

## Quick Start

### Prerequisites

- Python 3.8+ with the `linkedin_scraper` package installed (`pip install -e .` from repo root)
- Node.js 18+
- Playwright Chromium (`playwright install chromium`)
- Tor (optional, for IP rotation)

### 1. Install dependencies

```bash
# From repo root
pip install -e .
playwright install chromium

# Backend
cd web
pip install -r requirements.txt

# Frontend
cd web/frontend
npm install
```

### 2. Install and start Tor (optional, recommended)

Tor routes browser traffic through rotating IPs to avoid LinkedIn rate limiting. The scraper auto-detects Tor — if it's running, traffic routes through it automatically.

**macOS:**
```bash
brew install tor

# Enable control port for IP renewal between scrape batches
echo -e "ControlPort 9051\nCookieAuthentication 0" >> /opt/homebrew/etc/tor/torrc

# Start Tor
brew services start tor
```

**Ubuntu/Debian:**
```bash
sudo apt install tor

# Enable control port
echo -e "ControlPort 9051\nCookieAuthentication 0" | sudo tee -a /etc/tor/torrc

# Restart
sudo systemctl restart tor
```

**Verify Tor is running:**
```bash
# Should return an IP different from your real one
curl --socks5 127.0.0.1:9050 https://api.ipify.org
```

**Note:** LinkedIn blocks some Tor exit nodes. If you get blocked, stop Tor and the scraper will automatically fall back to your direct IP with human-like delays (30-60s between actions).

### 3. Start the servers

```bash
# Terminal 1: Start Tor (if not using brew services)
tor

# Terminal 2: Backend (from web/)
cd web
uvicorn backend.main:app --reload --port 8000

# Terminal 3: Frontend dev server (from web/frontend/)
cd web/frontend
npm run dev
```

Open http://localhost:5173

### Production mode

```bash
cd web/frontend
npm run build
cd ../
uvicorn backend.main:app --port 8000
```

Open http://localhost:8000

## Features

### Session Management

Create and manage LinkedIn authentication sessions. Three methods:

- **li_at cookie** — Paste your `li_at` cookie value from browser DevTools (Application > Cookies > linkedin.com > li_at)
- **Email/password** — Programmatic login (may trigger security checkpoints)
- **Upload session file** — Upload a Playwright storage state JSON

Sessions can be verified to check if they're still authenticated with LinkedIn.

### Scraping

Each scrape type has a dedicated page with a form, live progress bar, and inline results:

| Type | Input | Output |
|------|-------|--------|
| **Person** | Profile URL | Name, headline, about, experiences, education, skills, accomplishments, contacts |
| **Company** | Company URL | Name, industry, size, headquarters, about, employees |
| **Job** | Job URL | Title, company, location, description, benefits |
| **Job Search** | Keywords, location, limit | List of matching job URLs |
| **Company Posts** | Company URL, limit | Post text, reactions, comments, reposts, images |
| **Extract Users** | Company URL, posts limit, session(s) | Users who reacted/reposted — name, headline, profile URL, engagement type |

Scraping runs in the background. Progress is streamed via WebSocket in real time.

### Extract Users from Posts

A lead-generation workflow that chains multiple scrapers:

1. Scrapes posts from a company page
2. For each post, opens the reactions modal and extracts users who liked it
3. Opens the reposts modal and extracts users who reshared it
4. Deduplicates across all posts
5. Optionally scrapes each user's full LinkedIn profile

**Session rotation**: Select multiple LinkedIn sessions and the system rotates between them round-robin. When a session gets rate-limited, it's automatically placed in a 5-minute cooldown and traffic shifts to the remaining sessions. This distributes load so each account looks like a normal user with moderate activity.

**Anti-detection**: All operations use randomized human-like behavior — variable delays between actions (5-18s), mouse jitter, chunked scrolling, hover-before-click, and periodic "coffee breaks" (15-45s pauses every 3 operations).

### History & Export

All scrape results are stored in a local SQLite database. The history page provides:

- Filterable/paginated table of all past scrapes
- Status tracking (pending, running, completed, failed)
- Detail view for each result
- JSON and CSV export per result

### Settings

- **Headless mode** — Toggle browser visibility (LinkedIn blocks headless browsers, so this is off by default)
- **Slow Mo** — Add delay between browser actions for debugging
- **Max concurrent sessions** — Limit running Chromium instances (each uses ~100-200MB RAM)

## Architecture

```
web/
├── backend/
│   ├── main.py              # FastAPI app, lifespan, CORS
│   ├── config.py            # Settings (env-based via pydantic-settings)
│   ├── database.py          # SQLite async engine (aiosqlite + SQLAlchemy)
│   ├── models.py            # ORM: linkedin_sessions, scrape_jobs, scrape_results
│   ├── schemas.py           # Request/response Pydantic models
│   ├── browser_pool.py      # One Chromium instance per session, with locking
│   ├── ws_callback.py       # ProgressCallback → WebSocket bridge
│   ├── routers/
│   │   ├── sessions.py      # CRUD + auth endpoints
│   │   ├── scrape.py        # Start scrapes + WebSocket progress
│   │   ├── history.py       # Browse/export past results
│   │   └── settings.py      # Runtime config + health check
│   └── services/
│       ├── session_service.py
│       ├── scrape_service.py
│       └── export_service.py
└── frontend/
    └── src/
        ├── api/              # Axios client per resource
        ├── hooks/            # useWebSocket, useScrapeJob
        ├── stores/           # Zustand global state
        ├── pages/            # One page per route
        ├── components/       # Layout, scrape forms, result cards
        └── types/            # TypeScript interfaces matching backend models
```

### Key design decisions

- **One browser per session** — LinkedIn ties auth to browser context. Browsers start lazily on first use and persist until the server shuts down or the session is deleted.
- **Per-session locking** — Playwright pages aren't concurrency-safe. An `asyncio.Lock` per session serializes scrape operations.
- **JSON blob storage** — Scrape results are stored as JSON in SQLite rather than normalized tables. The deeply nested Pydantic models (Person has 5 nested arrays) don't benefit from relational normalization, and the main access pattern is "get full result by job ID."
- **asyncio.create_task** — Scrapes run as background tasks on the FastAPI event loop. No external task queue needed for single-user usage.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sessions` | List sessions |
| POST | `/api/sessions` | Create session |
| POST | `/api/sessions/{id}/verify` | Check auth status |
| POST | `/api/sessions/{id}/login-cookie` | Auth with li_at cookie |
| POST | `/api/sessions/{id}/login-credentials` | Auth with email/password |
| DELETE | `/api/sessions/{id}` | Delete session |
| POST | `/api/scrape/person` | Start person scrape |
| POST | `/api/scrape/company` | Start company scrape |
| POST | `/api/scrape/job` | Start job scrape |
| POST | `/api/scrape/job-search` | Start job search |
| POST | `/api/scrape/company-posts` | Start posts scrape |
| POST | `/api/scrape/extract-users` | Extract users from posts (multi-session rotation) |
| GET | `/api/scrape/{id}` | Get job status |
| GET | `/api/scrape/{id}/result` | Get result data |
| WS | `/api/scrape/ws/{id}` | Live progress stream |
| GET | `/api/history` | Paginated history |
| GET | `/api/history/{id}/export?format=json\|csv` | Export result |
| DELETE | `/api/history/{id}` | Delete history entry |
| GET | `/api/settings` | Get settings |
| PUT | `/api/settings` | Update settings |
| GET | `/api/health` | Health check |

## Configuration

Environment variables (prefix `SCRAPER_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPER_DATABASE_URL` | `sqlite+aiosqlite:///./web/data/scraper.db` | Database connection |
| `SCRAPER_SESSIONS_DIR` | `./web/data/sessions` | Session file storage |
| `SCRAPER_BROWSER_HEADLESS` | `false` | Headless browser mode |
| `SCRAPER_BROWSER_SLOW_MO` | `0` | Browser action delay (ms) |
| `SCRAPER_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `SCRAPER_MAX_CONCURRENT_SESSIONS` | `3` | Max Chromium instances |

You can also set these in a `.env` file in the `web/` directory.

## Data Storage

All data is stored locally:

- **SQLite database** — `web/data/scraper.db` (auto-created on first run)
- **Session files** — `web/data/sessions/*.json` (Playwright storage state)

To reset everything, delete the `web/data/` directory.
