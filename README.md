# Music Upscaler Platform

Private technical README for the Django-based music upscaling service.

This repository contains the flagship/proprietary Django service for audio post-production: library management, upload/processing flow, playback UI, metadata handling, DSP/AI enhancement, format conversion, quality reports, and future subscription-ready product architecture.

The goal is not to compete with audio generators. The product is positioned as a post-generation and home-recording workspace: take rough audio, bad exports, low-quality MP3 files, generated tracks, demos, or home recordings and turn them into a better organized, better sounding, publish-ready or private-library-ready asset.

## Product direction

Core value:

- improve low-quality audio through DSP and, later, AI upscaling/restoration;
- manage a private/public music library;
- edit and normalize track metadata;
- compare original vs processed audio;
- prepare tracks for personal listening or legitimate publishing;
- support future karaoke/lyrics/transcription workflows;
- support future Free/Standard/Pro subscription tiers.

The app should be developed as a proprietary flagship product. A legacy Flask version may be kept as a local playground/prototype and may later become a small open-source demo if useful. The Django service is the main product line.

## Current implementation status

Current app:

- Django web application with server-rendered templates and vanilla JavaScript;
- upload modal and processing configuration flow;
- audio library with covers, track metadata and playback;
- DSP/AI processing services kept under the Django app service layer;
- original/processed comparison modal;
- generated metrics/quality report support;
- local media folders for development;
- SQLite development database for the current baseline.

Important: this project is still in active development. Some architecture sections describe the target direction, not the current implementation.

## Planned architecture

The long-term architecture roadmap is maintained here:

- `docs/ARCHITECTURE_ROADMAP.md`

That document is the source of truth for planned backend work: Docker Compose, PostgreSQL, ORM/OGM boundaries, repositories, Unit of Work, Celery workers, Redis/Channels, Kafka KRaft, CQRS-lite, ClickHouse analytics, object storage, auth/subscriptions/quotas, external drives, security, moderation, CI/CD, observability, support tooling, and ADRs.

Target direction:

```text
Frontend
  -> Django BFF / Admin / Auth
      -> PostgreSQL: transactional truth
      -> Redis: cache, websocket channel layer, locks
      -> Kafka KRaft: durable domain events
      -> ClickHouse: analytics/read models/recommendations
      -> Object storage through StorageService abstraction
      -> Celery/Python ML workers: DSP/AI/audio processing
      -> Go/Rust services later where they make sense
```

## Subscription model draft

The payment module is intentionally postponed until the product core is stable. The subscription domain should still be designed early.

Draft tiers:

- Anonymous: public-library listening only.
- Registered Free: 50 MB storage, public-only creation, MP3/DSP-only processing, no private tracks.
- Standard: 150 RUB/month, private tracks, all DSP formats, 800 DSP tracks per billing period, 200 MB storage.
- Pro: 300 RUB/month, Standard features plus AI upscaling, 2000 DSP tracks and 300 AI tracks per billing period, 400 MB storage.

Billing should start with a `FakePaymentProvider` for testing upgrade/downgrade/cancel/payment_failed flows before integrating a real payment provider.

## Security principles

The service must be designed as if user content, OAuth tokens, future payment metadata and private tracks are sensitive data.

Required direction:

- no raw SQL string interpolation;
- ORM/SQL access through repositories/services where possible;
- SQLAlchemy or similar typed SQL layer for non-Django Python services;
- Django ORM is acceptable for the Django core, but should not leak into domain/application logic;
- DB roles should be scoped per service, not shared superuser access;
- passwords must be hashed, not encrypted;
- OAuth/refresh tokens and external storage credentials must be encrypted at the application layer;
- no tokens, cookies, payment payloads or raw PII in logs;
- secure cookies, CSRF protection, session rotation and audit logs are mandatory for production;
- backups and object storage artifacts must be encrypted at rest.

## Technical stack

Current baseline:

- Python 3.10+
- Django 5
- SQLite for local development
- PyTorch / Torchaudio where AI processing is used
- Pydub / Mutagen / SoundFile-style tooling for audio and metadata tasks
- Vanilla JavaScript for current UI behavior
- `uv` for dependency management

Target additions are documented in the roadmap and should not be introduced all at once.

## Local setup

Install dependencies:

```bash
uv sync
```

Apply migrations:

```bash
uv run python manage.py migrate
```

Run development server:

```bash
uv run python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000
```

The first AI upscaling run may need to download model weights, depending on the selected pipeline.

## Project structure

```text
config/
  Django project settings and URLs.

music/
  Main Django application.

music/models.py
  Current database models. This is expected to be split later into Track, AudioAsset, ProcessingJob, AudioMetrics, subscriptions, quotas, etc.

music/views.py
  Current HTTP request handlers. Long-term goal: move business logic out of views into application services.

music/services/
  Audio processing, metrics, metadata and supporting logic.

music/static/music/
  JavaScript and CSS modules for player, upload modal, details modal and UI behavior.

music/templates/music/
  Django templates for the web UI.

legacy_flask/
  Archived/local Flask prototype. Treat as a playground/reference, not the flagship product.

media/
  Local development media storage. Production storage must go through StorageService/object storage.

docs/
  Architecture and planning documents.
```

## Development rules for AI coding agents

Before making changes:

1. Read this README.
2. Read `docs/ARCHITECTURE_ROADMAP.md`.
3. Identify whether the task is bugfix, product feature, architecture work, security work, or documentation.
4. Keep bugfix PRs small. Do not mix stabilization with Kafka/ClickHouse/storage rewrites.
5. Do not introduce new infrastructure without feature flag, fallback and clear rollback path.

When editing code:

- keep view logic thin;
- prefer service/repository boundaries for new backend code;
- keep user-facing actions idempotent where retries are possible;
- never trust frontend checks for subscription, quota, visibility, ownership or storage limits;
- do not expose internal admin capabilities through public user APIs;
- avoid raw SQL unless it is parameterized and reviewed;
- do not log tokens, cookies, raw PII or payment data;
- do not silently delete user data when quotas are exceeded;
- keep media lifecycle explicit: original, processed, cover, waveform, lyrics/transcription artifacts, temp uploads.

## Media and metadata policy

The app should support both generated audio and ordinary user audio such as home recordings or low-quality exports.

Future metadata editing should go beyond title/artist and support album, album artist, genre, date/year, track number, disc number, composer, lyricist, BPM, key, mood, language, explicit flag, label, copyright, ISRC/UPC and lyrics source.

Metadata should be split into:

- extracted metadata;
- user-edited metadata;
- normalized/display metadata;
- metadata revision history.

Writing metadata back to files should be a separate job, not a side effect of a normal edit request.

## Public library policy

The public library is a product feature, not a free file hosting loophole.

Required direction:

- anonymous users can listen only;
- registered users can create within their quota and entitlement rules;
- free user creations are public-only unless the plan changes;
- public tracks should be stream-only by default, not public download;
- publication should require rights/responsibility confirmation;
- likes/dislikes/top charts must include anti-abuse protections;
- moderation, report, takedown and appeal flows must exist before serious public launch.

## License and publication stance

This repository represents the proprietary flagship Django service unless a separate license file or explicit note says otherwise.

The legacy Flask prototype may be considered for a small open-source/local demo later, but that decision should not affect the proprietary status of the Django product.

## Current caution

Do not present this project as a tool for bypassing platform policies or hiding the origin of generated audio. The product should be framed around audio quality improvement, metadata management, private/public library workflows, and legitimate publishing preparation.
