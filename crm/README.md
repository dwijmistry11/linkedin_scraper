# Twenty CRM — Self-Hosted Setup & LinkedIn Scraper Integration

This guide covers setting up Twenty CRM via Docker Compose with AWS services (RDS, S3, ElastiCache) and integrating it with the LinkedIn scraper.

## Prerequisites

- Docker and Docker Compose installed
- Minimum 2GB RAM on the host
- A domain with SSL (required for clipboard/browser features)
- **AWS account** with access to RDS, S3, and optionally ElastiCache

---

## Deployment Options

### Option A: Production (AWS RDS + S3)

Uses AWS RDS for PostgreSQL, S3 for file storage. Only runs the app containers locally.

```bash
cd crm
cp .env.example .env
# Edit .env — fill in AWS credentials and secrets

docker compose up -d
```

### Option B: Local Development

Bundles PostgreSQL and Redis in Docker. No AWS required.

```bash
cd crm
cp .env.example .env
# Edit .env — set APP_SECRET and PG_DATABASE_PASSWORD

docker compose -f docker-compose.local.yml up -d
```

Twenty CRM will be available at `http://localhost:3000` (or your `SERVER_URL`).

### First-time setup

1. Open the Twenty CRM URL in your browser
2. Create an admin account
3. Go to **Settings -> API & Webhooks -> Create Key**
4. Copy the API key — you'll need it for the scraper integration

---

## AWS Infrastructure Setup

### 1. RDS (PostgreSQL)

Create an RDS PostgreSQL 16 instance for Twenty CRM's database.

**AWS Console:**
1. Go to **RDS -> Create database**
2. Choose **PostgreSQL 16**
3. Settings:
   - DB instance identifier: `twenty-crm`
   - Master username: `twenty`
   - Master password: (strong password, avoid `@#!` characters)
4. Instance: `db.t3.micro` (dev) or `db.t3.medium` (prod)
5. Storage: 20GB gp3 (auto-scaling enabled)
6. Connectivity:
   - VPC: same as your EC2/ECS host
   - Public access: No (access via VPC only)
   - Security group: allow port 5432 from your app server
7. Database name: `twenty`
8. Click **Create database**

**Or via AWS CLI:**
```bash
aws rds create-db-instance \
  --db-instance-identifier twenty-crm \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16 \
  --master-username twenty \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 20 \
  --storage-type gp3 \
  --db-name twenty \
  --vpc-security-group-ids sg-xxxxxxxxx \
  --no-publicly-accessible
```

After creation, note the **endpoint** (e.g. `twenty-crm.xxxx.us-east-1.rds.amazonaws.com`).

### 2. S3 (File Storage)

Create an S3 bucket for Twenty CRM's uploaded files, attachments, and images.

**AWS Console:**
1. Go to **S3 -> Create bucket**
2. Bucket name: `your-twenty-crm-files` (globally unique)
3. Region: same as your app server
4. Block all public access: **Yes** (Twenty accesses via IAM keys)
5. Versioning: optional (recommended for data safety)
6. Click **Create bucket**

**Bucket policy** (optional, for tighter access):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::YOUR_ACCOUNT_ID:user/twenty-crm-user"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-twenty-crm-files",
        "arn:aws:s3:::your-twenty-crm-files/*"
      ]
    }
  ]
}
```

**IAM User for S3 access:**
1. Go to **IAM -> Users -> Create user**
2. Name: `twenty-crm-s3`
3. Attach policy: `AmazonS3FullAccess` (or the custom policy above)
4. Create **Access Key** (programmatic access)
5. Save the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

**Or via AWS CLI:**
```bash
aws s3 mb s3://your-twenty-crm-files --region us-east-1

aws iam create-user --user-name twenty-crm-s3
aws iam attach-user-policy --user-name twenty-crm-s3 \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam create-access-key --user-name twenty-crm-s3
```

### 3. ElastiCache Redis (Optional)

For production, use ElastiCache instead of the bundled Redis container.

**AWS Console:**
1. Go to **ElastiCache -> Create cluster**
2. Choose **Redis OSS**
3. Settings:
   - Name: `twenty-crm-redis`
   - Node type: `cache.t3.micro` (dev) or `cache.t3.medium` (prod)
   - Number of replicas: 0 (dev) or 1 (prod)
4. Subnet group: same VPC as your app server
5. Security group: allow port 6379 from your app server
6. Click **Create**

After creation, note the **primary endpoint** (e.g. `twenty-crm-redis.xxxx.cache.amazonaws.com:6379`).

**Or via AWS CLI:**
```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id twenty-crm-redis \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-nodes 1 \
  --security-group-ids sg-xxxxxxxxx
```

If you skip ElastiCache, the bundled `twenty-redis-local` container in `docker-compose.yml` serves as Redis.

---

## Environment Variables

### Production (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_SECRET` | Yes | Security token — `openssl rand -base64 32` |
| `SERVER_URL` | Yes | External URL, e.g. `https://crm.yourdomain.com` |
| **AWS RDS** | | |
| `RDS_HOST` | Yes | RDS endpoint hostname |
| `RDS_PORT` | No | Default: `5432` |
| `RDS_DATABASE` | No | Default: `twenty` |
| `RDS_USERNAME` | Yes | RDS master username |
| `RDS_PASSWORD` | Yes | RDS master password |
| **AWS S3** | | |
| `AWS_REGION` | Yes | e.g. `us-east-1` |
| `S3_BUCKET_NAME` | Yes | S3 bucket name |
| `AWS_ACCESS_KEY_ID` | Yes | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | Yes | IAM secret key |
| `S3_ENDPOINT` | No | Only for S3-compatible (MinIO, DO Spaces) |
| **Redis** | | |
| `REDIS_URL` | Yes | ElastiCache or local Redis URL |

### Local Development (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_SECRET` | Yes | Security token |
| `PG_DATABASE_PASSWORD` | Yes | Local PostgreSQL password |
| `SERVER_URL` | No | Default: `http://localhost:3000` |

---

## Docker Compose Services

### Production (`docker-compose.yml`)

| Service | Port | Purpose |
|---------|------|---------|
| `twenty-server` | 3000 | Main application (connects to RDS + S3) |
| `twenty-worker` | — | Background job processor |
| `twenty-redis-local` | 6379 | Local Redis fallback (remove if using ElastiCache) |

No database container — uses AWS RDS externally.

### Local (`docker-compose.local.yml`)

| Service | Port | Purpose |
|---------|------|---------|
| `twenty-server` | 3000 | Main application |
| `twenty-worker` | — | Background job processor |
| `twenty-db` | 5432 (internal) | Bundled PostgreSQL 16 |
| `twenty-redis` | 6379 (internal) | Bundled Redis |

---

## Architecture Diagram

```
                    ┌─────────────────────┐
                    │   Your Server (EC2)  │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │ twenty-server  │──┼──────┐
                    │  │   :3000       │  │      │
                    │  └───────────────┘  │      │
                    │  ┌───────────────┐  │      │
                    │  │ twenty-worker  │──┼──┐   │
                    │  └───────────────┘  │  │   │
                    └─────────────────────┘  │   │
                                            │   │
                 ┌──────────────────────────┘   │
                 │                              │
     ┌───────────▼───────────┐    ┌─────────────▼──────────┐
     │      AWS RDS          │    │       AWS S3            │
     │   PostgreSQL 16       │    │   File Storage          │
     │                       │    │                        │
     │ twenty-crm.xxxx.     │    │ your-twenty-crm-files  │
     │  rds.amazonaws.com    │    │                        │
     └───────────────────────┘    └────────────────────────┘

     ┌───────────────────────┐
     │   AWS ElastiCache     │  (optional — can use local Redis)
     │      Redis            │
     │                       │
     │ twenty-crm-redis.     │
     │  cache.amazonaws.com  │
     └───────────────────────┘
```

---

## Security Best Practices

### RDS
- Keep RDS in a private subnet (no public access)
- Use security groups to allow only your app server's IP/VPC
- Enable encryption at rest
- Enable automated backups (7-day retention minimum)

### S3
- Block all public access
- Use a dedicated IAM user with minimal permissions (only the bucket)
- Enable server-side encryption (SSE-S3 or SSE-KMS)
- Enable versioning for data recovery

### ElastiCache
- Keep in a private subnet
- Use security groups to restrict access to app server only
- Enable encryption in transit (TLS)

### Application
- Use HTTPS with a valid SSL certificate (Let's Encrypt via nginx/caddy)
- Store `.env` securely — never commit it to git
- Rotate `APP_SECRET` and API keys periodically

---

## Data Model Mapping

### LinkedIn Person -> Twenty People

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
| `experiences` | `experiencesJson` | JSON | **Custom field** |
| `educations` | `educationsJson` | JSON | **Custom field** |

### LinkedIn Company -> Twenty Companies

| LinkedIn Scraper Field | Twenty CRM Field | Type | Notes |
|---|---|---|---|
| `name` | `name` | Text | Standard field |
| `website` | `domainName` | Links | Standard field |
| `linkedin_url` | `linkedinUrl` | Links | **Custom field** |
| `industry` | `industry` | Text | **Custom field** |
| `company_size` | `employeeCount` | Number | **Custom field** |
| `headquarters` | `address` | Address | **Custom field** |
| `founded` | `founded` | Text | **Custom field** |
| `about_us` | `aboutUs` | Rich Text | **Custom field** |
| `specialties` | `specialties` | Text | **Custom field** |

### PostEngagementUser -> Twenty People + Notes

| LinkedIn Scraper Field | Twenty CRM Field | Notes |
|---|---|---|
| `name` (split) | `name.firstName` / `name.lastName` | |
| `headline` | `jobTitle` | |
| `profile_url` | `linkedinUrl` (custom) | |
| `engagement_type` | — | Added as a **Note**: "Reacted to {company} post" |

---

## Custom Fields Setup

Run the setup script after Twenty CRM is running:

```bash
python crm/setup_fields.py --url https://your-crm.com --key YOUR_API_KEY
```

This creates all required custom fields on People and Companies objects. The script is idempotent.

See the script source for the full field list, or create them manually in **Settings -> Data Model**.

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
    "name": { "firstName": "Satya", "lastName": "Nadella" },
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
  -d '{ "company": { "connect": "<company-id>" } }'
```

### Search for Existing Person (dedup)

```bash
curl "https://your-crm.com/rest/people?filter=linkedinUrl[eq]=https://linkedin.com/in/satyanadella/" \
  -H "Authorization: Bearer $API_KEY"
```

---

## Sync Flow

```
Scrape completes
  |
  v
Map LinkedIn model -> Twenty fields
  |
  v
Search Twenty for existing record (by linkedinUrl)
  |
  v
Found? -> PATCH (update)    Not found? -> POST (create)
  |
  v
If Person has company -> Find/create Company -> Link
  |
  v
If PostEngagementUser -> Create Person + add Note
  |
  v
Mark scrape_result as synced
```

---

## Relationships in Twenty

```
+----------------+       +-----------------+
|    People      |------>|   Companies     |
|                | works |                 |
| firstName      |  at   | name            |
| lastName       |       | domainName      |
| jobTitle       |       | linkedinUrl*    |
| linkedinUrl*   |       | industry*       |
| intro*         |       | aboutUs*        |
| openToWork*    |       | founded*        |
+-------+--------+       +-----------------+
        |
        | has
        v
+----------------+
|    Notes       |
|                |
| body           |  "Reacted to {company} post"
| personId       |
+----------------+

* = custom field
```

---

## File Structure

```
crm/
+-- docker-compose.yml       # Production: AWS RDS + S3 (no local DB)
+-- docker-compose.local.yml # Development: bundled PostgreSQL + Redis
+-- .env.example             # Environment template with all variables
+-- setup_fields.py          # Create custom fields via Twenty API
+-- README.md                # This file
```

---

## Troubleshooting

### Cannot connect to RDS
- Verify security group allows inbound 5432 from your app server
- Check RDS is in the same VPC or has VPC peering
- Test: `psql -h your-rds-endpoint -U twenty -d twenty`

### S3 permission denied
- Verify IAM user has `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` on the bucket
- Check `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`
- Test: `aws s3 ls s3://your-bucket --profile twenty-crm`

### Twenty CRM won't start
- Check logs: `docker compose logs twenty-server`
- Ensure `APP_SECRET` is set
- Verify database URL is correct: `PG_DATABASE_URL` should resolve

### API returns 401
- API key may have expired — regenerate in Settings -> API & Webhooks
- Verify `Authorization: Bearer` header

### ElastiCache connection refused
- Security group must allow 6379 from app server
- `REDIS_URL` format: `redis://endpoint:6379` (no password by default)
- If using auth token: `redis://:authtoken@endpoint:6379`

### SSL/HTTPS
- Use nginx or caddy as reverse proxy with Let's Encrypt
- Twenty requires HTTPS for clipboard and some browser features
