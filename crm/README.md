# Twenty CRM — Self-Hosted Setup & LinkedIn Scraper Integration

This guide covers setting up Twenty CRM via Docker Compose and integrating it with the LinkedIn scraper to auto-sync scraped data into CRM contacts and companies.

## Prerequisites

- Docker and Docker Compose installed
- Minimum 2GB RAM on the host
- A domain with SSL (required for clipboard/browser features)

## Quick Start

```bash
cd crm
cp .env.example .env
# Edit .env — set APP_SECRET, PG_DATABASE_PASSWORD, SERVER_URL

docker compose up -d
```

Twenty CRM will be available at `http://localhost:3000` (or your `SERVER_URL`).

### First-time setup

1. Open the Twenty CRM URL in your browser
2. Create an admin account
3. Go to **Settings → API & Webhooks → Create Key**
4. Copy the API key — you'll need it for the scraper integration

---

## Docker Compose Services

| Service | Port | Purpose |
|---------|------|---------|
| `twenty-server` | 3000 | Main application server |
| `twenty-worker` | — | Background job processor |
| `twenty-db` | 5432 (internal) | PostgreSQL 16 database |
| `twenty-redis` | 6379 (internal) | Redis cache and message queue |

### Persistent volumes

- `db-data`: PostgreSQL data
- `server-local-data`: Uploaded files, attachments

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_SECRET` | Yes | Security token — generate with `openssl rand -base64 32` |
| `PG_DATABASE_PASSWORD` | Yes | PostgreSQL password (avoid special characters) |
| `SERVER_URL` | Yes | External URL (e.g. `https://crm.yourdomain.com`) |
| `STORAGE_TYPE` | No | `local` (default) or `s3` for file storage |

---

## Data Model Mapping

### LinkedIn Person → Twenty People

| LinkedIn Scraper Field | Twenty CRM Field | Type | Notes |
|---|---|---|---|
| `name` (split on first space) | `name.firstName` / `name.lastName` | Name | Standard field |
| `contacts[type=email].value` | `emails.primaryEmail` | Email | First email contact |
| `contacts[type=phone].value` | `phones.primaryPhoneNumber` | Phone | First phone contact |
| `experiences[0].position_title` | `jobTitle` | Text | Current role headline |
| `location` | `city` | Text | Parse city from location |
| `linkedin_url` | `linkedinUrl` | Links | **Custom field** |
| `about` | `intro` | Rich Text | **Custom field** |
| `open_to_work` | `openToWork` | Boolean | **Custom field** |
| `experiences` | `experiencesJson` | JSON | **Custom field** — full experience array |
| `educations` | `educationsJson` | JSON | **Custom field** — full education array |

### LinkedIn Company → Twenty Companies

| LinkedIn Scraper Field | Twenty CRM Field | Type | Notes |
|---|---|---|---|
| `name` | `name` | Text | Standard field |
| `website` | `domainName` | Links | Standard field |
| `linkedin_url` | `linkedinUrl` | Links | **Custom field** |
| `industry` | `industry` | Text | **Custom field** |
| `company_size` | `employeeCount` | Number | **Custom field** — parse from range |
| `headquarters` | `address` | Address | **Custom field** |
| `founded` | `founded` | Text | **Custom field** |
| `about_us` | `aboutUs` | Rich Text | **Custom field** |
| `specialties` | `specialties` | Text | **Custom field** |
| `company_type` | `companyType` | Text | **Custom field** |

### PostEngagementUser → Twenty People + Notes

| LinkedIn Scraper Field | Twenty CRM Field | Notes |
|---|---|---|
| `name` (split) | `name.firstName` / `name.lastName` | |
| `headline` | `jobTitle` | |
| `profile_url` | `linkedinUrl` (custom) | |
| `engagement_type` | — | Added as a **Note** on the person: "Reacted to {company} post on {date}" |

**Deduplication**: Before creating a person, search Twenty for existing records matching `linkedinUrl`. If found, update instead of creating a duplicate.

---

## Custom Fields Setup

Before syncing data, you need to create custom fields in Twenty CRM. Use the metadata API or the UI:

### Via Settings UI

1. Go to **Settings → Data Model → People**
2. Click **+ Add Field** for each:
   - `linkedinUrl` — Type: Links
   - `intro` — Type: Rich Text
   - `openToWork` — Type: Boolean
   - `engagementSource` — Type: Text
   - `experiencesJson` — Type: JSON
   - `educationsJson` — Type: JSON

3. Go to **Settings → Data Model → Companies**
4. Click **+ Add Field** for each:
   - `linkedinUrl` — Type: Links
   - `industry` — Type: Text
   - `employeeCount` — Type: Number
   - `founded` — Type: Text
   - `aboutUs` — Type: Rich Text
   - `specialties` — Type: Text
   - `companyType` — Type: Text

### Via REST API (programmatic)

```bash
# Create custom field on People object
curl -X POST https://your-crm.com/rest/metadata/fields \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "linkedinUrl",
    "label": "LinkedIn URL",
    "type": "LINKS",
    "objectMetadataId": "<people-object-id>"
  }'
```

See `crm/setup_fields.py` for an automated script that creates all fields.

---

## API Integration

### Authentication

```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### Base URL

- Self-hosted: `https://your-crm-domain.com/rest/`
- Rate limit: 100 requests/minute, 60 records/batch

### Create a Person

```bash
curl -X POST https://your-crm.com/rest/people \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": {
      "firstName": "Satya",
      "lastName": "Nadella"
    },
    "jobTitle": "CEO at Microsoft",
    "emails": { "primaryEmail": "satya@microsoft.com" },
    "city": "Redmond"
  }'
```

### Create a Company

```bash
curl -X POST https://your-crm.com/rest/companies \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Microsoft",
    "domainName": "microsoft.com"
  }'
```

### Link Person to Company

```bash
curl -X PATCH https://your-crm.com/rest/people/<person-id> \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "company": { "connect": "<company-id>" }
  }'
```

### Add a Note to a Person

```bash
curl -X POST https://your-crm.com/rest/notes \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "body": "Reacted to Microsoft company post (LinkedIn engagement extraction)",
    "noteTargets": [{ "personId": "<person-id>" }]
  }'
```

### Search for Existing Person (dedup)

```bash
curl -X GET "https://your-crm.com/rest/people?filter=linkedinUrl[eq]=https://linkedin.com/in/satyanadella/" \
  -H "Authorization: Bearer $API_KEY"
```

---

## Sync Flow

### Manual sync

1. Scrape a LinkedIn profile/company/engagement users via the web UI
2. After scraping completes, click **"Push to CRM"** on the result page
3. The backend maps the scraped data to Twenty CRM fields and calls the REST API
4. Records are created or updated (dedup by LinkedIn URL)

### Auto-sync

1. In **Settings → CRM Integration**, enter your Twenty CRM URL and API key
2. Toggle **Auto-sync** on
3. Every time a scrape completes successfully, results are automatically pushed to Twenty CRM

### Sync logic

```
Scrape completes
  ↓
Map LinkedIn model → Twenty fields
  ↓
Search Twenty for existing record (by linkedinUrl)
  ↓
Found? → PATCH (update)    Not found? → POST (create)
  ↓
If Person has company experience → Find/create Company → Link
  ↓
If PostEngagementUser → Create Person + add Note with engagement context
  ↓
Mark scrape_result as synced_to_crm = true
```

---

## Scraper Web UI Integration

### Settings Page — CRM Section

| Setting | Type | Description |
|---------|------|-------------|
| Twenty CRM URL | Text input | Base URL of your Twenty instance |
| API Key | Password input | Twenty API key (masked) |
| Auto-sync | Toggle | Automatically push results after scraping |
| Test Connection | Button | Verify API key and URL are valid |

### Result Pages — Sync Controls

Each completed scrape result shows:
- **Not synced** — gray badge, "Push to CRM" button
- **Syncing...** — spinner
- **Synced at {datetime}** — green badge, "Re-sync" button

---

## Relationships in Twenty

```
┌──────────────┐       ┌───────────────┐
│    People     │──────▶│   Companies   │
│              │  works │               │
│ firstName    │  at    │ name          │
│ lastName     │       │ domainName    │
│ jobTitle     │       │ linkedinUrl*  │
│ linkedinUrl* │       │ industry*     │
│ intro*       │       │ aboutUs*      │
│ openToWork*  │       │ founded*      │
│              │       │ specialties*  │
└──────┬───────┘       └───────────────┘
       │
       │ has
       ▼
┌──────────────┐
│    Notes      │
│              │
│ body         │  "Reacted to {company} post"
│ personId     │  "Reposted {company} post"
└──────────────┘

* = custom field (needs to be created)
```

---

## File Structure

```
crm/
├── docker-compose.yml    # Twenty CRM services
├── .env.example          # Environment template
├── setup_fields.py       # Script to create custom fields via API
└── README.md             # This file
```

---

## Troubleshooting

### Twenty CRM won't start
- Check Docker logs: `docker compose logs twenty-server`
- Ensure port 3000 is not in use
- Verify PostgreSQL password has no special characters (`@`, `#`, `!` etc.)

### API returns 401
- API key may have expired — regenerate in Settings → API & Webhooks
- Verify the `Authorization: Bearer` header is correct

### Rate limited during sync
- Twenty allows 100 requests/minute
- The sync service adds 0.6s delay between API calls
- For bulk syncs (extract-users with many results), use batch endpoints (60 records/batch)

### Duplicate records in Twenty
- Ensure `linkedinUrl` custom field exists before syncing
- The sync service deduplicates by LinkedIn URL — if the field doesn't exist, it can't search

### SSL/HTTPS issues
- Twenty requires HTTPS for clipboard and some browser features
- Use a reverse proxy (nginx/caddy) with Let's Encrypt for SSL termination
