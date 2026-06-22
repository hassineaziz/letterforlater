<div align="center">

# 📬 Legacy Letter — *Letters That Outlive You*

**A production Flask/Python SaaS application** for writing encrypted letters to be delivered after death verification.

[![Live Product](https://img.shields.io/badge/Live%20Product-letterforlater.com-brightgreen?style=for-the-badge)](https://letterforlater.com)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3-black?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue?style=for-the-badge&logo=postgresql)](https://postgresql.org)
[![AWS S3](https://img.shields.io/badge/AWS-S3%20%7C%20IAM-orange?style=for-the-badge&logo=amazonaws)](https://aws.amazon.com)

</div>

---

## What It Does

Legacy Letter lets users compose personal letters—to family, friends, or themselves—and schedule them to be delivered at a specific future date **or** only after a verified death event. The platform handles:

- **Secure writing** — rich-text editor with media uploads (images, video, audio)
- **Encryption at rest** — letter content encrypted with Fernet (AES-128-CBC) before hitting the database
- **Death verification** — trusted contacts are notified and must reach a consensus quorum before letters are released
- **Scheduled delivery** — cron-driven delivery engine sends letters via transactional email
- **Subscription tiers** — free / premium / lifetime, managed through Stripe with webhook-driven state sync

> **This is a real, deployed application** at [letterforlater.com](https://letterforlater.com) with paying users.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                    ┌────────▼────────┐
                    │   Cloudflare    │  (Bot protection, Turnstile)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Gunicorn/Flask │  (4 workers, whitenoise static)
                    │  + Blueprints   │
                    └────┬───────┬────┘
                         │       │
           ┌─────────────▼─┐   ┌─▼──────────────┐
           │  PostgreSQL   │   │    AWS S3        │
           │  (JSONB cols) │   │  (media files,  │
           │  + indexes    │   │   signed URLs)  │
           └───────────────┘   └────────────────┘
                         │
              ┌──────────▼──────────┐
              │   Cron Scheduler    │
              │  send_scheduled.py  │  ← runs every 15 min
              │  cleanup_media.py   │  ← runs daily
              └─────────────────────┘
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full data-flow diagram and security model.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | Flask 2.3 + Blueprints | Lightweight, explicit routing |
| **Database** | PostgreSQL 14 + SQLAlchemy 2.0 | JSONB for flexible schema, GIN indexes |
| **ORM / Migrations** | Flask-SQLAlchemy + Flask-Migrate | Alembic-backed schema versioning |
| **Encryption** | `cryptography` — Fernet (AES-128) | Authenticated symmetric encryption for letter content |
| **Auth** | Flask-Login + PyOTP (TOTP) | Session auth + software 2FA |
| **OAuth** | Google OAuth 2.0 | One-click sign-in |
| **Email** | Flask-Mail (Zoho SMTP) | Transactional delivery |
| **Payments** | Stripe (subscriptions + webhooks) | Lifecycle management via events |
| **Storage** | AWS S3 + boto3 | Scalable object storage with pre-signed URLs |
| **Media** | Pillow, OpenCV, MoviePy | Server-side image resize, video thumbnail generation |
| **Frontend** | Jinja2 + Tailwind CSS | Server-rendered, minimal JS |
| **Server** | Gunicorn + WhiteNoise | Production WSGI, static file serving |
| **Bot Protection** | Cloudflare Turnstile | Challenge-based CAPTCHA-free protection |

---

## Key Engineering Highlights

### 🔐 Encryption at Rest
Letter titles and content are encrypted with **Fernet symmetric encryption** before database writes. The system performs atomic encrypt-then-verify, falling back gracefully if the key is misconfigured, and exposes both `encrypt_fields()` / `decrypt_fields()` model methods and read-only `@property` decryptors for safe in-template access.

```python
# Atomic encrypt-then-verify pattern (website/models.py)
encrypted_title = encrypt_text(self.title)
if not is_encrypted_text(encrypted_title):
    self.is_encrypted = False
    return False  # non-blocking — letter saved unencrypted, error logged
```

### 🤖 Algorithmic Spam Detection (`website/spam_detection.py`)
A **confidence-scoring classification pipeline** that scores signup attempts across multiple independent signals — similar in structure to a hand-engineered feature ensemble:

| Signal | Weight |
|---|---|
| Disposable/random email pattern | +50 |
| Random-looking first/last name (vowel ratio + consonant sequences) | +30 each |
| IP rate limiting (≥3 signups / 30 min from same IP or subnet) | +100 |
| AWS/datacenter IP range detection | +10 (combined only) |
| Cross-IP email pattern clustering | +40 |
| Temporal pattern analysis (regular bot timing intervals) | +60 |

Signups scoring **≥ 80** are flagged as spam. The system also performs **subnet-level rate limiting** (`192.168.1.*`) to catch VPN-rotating bots.

```python
def detect_spam_pattern(email, first_name, last_name, registration_ip):
    """Returns (is_spam: bool, reason: str, confidence: int)"""
```

### 📬 Death Verification Workflow
A distributed **consensus protocol** where multiple trusted contacts must independently confirm a death before letters are released. Includes:
- Cooldown enforcement to prevent repeat confirmations
- Status machine: `pending → verified / rejected / denied`
- Main user can challenge and cancel a verification in progress

### 📊 PostgreSQL JSONB & Indexing Strategy
- `JSONB` columns for media attachments, notification prefs, and blog tags
- **GIN index** on blog post tags for fast `@>` containment queries
- Composite indexes on high-traffic filter patterns (`user_id + status`, `status + published_at`)

### ⏰ Data Pipeline / Cron Jobs
Real-world scheduled data pipelines running in production:

| Script | Cadence | What it does |
|---|---|---|
| `send_scheduled_letters.py` | Every 15 min | Checks DB for due letters, sends via SMTP |
| `cleanup_expired_media.py` | Daily 2 AM | Removes orphaned S3 objects |
| `sync_subscriptions.py` | On demand | Reconciles Stripe subscription state with DB |
| `update_sitemap.py` | On deploy | Regenerates XML sitemap from live routes |
| `find_spam_signups.py` | On demand | Audits existing users for spam patterns |
| `encrypt_letters.py` | Migration | Batch-encrypts unencrypted legacy letters |

---

## Project Structure

```
legacy-letter/
├── main.py                     # App entry point
├── wsgi.py                     # Gunicorn WSGI binding
├── requirements.txt            # Pinned dependencies
├── env.example                 # Environment variable template
│
├── website/                    # Main application package
│   ├── __init__.py             # App factory, extensions init
│   ├── models.py               # SQLAlchemy ORM models (11 models)
│   ├── views.py                # Core routes (~3k lines, feature-rich)
│   ├── auth.py                 # Auth routes: login, register, 2FA, OAuth
│   ├── encryption.py           # Fernet encrypt/decrypt utilities
│   ├── spam_detection.py       # Multi-signal signup classifier
│   ├── email_service.py        # Transactional email composition + delivery
│   ├── email_rate_limit.py     # Per-user/IP email rate limiting
│   ├── email_validation.py     # MX record + syntax validation
│   ├── s3_config.py            # AWS S3 client configuration
│   ├── s3_media_handler.py     # Upload, resize, thumbnail, signed URLs
│   ├── blocking.py             # IP blocking middleware
│   ├── plan_utils.py           # Subscription plan enforcement
│   ├── stripe_routes.py        # Stripe checkout + webhook handler
│   ├── webhook_handler.py      # Stripe event processing
│   ├── sitemap_config.py       # Dynamic sitemap generation
│   └── templates/              # Jinja2 HTML templates
│
├── send_scheduled_letters.py   # Cron: deliver due letters
├── cleanup_expired_media.py    # Cron: purge orphaned S3 files
├── encrypt_letters.py          # Migration: batch encrypt legacy letters
├── find_spam_signups.py        # Audit: flag suspicious accounts
├── cleanup_spam_accounts.py    # Admin: remove confirmed spam
├── sync_subscriptions.py       # Reconcile Stripe ↔ DB state
└── migrations/                 # Alembic migration history
```

---

## Data Model (Simplified)

```
User ──< Letter ──< MediaAttachment (S3)
  │          └──< RecipientInvite
  │
  ├──< TrustedContact
  │         └── (confirms) ──> DeathVerification
  │                               └──< DeathVerificationConfirmation
  ├──< Notification
  ├──< Payment
  └── NewsletterSubscriber
```

---

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 14+
- AWS S3 bucket
- Stripe account (for payment features)

### Installation

```bash
# 1. Clone and set up virtual environment
git clone https://github.com/hassineaziz/letterforlater.git
cd letterforlater
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp env.example .env
# Edit .env with your credentials (see env.example for all required vars)

# 4. Set up database
flask db upgrade

# 5. Run development server
flask run
```

### Production Deployment

```bash
# Gunicorn with 4 workers
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 120 main:app
```

### Cron Setup

```cron
# Send scheduled letters every 15 minutes
*/15 * * * * cd /path/to/app && /path/to/venv/bin/python send_scheduled_letters.py >> /var/log/app/cron.log 2>&1

# Cleanup orphaned media daily
0 2 * * * cd /path/to/app && /path/to/venv/bin/python cleanup_expired_media.py >> /var/log/app/cleanup.log 2>&1
```

---

## Security

- **Encryption at rest** — Fernet AES-128 for all letter content
- **2FA** — TOTP-based software authenticator support
- **Input sanitisation** — `bleach` library for rich-text content
- **CSRF protection** — Flask-WTF tokens on all state-changing forms
- **Bot protection** — Cloudflare Turnstile + server-side spam classifier
- **IP blocking** — Admin-managed blocklist with subnet awareness
- **Signed URLs** — Time-limited S3 pre-signed URLs (10-minute expiry) for media access
- **Password resets** — Single-use tokenised reset links with expiry

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE)
