# Architecture — Letter for Later

## System Overview

Letter for Later is a Flask/PostgreSQL SaaS application with a server-rendered frontend, cron-based data pipelines, and third-party integrations for payments, storage, and email.

```
                        ┌─────────────────────────────────────────────────────┐
                        │                 USER BROWSER                        │
                        └──────────────────────┬──────────────────────────────┘
                                               │ HTTPS
                               ┌───────────────▼───────────────┐
                               │          Cloudflare            │
                               │  (DDoS, Turnstile CAPTCHA,    │
                               │   SSL termination)            │
                               └───────────────┬───────────────┘
                                               │
                               ┌───────────────▼───────────────┐
                               │     VPS — Gunicorn (4 workers) │
                               │     Flask Application          │
                               │     WhiteNoise (static files)  │
                               └───┬───────────────────┬────────┘
                                   │                   │
               ┌───────────────────▼──┐     ┌──────────▼────────────┐
               │   PostgreSQL 14       │     │       AWS S3           │
               │  (primary datastore)  │     │   (media attachments)  │
               │  JSONB, GIN indexes   │     │   (pre-signed URLs)    │
               └───────────────────────┘     └────────────────────────┘
                                   │
                   ┌───────────────▼───────────────────┐
                   │           Cron Jobs                │
                   │   send_scheduled_letters.py        │  every 15 min
                   │   cleanup_expired_media.py         │  daily
                   └────────────────────────────────────┘
                                   │
                   ┌───────────────▼───────────────────┐
                   │     External Services              │
                   │   Stripe    — payments/webhooks    │
                   │   Zoho SMTP — transactional email  │
                   │   Google    — OAuth 2.0            │
                   └────────────────────────────────────┘
```

---

## Application Package Structure

The Flask application uses a **factory pattern** (`create_app()` in `website/__init__.py`) with Flask extensions registered at startup:

```
website/
├── __init__.py          # App factory — registers db, login_manager, mail, blueprints
├── models.py            # SQLAlchemy ORM (11 models)
├── views.py             # Core feature routes (letter CRUD, dashboard, settings)
├── auth.py              # Auth routes (register, login, 2FA, Google OAuth, password reset)
├── encryption.py        # Fernet encrypt/decrypt utilities
├── spam_detection.py    # Multi-signal signup confidence classifier
├── email_service.py     # Email composition and transactional delivery
├── email_rate_limit.py  # Per-user and per-IP email sending rate limits
├── email_validation.py  # MX record + syntax validation
├── s3_config.py         # AWS S3 client and bucket config
├── s3_media_handler.py  # Upload pipeline: resize → thumbnail → S3 → signed URL
├── blocking.py          # IP blocking middleware (checks BlockedIP table per request)
├── plan_utils.py        # Subscription plan feature gating
├── stripe_routes.py     # Stripe checkout session creation
├── webhook_handler.py   # Stripe event → DB state machine
├── sitemap_config.py    # Dynamic XML sitemap generation
└── auto_sitemap.py      # Sitemap auto-refresh on route changes
```

---

## Data Model

### Entity Relationships

```
User ─────────────────────────────────────────────────────────────────────┐
 │                                                                         │
 ├──< Letter                                                               │
 │      ├── (title, content) encrypted with Fernet AES-128               │
 │      ├──< MediaAttachment  ──→  S3 object                              │
 │      └──< RecipientInvite  (tracks delivery + follow-up reminders)     │
 │                                                                         │
 ├──< TrustedContact                                                       │
 │      └── (confirmed) ──→ DeathVerification ──< DeathVerificationConfirmation
 │                                                                         │
 ├──< Notification                                                         │
 ├──< Payment                (Stripe payment ledger)                      │
 └── (optionally) NewsletterSubscriber                                    │
                                                                           │
BlockedIP   (admin-managed, checked per-request by blocking.py) ──────────┘
```

### Key Model Details

| Model | Notable Fields | Index Strategy |
|---|---|---|
| `User` | `plan`, `subscription_status`, `two_factor_secret`, `backup_codes (JSONB)`, `registration_ip` | `email`, `is_active` |
| `Letter` | `content` (encrypted), `delivery_type`, `scheduled_date`, `is_encrypted`, `media_attachments (JSONB)` | `user_id + status`, `scheduled_date` |
| `TrustedContact` | `is_confirmed`, `confirmation_code`, `death_confirmation_cooldown_until` | `user_id`, `email` |
| `DeathVerification` | `confirmations_count`, `status` (state machine), `verification_code` | `status`, `verification_code` |
| `BlogPost` | `tags (JSONB)`, `meta_title`, `focus_keyword` | GIN on `tags`, `status + published_at` |
| `MediaAttachment` | `file_type`, `s3_bucket`, `s3_etag`, `thumbnail_path` | composite `user_id + letter_id` |

---

## Core Data Flows

### 1. Letter Creation & Encryption

```
POST /create-letter
    │
    ├── Validate rich-text content (bleach sanitise)
    ├── Save Letter to DB (status=draft, is_encrypted=False)
    ├── Upload media files → s3_media_handler.py
    │       ├── Resize images (Pillow)
    │       ├── Generate video thumbnails (OpenCV / MoviePy)
    │       └── boto3.upload_fileobj() → S3
    ├── letter.encrypt_fields()          ← Fernet encrypt title + content
    │       ├── encrypt_text(title) → base64 token
    │       ├── is_encrypted_text(token) → verify
    │       └── db.session.commit()
    └── Return dashboard redirect
```

### 2. Death Verification Workflow

```
TrustedContact clicks "Confirm Death"
    │
    ├── Check cooldown period (7-day cooldown enforced)
    ├── Create / increment DeathVerification record
    ├── If confirmations_count >= threshold (e.g. 2):
    │       ├── Notify main user: "Do you want to challenge this?"
    │       ├── 48-hour window for user to deny
    │       └── If not denied → status = 'verified'
    │
    └── Cron: send_scheduled_letters.py
            ├── Query Letters WHERE user has verified death
            ├── letter.decrypt_fields()
            ├── Send via SMTP with media URLs (S3 signed, 10-min TTL)
            └── Update letter.status = 'delivered'
```

### 3. Spam Detection Pipeline

```
POST /sign-up
    │
    └── detect_spam_pattern(email, first_name, last_name, ip)
            │
            ├── is_random_email(email)        → +50 confidence
            │     ├── Disposable domain list
            │     ├── Regex: random character patterns
            │     └── Vowel ratio < 20% + consonant run > 5
            │
            ├── is_random_name(first/last)    → +30 each
            │     ├── Vowel ratio < 25%
            │     └── Consonant run > 4
            │
            ├── check_recent_spam_activity(ip)  → +100 (override)
            │     ├── ≥3 signups from exact IP in 30 min
            │     └── ≥3 signups from /24 subnet in 30 min
            │
            ├── check_aws_ip_range(ip)          → +10 (combined)
            │
            ├── Cross-IP email clustering       → +40
            │     └── Same email prefix from ≥2 different IPs in 1hr
            │
            └── check_timing_pattern(ip)        → +60
                    └── Bot-interval detection (4-6 min regular spacing)

            confidence >= 80 → REJECT signup
```

### 4. Stripe Subscription Lifecycle

```
User clicks "Upgrade"
    │
    ├── stripe_routes.py: create checkout session
    └── Redirect to Stripe hosted checkout
            │
            └── Stripe sends webhook → webhook_handler.py
                    ├── checkout.session.completed  → set plan='premium', subscription_id
                    ├── invoice.paid               → update next_payment_date
                    ├── customer.subscription.updated → sync status, cancel_at
                    └── customer.subscription.deleted → downgrade to 'free'
```

---

## Security Model

| Threat | Mitigation |
|---|---|
| Data breach exposes letters | Fernet encryption at rest — ciphertext useless without ENCRYPTION_KEY |
| Brute-force login | Flask-Login session management + planned rate limiting |
| Fake death confirmation | Quorum consensus + 48-hour user challenge window + cooldown |
| Spam account creation | Multi-signal classifier + Cloudflare Turnstile + IP blocklist |
| XSS in letters | `bleach` HTML sanitisation on all rich-text input |
| CSRF attacks | Flask-WTF CSRF tokens on all POST forms |
| Media hotlinking | S3 pre-signed URLs with 10-minute expiry |
| Bot signups | Cloudflare Turnstile (server-side validation) |
| Email bombing | Per-user + per-IP rate limiting in `email_rate_limit.py` |
| MX-invalid emails | DNS MX record validation before account creation |

---

## Scheduled Jobs (Cron Pipeline)

| Script | Schedule | Description |
|---|---|---|
| `send_scheduled_letters.py` | `*/15 * * * *` | Queries for due letters, decrypts, sends via SMTP |
| `cleanup_expired_media.py` | `0 2 * * *` | Removes S3 objects for deleted/cancelled letters |
| `find_spam_signups.py` | On-demand | Audits all users against spam classifier |
| `cleanup_spam_accounts.py` | On-demand | Deactivates confirmed spam accounts |
| `sync_subscriptions.py` | On-demand | Reconciles Stripe subscription state with DB |
| `update_sitemap.py` | On-deploy | Regenerates `/sitemap.xml` from Flask route registry |
| `encrypt_letters.py` | Migration | Batch-encrypts legacy plaintext letters |
| `block_ip.py` | On-demand | Admin CLI tool to add IPs to BlockedIP table |

---

## Environment Variables

All sensitive configuration is injected via environment variables. See [`env.example`](env.example) for the full list, which includes:

- Flask `SECRET_KEY` and `ENCRYPTION_KEY`
- PostgreSQL `DATABASE_URL`
- AWS credentials and bucket name
- Stripe publishable + secret keys + webhook secret
- Google OAuth client credentials
- SMTP server configuration
- Cloudflare Turnstile keys
