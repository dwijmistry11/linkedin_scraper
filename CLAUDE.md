# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Async LinkedIn scraper (v3.x) built with Playwright. Extracts person profiles, company pages, company posts, and job listings. Published to PyPI as `linkedin-scraper`. Python 3.8+.

## Commands

```bash
# Install in dev mode
pip install -e .
pip install -r requirements-dev.txt
playwright install chromium

# Run all tests
pytest

# Run only unit tests (fast, no LinkedIn session needed)
pytest -m "not integration"

# Run a single test file / single test
pytest tests/test_person_scraper.py -v
pytest tests/test_person_scraper.py::test_person_model_to_dict -v

# Run with coverage
pytest --cov=linkedin_scraper -v

# Linting and formatting
black linkedin_scraper/
flake8 linkedin_scraper/
mypy linkedin_scraper/
```

## Architecture

### Three-layer design

1. **`core/`** — Browser lifecycle, authentication, and DOM utilities
   - `browser.py`: `BrowserManager` async context manager wrapping Playwright (launch, session save/load via storage state JSON, cookie management)
   - `auth.py`: `login_with_credentials`, `login_with_cookie`, `is_logged_in`, `wait_for_manual_login`. Login verification polls `is_logged_in()` which checks nav selectors + URL patterns.
   - `utils.py`: Shared page helpers — `retry_async` decorator (exponential backoff), `detect_rate_limit`, `scroll_to_bottom`, `click_see_more_buttons`, `extract_text_safe`, `handle_modal_close`
   - `exceptions.py`: Exception hierarchy rooted at `LinkedInScraperException`

2. **`scrapers/`** — One scraper per entity type, all extend `BaseScraper`
   - `BaseScraper` (in `base.py`) takes a Playwright `Page` + optional `ProgressCallback`. Provides auth checking, rate limit detection, scrolling, safe text extraction, and retry-wrapped click.
   - `PersonScraper`, `CompanyScraper`, `JobScraper`, `JobSearchScraper`, `CompanyPostsScraper`

3. **`models/`** — Pydantic v2 data models returned by scrapers
   - `Person` (with `Experience`, `Education`, `Contact`, `Accomplishment`, `Interest`), `Company` (with `CompanySummary`, `Employee`), `Job`, `Post`

### Callback system

`callbacks.py` provides `ProgressCallback` (base), `ConsoleCallback`, `SilentCallback`, `JSONLogCallback`, `MultiCallback`. Scrapers accept an optional callback for progress reporting.

### Key patterns

- Everything is async/await. Scrapers are used inside `async with BrowserManager() as browser:`.
- Authentication is session-based: save/load Playwright storage state JSON files. The `li_at` cookie is the key auth token.
- LinkedIn actively blocks headless browsers — tests and samples use `headless=False`.
- CSS selectors for LinkedIn change frequently; `is_logged_in()` checks both old-style (`.global-nav__primary-link`) and new-style (`nav a[href*="/feed"]`) selectors.

## Testing

- Tests use `pytest-asyncio` with `asyncio_mode = auto` (no need for `@pytest.mark.asyncio`).
- Integration tests are marked `@pytest.mark.integration` and require a valid `linkedin_session.json` at project root.
- Unit tests mock Playwright objects and test models/utilities without network calls.
- `conftest.py` provides `browser`, `browser_with_session`, and URL fixtures.
