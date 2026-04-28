# Twenty CRM — Production Setup on AWS EC2

Complete guide for deploying Twenty CRM on a fresh Ubuntu EC2 instance with AWS RDS (PostgreSQL), S3 (file storage), local Redis, Nginx + SSL, and email via Microsoft Outlook.

---

## Architecture

```
    Internet
       |
       v
 +-- Nginx (443/SSL) -----+
 |   crm.3dsurgical.com   |
 +--------+---------------+
          |
          v :3000
 +-- EC2 (Ubuntu) --------+
 |                        |
 |  twenty-server         |-----> AWS RDS (PostgreSQL 16)
 |  twenty-worker         |-----> AWS S3 (file storage)
 |  twenty-redis (local)  |
 |                        |
 +------------------------+
```

---

## Step 1: Provision AWS Resources

### 1a. EC2 Instance

- **AMI**: Ubuntu 22.04 or 24.04
- **Instance type**: `t3.medium` (4GB RAM) minimum — Twenty migrations need 2GB+
- **Storage**: 20GB gp3
- **Security group** inbound rules:

| Port | Source | Purpose |
|------|--------|---------|
| 22 | Your IP | SSH |
| 80 | 0.0.0.0/0 | HTTP (redirects to HTTPS) |
| 443 | 0.0.0.0/0 | HTTPS |

### 1b. RDS (PostgreSQL)

1. **RDS -> Create database -> PostgreSQL 16**
2. Instance: `db.t3.micro` (dev) or `db.t3.medium` (prod)
3. Master username: `postgres`
4. Password: strong, **avoid special characters** (`@`, `#`, `!`) — they break connection strings
5. Database name: `postgres`
6. VPC: same as EC2
7. Public access: **No**
8. Security group: allow **port 5432** from EC2's security group

Note the endpoint after creation (e.g. `your-instance.xxxx.ap-south-1.rds.amazonaws.com`).

### 1c. S3 Bucket

1. **S3 -> Create bucket**
2. Region: same as EC2
3. Block all public access: **Yes**
4. Create an **IAM user** with S3 access:
   - IAM -> Users -> Create user (e.g. `twenty-crm-s3`)
   - Attach inline policy:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Action": "s3:*",
         "Resource": [
           "arn:aws:s3:::YOUR-BUCKET-NAME",
           "arn:aws:s3:::YOUR-BUCKET-NAME/*"
         ]
       }]
     }
     ```
   - Create **Access Key** -> save both keys

### 1d. DNS

Add an A record pointing your domain to the EC2 public IP:

```
crm.yourdomain.com  ->  <EC2 public IP>
```

---

## Step 2: EC2 Server Setup

SSH into your EC2 instance and run:

### 2a. System update + swap

```bash
sudo apt update && sudo apt upgrade -y

# Add swap (needed for Twenty migrations)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2b. Install Docker

```bash
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

Verify: `docker --version && docker compose version`

### 2c. Install Nginx + Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2d. Configure Nginx reverse proxy

```bash
sudo nano /etc/nginx/sites-available/twenty-crm
```

Paste:

```nginx
server {
    listen 80;
    server_name crm.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/twenty-crm /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 2e. SSL certificate

```bash
sudo certbot --nginx -d crm.yourdomain.com
```

Follow prompts. Verify auto-renewal: `sudo certbot renew --dry-run`

---

## Step 3: Deploy Twenty CRM

### 3a. Get the files

```bash
cd ~
git clone <your-repo-url>
cd linkedin_scraper/crm
```

Or just create the files manually — you need `docker-compose.yml` and `.env`.

### 3b. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Fill in all values:

```env
# Core
APP_SECRET=<generate with: openssl rand -base64 32>
SERVER_URL=https://crm.yourdomain.com

# AWS RDS
RDS_HOST=your-instance.xxxx.ap-south-1.rds.amazonaws.com
RDS_PORT=5432
RDS_DATABASE=postgres
RDS_USERNAME=postgres
RDS_PASSWORD=your-rds-password

# AWS S3
AWS_REGION=ap-south-1
S3_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# Redis (local container)
REDIS_URL=redis://twenty-redis-local:6379

# Email (Microsoft Outlook)
EMAIL_DRIVER=smtp
EMAIL_SMTP_HOST=smtp.office365.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=your@company.com
EMAIL_SMTP_PASSWORD=your-app-password

# Security (add AFTER creating your admin account)
# IS_MULTIWORKSPACE_ENABLED=false
# IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true
# LOGIC_FUNCTION_TYPE=DISABLED
# CODE_INTERPRETER_TYPE=DISABLED
```

### 3c. Start Twenty CRM

```bash
docker compose up -d
docker compose logs -f twenty-server
```

First startup takes 3-10 minutes (database migrations). Wait until you see:

```
[NestApplication] Nest application successfully started
```

### 3d. Create admin account

1. Open `https://crm.yourdomain.com`
2. Sign up with your email and password
3. Complete the onboarding wizard

### 3e. Lock down signups

After your admin account is created, uncomment the security lines in `.env`:

```env
IS_MULTIWORKSPACE_ENABLED=false
IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true
LOGIC_FUNCTION_TYPE=DISABLED
CODE_INTERPRETER_TYPE=DISABLED
```

Restart:

```bash
docker compose down
docker compose up -d
```

### 3f. Enable 2FA

1. Log into Twenty CRM
2. Go to **Settings -> Accounts -> Security**
3. Enable **Two-Factor Authentication**
4. Scan QR code with your authenticator app

### 3g. Generate API key (for scraper integration)

1. Go to **Settings -> API & Webhooks**
2. Click **Create Key**
3. Save the key

### 3h. Create custom fields

From your local machine:

```bash
python crm/setup_fields.py --url https://crm.yourdomain.com --key YOUR_API_KEY
```

---

## Docker Compose — Key Modifications

The `docker-compose.yml` differs from Twenty's default in these ways:

### 1. External RDS instead of local PostgreSQL

**Default Twenty**: bundles a `twentycrm/twenty-postgres` container.

**Our config**: no database container. Connects to AWS RDS via:
```yaml
PG_DATABASE_URL=postgres://${RDS_USERNAME}:${RDS_PASSWORD}@${RDS_HOST}:${RDS_PORT}/${RDS_DATABASE}?sslmode=require
```

### 2. `NODE_TLS_REJECT_UNAUTHORIZED=0`

Required because AWS RDS uses Amazon's root CA certificate, which Node.js doesn't trust by default. This tells Node to accept the RDS SSL certificate. Safe within the same VPC.

### 3. S3 storage instead of local filesystem

**Default Twenty**: stores files on local disk.

**Our config**: uses AWS S3:
```yaml
STORAGE_TYPE=s3
STORAGE_S3_REGION=${AWS_REGION}
STORAGE_S3_NAME=${S3_BUCKET_NAME}
```

### 4. Local Redis instead of ElastiCache

**Why not ElastiCache Serverless**: ElastiCache Serverless uses Redis Cluster mode, which causes `CROSSSLOT` errors with Twenty CRM. Twenty expects standalone (non-clustered) Redis.

**Our config**: runs a simple Redis container alongside the app:
```yaml
twenty-redis-local:
  image: redis:latest
  command: redis-server --maxmemory-policy noeviction
```

If you want managed Redis, use a **non-serverless** ElastiCache node (`cache.t3.micro`) with cluster mode **disabled**.

### 5. Removed `version: "3.9"`

Docker Compose V2 treats the `version` key as obsolete. It still works but shows a warning. Can be safely removed.

---

## Email Configuration

### Microsoft Outlook / Office 365

```env
EMAIL_DRIVER=smtp
EMAIL_SMTP_HOST=smtp.office365.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=your@company.com
EMAIL_SMTP_PASSWORD=your-password-or-app-password
```

If your org has MFA, you need an **app password**:
1. Go to https://mysignins.microsoft.com/security-info
2. Add sign-in method -> App password
3. Use the generated password

### Microsoft SSO + Email/Calendar Sync (optional)

For full Microsoft integration (SSO login + Outlook sync + Calendar sync):

1. Go to **Azure Portal -> Microsoft Entra ID -> App Registrations -> New registration**
2. Name: `Twenty CRM`
3. Redirect URIs (Web):
   - `https://crm.yourdomain.com/auth/microsoft/redirect`
   - `https://crm.yourdomain.com/auth/microsoft-apis/get-access-token`
4. Certificates & secrets -> New client secret -> copy value
5. Copy Application (client) ID from overview

Add to `.env`:

```env
AUTH_MICROSOFT_ENABLED=true
AUTH_MICROSOFT_CLIENT_ID=<application-id>
AUTH_MICROSOFT_CLIENT_SECRET=<client-secret>
AUTH_MICROSOFT_CALLBACK_URL=https://crm.yourdomain.com/auth/microsoft/redirect
AUTH_MICROSOFT_APIS_CALLBACK_URL=https://crm.yourdomain.com/auth/microsoft-apis/get-access-token
MESSAGING_PROVIDER_MICROSOFT_ENABLED=true
CALENDAR_PROVIDER_MICROSOFT_ENABLED=true
```

### Gmail (alternative)

```env
EMAIL_DRIVER=smtp
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=your@gmail.com
EMAIL_SMTP_PASSWORD=<app-password>
```

---

## Security Checklist

| Setting | How | Status |
|---------|-----|--------|
| HTTPS / SSL | Certbot + Nginx | Required |
| Admin account created | Sign up on first visit | Do first |
| Signups disabled | `IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true` | After admin signup |
| 2FA enabled | Settings -> Accounts -> Security | Recommended |
| Code execution disabled | `LOGIC_FUNCTION_TYPE=DISABLED` | Recommended |
| S3 private | Block all public access on bucket | Required |
| RDS private | No public access, VPC-only | Required |
| SSH restricted | Security group: port 22 from your IP only | Required |
| App secret set | `APP_SECRET` via `openssl rand -base64 32` | Required |
| .env not in git | `.gitignore` or manual deploy | Required |

---

## Common Operations

```bash
# View logs
docker compose logs -f twenty-server
docker compose logs -f twenty-worker

# Search for errors
docker compose logs twenty-server 2>&1 | grep -i error

# Recent errors only
docker compose logs --since 5m twenty-server 2>&1 | grep -i error

# Restart
docker compose restart

# Full restart (recreate containers)
docker compose down
docker compose up -d

# Update to latest Twenty version
docker compose pull
docker compose down
docker compose up -d

# Check container status
docker compose ps

# Check resource usage
docker stats

# Check disk/memory
df -h
free -h
```

---

## Troubleshooting

### `no pg_hba.conf entry ... no encryption`
RDS requires SSL. Ensure `?sslmode=require` is in the `PG_DATABASE_URL`.

### `self-signed certificate in certificate chain`
Add `NODE_TLS_REJECT_UNAUTHORIZED=0` to both server and worker environment sections.

### `CROSSSLOT Keys in request don't hash to the same slot`
You're using Redis Cluster (ElastiCache Serverless). Switch to local Redis or a non-clustered ElastiCache node.

### Migrations stuck / server silent for 10+ minutes
- Check RAM: `free -h` — need 2GB+ free
- Add swap if needed: `sudo fallocate -l 2G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`
- Check if process is alive: `docker exec twenty-server ps aux`
- Check DB connection: `docker exec twenty-server netstat -an | grep 5432`

### `relation "core.keyValuePair" does not exist`
Migrations didn't complete (likely interrupted). Reset the database:
```bash
PGPASSWORD='your-password' psql -h your-rds-host -U postgres -d postgres -c "
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
"
docker compose down
docker compose up -d
```

### S3 `AccessDenied`
IAM user missing permissions. Add an inline policy with `s3:*` on your bucket (see Step 1c).

### `bash: !...: event not found`
Bash interprets `!` in passwords. Use `PGPASSWORD='...'` as a separate env var instead of embedding in the URL.

### Server keeps restarting
Check `docker compose logs --tail 50 twenty-server` for the actual error. Common causes:
- RDS not reachable (security group)
- Redis not reachable (wrong URL)
- S3 permissions denied (IAM policy)
- Out of memory (need swap or bigger instance)

---

## File Structure

```
crm/
+-- docker-compose.yml       # Production: RDS + S3 + local Redis
+-- docker-compose.local.yml # Development: bundled PostgreSQL + Redis
+-- .env.example             # Environment template (no real credentials)
+-- setup_fields.py          # Create custom fields via Twenty API
+-- README.md                # This file
```

---

## LinkedIn Scraper Integration

See the data model mapping and sync flow documentation in the sections below.

### Data Model: LinkedIn -> Twenty CRM

| LinkedIn | Twenty Object | Twenty Field | Notes |
|----------|--------------|--------------|-------|
| Person.name | People | name.firstName / lastName | Split on first space |
| Person.linkedin_url | People | linkedinUrl* | Custom field, used for dedup |
| Person.location | People | city | |
| Person.about | People | intro* | Custom field |
| Person.experiences[0].position_title | People | jobTitle | |
| Person.contacts[email] | People | emails.primaryEmail | |
| Company.name | Companies | name | |
| Company.website | Companies | domainName | |
| Company.linkedin_url | Companies | linkedinUrl* | Custom field |
| Company.industry | Companies | industry* | Custom field |
| PostEngagementUser.name | People | name.firstName / lastName | |
| PostEngagementUser.headline | People | jobTitle | |
| PostEngagementUser.engagement_type | Notes | body | "Reacted to {company} post" |

*Custom fields — created by `setup_fields.py`.

### Sync Flow

```
Scrape completes
  -> Map to Twenty fields
  -> Search by linkedinUrl (dedup)
  -> Found? PATCH : POST
  -> Link Person to Company
  -> Add engagement Note if applicable
  -> Mark as synced
```
