# Architecture Roadmap

Документ фиксирует целевую дорожную карту развития backend-архитектуры проекта. Это не runtime-изменение и не обязательство внедрить всё одним PR. Цель — заранее заложить границы модулей, транзакции, безопасность, подписки, realtime, storage, ML inference и будущий мультиязычный стек так, чтобы дальнейшее развитие не требовало переписывания ядра.

## Базовые принципы

- PostgreSQL остаётся transactional source of truth.
- Django постепенно становится BFF/API/Admin/Auth orchestration layer.
- Python остаётся основным runtime для ML/DSP/audio workers.
- Go/Rust рассматриваются для отдельных сервисов, где есть смысл: media gateway, realtime gateway, Kafka consumers, hot path audio tooling.
- Kafka используется как durable event backbone в KRaft mode, без ZooKeeper.
- ClickHouse используется для аналитики, recommendations features и read-heavy событийных данных, а не как основная transactional DB.
- Docker Compose становится основным dev/stage способом развёртывания.
- Kubernetes/Swarm не внедряются сразу, но код проектируется multi-instance safe.
- MinIO не используется как основной self-hosted storage из-за лицензионных рисков; storage закрывается через `StorageService` abstraction.
- Любые новые механизмы включаются постепенно через feature flags и rollback path.

## Целевая схема

```text
Frontend
  -> Django BFF / Admin / Auth
      -> PostgreSQL: transactional truth
      -> Redis: cache, websocket channel layer, locks
      -> Kafka KRaft: durable domain events
      -> ClickHouse: analytics/read models/recommendations
      -> Object storage: SeaweedFS/Ceph/S3-compatible backend through StorageService
      -> Celery/Python ML workers: DSP/AI/audio processing
      -> Go/Rust services: media/realtime/consumers/hot path tooling
```

## Phase 0 — Stabilization baseline

- [ ] Держать bugfix PR отдельно от архитектурных PR.
- [ ] После стабилизации upload/delete/player/details modal начинать архитектурную ветку отдельно.
- [ ] Не смешивать Kafka/ClickHouse/CQRS/Storage rewrite с мелкими UI bugfix.

## Phase 1 — Docker Compose как основной способ развёртывания

- [ ] Сделать Docker Compose основным dev/stage deployment path.
- [ ] Вынести настройки окружения в `.env` и settings split: local, docker, staging, production-like.
- [ ] Подготовить compose-сервисы: `web`, `postgres`, `redis`, `worker`, `beat`, `nginx`.
- [ ] Позже добавить compose-сервисы: `kafka` в KRaft mode, `clickhouse`, object storage, observability.
- [ ] Kubernetes/Swarm пока не вводить, но проектировать сервисы так, чтобы они пережили горизонтальное масштабирование.

## Phase 2 — Modular Django Core и типизация

- [ ] Разделить текущий Django-монолит по пакетам: `domain`, `application`, `infrastructure`, `interfaces`, `ml`.
- [ ] Ввести typed DTO/command/query/event объекты.
- [ ] Подключить `ruff` и `pyright` или `mypy`.
- [ ] Вынести прямую работу с файлами за `StorageService` abstraction.
- [ ] Подготовить границы будущих сервисов без преждевременного физического распила.

## Phase 3 — PostgreSQL и новая доменная модель

- [ ] Перейти с SQLite на PostgreSQL как основную transactional DB.
- [ ] Разделить сущности `Track`, `AudioAsset`, `ProcessingJob`, `AudioMetrics`.
- [ ] Хранить параметры DSP/AI/metrics в `jsonb`, а не размазывать их по случайным полям.
- [ ] Добавить `UsageLedger`/quota-ready поля под Free/Standard/Pro модель.
- [ ] Подготовить миграцию старых данных из текущей модели `Track`.

## Phase 3.5 — Persistence layer: ORM/OGM, repositories и Unit of Work

- [ ] PostgreSQL остаётся transactional source of truth; ORM/OGM не должен протекать напрямую в `domain`/`application` слой.
- [ ] На первом этапе использовать Django ORM для основного ядра, но закрыть доступ к данным через repositories/services.
- [ ] Для non-Django Python services заложить SQLAlchemy 2.x или аналогичный typed SQL layer.
- [ ] Для Go/Rust выбирать persistence stack по сервису: Go `sqlc`/`ent`/`bun`/`gorm`, Rust `sqlx`/`SeaORM`/`Diesel`.
- [ ] Ввести Unit of Work и явные transaction boundaries для upload commit/cancel, process start, metadata update, subscription change, billing webhook, outbox publish.
- [ ] Определить aggregate boundaries: `Track`, `AudioAsset`, `ProcessingJob`, `Subscription`, `UsageLedger`.
- [ ] Не вводить distributed transactions между сервисами; использовать Outbox/Inbox, idempotency, saga/compensation flows.
- [ ] OGM рассматривать только для отдельного graph/document read-model слоя: recommendations, metadata graph, knowledge graph.
- [ ] Если появится graph DB/document DB, доступ к ней вести через adapter/repository, чтобы доменная логика не зависела от конкретной OGM-библиотеки.
- [ ] Схемы и миграции держать явными: Django migrations/Alembic/Goose/Atlas/SeaORM migrations по сервисам, с владельцем схемы и rollback policy.
- [ ] Добавить tests на transaction rollback, repeated event delivery, duplicate idempotency key и version conflict.

## Phase 4 — Workers и тяжёлая обработка

- [ ] Заменить `threading.Thread` на Celery workers.
- [ ] Разнести очереди: `default`, `standard`, `pro`, `heavy_ai`, `waveform`, `metadata`, `cleanup`.
- [ ] Добавить retry/cancel/manual retry для processing jobs.
- [ ] Добавить scheduled cleanup для pending/temp uploads.
- [ ] Python оставить основным runtime для ML/DSP/audio processing пайплайнов.

## Phase 5 — Realtime statuses без polling

- [ ] Добавить Django Channels + Redis channel layer.
- [ ] Перевести статусы processing/upload/delete/library updates на WebSocket-события.
- [ ] Оставить polling только как fallback, а не как основной механизм.
- [ ] События статусов строить поверх текущего состояния в PostgreSQL, чтобы refresh страницы всегда восстанавливал корректную картину.

## Phase 6 — Kafka + CQRS-lite

- [ ] Ввести `OutboxEvent` в PostgreSQL перед физическим подключением Kafka.
- [ ] Добавить `InboxEvent`/idempotency для consumers.
- [ ] Использовать Kafka в KRaft mode, без ZooKeeper.
- [ ] Завести топики: `music.track.events`, `music.processing.events`, `music.playback.events`, `music.user.events`, `music.subscription.events`, `music.billing.events`.
- [ ] Ввести единый event envelope: `event_id`, `event_type`, `version`, `occurred_at`, `aggregate_id`, `user_id`, `correlation_id`, `causation_id`, `payload`.
- [ ] Использовать CQRS-lite: PostgreSQL как write model/source of truth, projections/read models для UI, аналитики и рекомендаций.
- [ ] Не делать полный event sourcing на первом этапе, пока нет реальной необходимости.

## Phase 7 — ClickHouse analytics

- [ ] Подключить ClickHouse как OLAP-хранилище событий и аналитики.
- [ ] Написать Kafka -> ClickHouse consumers.
- [ ] Начать с таблиц: `playback_events`, `processing_events`, `track_events`, `subscription_events`, `search_events`, `recommendation_feedback_events`.
- [ ] Использовать ClickHouse для дашбордов, retention, skip-rate, completion-rate, Free/Standard/Pro analytics и future recommendation features.

## Phase 8 — Object storage без MinIO

- [ ] Не закладывать MinIO как основной self-hosted storage из-за лицензионных рисков для коммерческого сценария.
- [ ] Рассмотреть SeaweedFS как первый S3-compatible вариант для dev/stage/self-hosted.
- [ ] Держать Ceph как более тяжёлый production-вариант на будущее.
- [ ] Все storage operations выполнять через `StorageService`, чтобы заменить backend хранения без переписывания доменной логики.
- [ ] Предусмотреть signed URLs, checksums, deduplication, retention policy и cleanup failed artifacts.
- [ ] Не полагаться на локальную файловую систему контейнера для постоянных медиафайлов.

## Phase 9 — Multilingual service-ready stack

- [ ] Django постепенно перевести в роль BFF/API/Admin/Auth orchestration layer.
- [ ] Python оставить для ML/audio workers.
- [ ] Go рассмотреть для `media-gateway`, upload/session service, realtime gateway, billing/webhook service, Kafka consumers.
- [ ] Rust рассмотреть для hot path: waveform/peaks, audio preprocessing, transcoding helpers, низкоуровневые безопасные утилиты.
- [ ] Контракты между сервисами описывать через OpenAPI/AsyncAPI/JSON Schema или Protobuf, а не неявными JSON-структурами.

## Phase 10 — Race conditions и readiness к Swarm/Kubernetes

- [ ] Проектировать код как multi-instance safe, даже если deployment пока остаётся на Docker Compose.
- [ ] Все критичные операции делать идемпотентными: upload commit/cancel, process start, delete, billing webhook, event publish.
- [ ] Использовать optimistic locking/version fields для `Track`, `AudioAsset`, `ProcessingJob`.
- [ ] Использовать PostgreSQL transactions, row-level locking/advisory locks там, где возможно двойное выполнение.
- [ ] Для distributed locks использовать Redis только там, где это действительно нужно, с TTL и безопасным release.
- [ ] Ввести unique constraints для защиты от дублей: asset checksum, idempotency key, event id, external payment event id.
- [ ] Для Kafka consumers предусмотреть at-least-once delivery: idempotent handlers, inbox table, retry и DLQ.
- [ ] Не хранить критичное состояние только в памяти контейнера; всё состояние должно восстанавливаться из PostgreSQL/Kafka/object storage.
- [ ] Предусмотреть graceful shutdown для workers: не начинать новую задачу, корректно помечать running job, давать возможность retry.
- [ ] Kubernetes/Swarm вводить позже отдельным этапом, когда compose-архитектура стабилизируется.

## Phase 11 — Accounts, auth, subscriptions, quotas

### Auth model

- [ ] Anonymous users получают только read-only прослушивание публичной библиотеки.
- [ ] Upload, processing, likes/dislikes, comments и external storage доступны только после регистрации.
- [ ] Авторизацию заложить через provider adapters: Google, Yandex, VK, later password/email if needed.
- [ ] Ввести `AuthIdentity`: provider, provider_user_id, email_from_provider, avatar_url, linked_at, last_login_at.
- [ ] Разрешить привязку нескольких identity к одному user/account.
- [ ] Обрабатывать OAuth edge cases: user denied consent, token expired, token revoked, provider unavailable.

### Subscription tiers

- [ ] Registered free users получают 50 MB storage quota, public-only творчество, DSP MP3-only processing, без private tracks.
- [ ] Standard: 150 RUB/month, private творчество, все DSP-форматы, лимит 800 DSP tracks per billing period, storage quota 200 MB.
- [ ] Pro: 300 RUB/month, всё из Standard, AI upscale, 2000 DSP tracks и 300 AI tracks per billing period, storage quota 400 MB.
- [ ] Storage quota считать отдельно от monthly processing quotas.
- [ ] Ввести `Plan`, `PlanVersion`, `Subscription`, `Entitlement`, `UsageQuota`, `UsageLedger`, `QuotaReservation`.
- [ ] Разнести Free/Standard/Pro лимиты и priority queues на backend, а не только в UI.
- [ ] При downgrade приватные треки не делать публичными автоматически; старые данные сохранять, новые private uploads блокировать по entitlement.

### Billing/payment readiness

- [ ] Платёжку подключать после стабилизации core, auth, quota и processing pipeline.
- [ ] До реальной платёжки использовать `FakePaymentProvider` для тестов upgrade/downgrade/cancel/payment_failed.
- [ ] Подготовить `PaymentProviderAdapter`, `Invoice`, `PaymentIntent`, `PaymentMethod`, `PaymentWebhookEvent`, `BillingAuditLog`.
- [ ] Webhook processing делать идемпотентным через external payment event id.
- [ ] Юридический и платёжный провайдер выбирать поздним этапом после проверки актуальных требований.

## Phase 12 — Contracts, schemas, API versioning

- [ ] Ввести API versioning: `/api/v1/...`, затем `/api/v2/...` без ломающих изменений старых клиентов.
- [ ] Завести каталог контрактов: OpenAPI для HTTP, AsyncAPI для Kafka/WebSocket, JSON Schema или Protobuf для событий.
- [ ] Добавить contract tests между Django BFF, Go/Rust services, Python ML workers и Kafka consumers.
- [ ] Версионировать event schemas и явно фиксировать producers/consumers для каждого события.

## Phase 13 — Extended track metadata и ручное редактирование

- [ ] Расширить модель метаданных трека за пределы `title` и `artist`.
- [ ] Поддержать ручную правку: album, album_artist, genre, year/date, track_number, disc_number, composer, lyricist, bpm, key, mood, language, explicit flag, copyright, label, ISRC/UPC, lyrics source.
- [ ] Разделить extracted metadata, user-edited metadata и normalized/display metadata, чтобы не терять оригинальные данные файла.
- [ ] Хранить metadata revision history и источник правки: extractor, user, admin, external provider, AI.
- [ ] Предусмотреть запись метаданных обратно в файл как отдельную задачу, а не как побочный эффект простого edit endpoint.
- [ ] Добавить metadata events: `track.metadata.extracted`, `track.metadata.updated`, `track.metadata.writeback.requested`, `track.metadata.writeback.completed`.

## Phase 14 — Karaoke, lyrics и transcription pipeline

- [ ] Спроектировать отдельные сущности `LyricsDocument`, `TranscriptionJob`, `LyricSegment`, `SyllableTiming`.
- [ ] Поддержать уровни синхронизации: plain lyrics, line-level, word-level, syllable-level.
- [ ] Развести задачи: source separation/vocal isolation, ASR, forced alignment, punctuation/casing, language detection, translation/romanization.
- [ ] Исследовать два класса решений: специализированные ASR/alignment-модели для точного тайминга и мультимодальные LLM для восстановления текста/языка/пунктуации/постобработки.
- [ ] Поддержать мультиязычность и mixed-language tracks.
- [ ] Хранить confidence score на уровне строки/слова/слога и давать ручную коррекцию таймингов.
- [ ] Все karaoke/transcription jobs проводить через очереди, retry/fallback и события статусов.

## Phase 15 — ML inference serving, model routing, retries/fallbacks

- [ ] Выделить inference layer отдельно от Django BFF и обычных Celery tasks.
- [ ] Рассмотреть Triton/vLLM как слой serving/routing для нескольких моделей, чтобы не блокировать все запросы одной моделью и одной очередью.
- [ ] Ввести model registry: `model_id`, `model_version`, `weights_checksum`, runtime, device, supported tasks, quality tier.
- [ ] Добавить model routing: ASR, alignment, restoration, upscaling, embeddings, recommendations, moderation.
- [ ] Разделить очереди и resource pools по CPU/GPU/VRAM/model family.
- [ ] Добавить fallback policy: primary model -> lighter model -> external/manual fallback -> failed with actionable error.
- [ ] Добавить retry policy по типам ошибок: transient infra error, OOM, timeout, invalid input, model unavailable.
- [ ] Ввести job timeout, cancellation, priority, preemption/capacity guards для Free/Standard/Pro.
- [ ] Хранить inference attempt history, чтобы видеть, какая модель и какой fallback реально сработал.

## Phase 16 — Observability, status logging и monitoring

- [ ] Ввести structured JSON logs с `request_id`, `correlation_id`, `job_id`, `track_id`, `user_id`, `model_id`, `event_id`.
- [ ] Разделить логи по статусам и стадиям: upload, metadata, queue, processing, inference, storage, websocket, kafka, billing, recommendation.
- [ ] Добавить OpenTelemetry traces между BFF, workers, Kafka consumers, storage, ClickHouse и inference services.
- [ ] Добавить Prometheus metrics/Grafana dashboards: queue depth, job latency, model latency, GPU/CPU usage, error rate, retry rate, fallback rate, Kafka consumer lag, WebSocket connections, storage latency.
- [ ] Добавить Sentry/error tracking с fingerprinting по stage/model/error class.
- [ ] Сделать admin/ops dashboard для active/failed jobs, retry/cancel, consumer lag, storage usage, user quotas и последних ошибок.

## Phase 17 — Security, privacy, backup/restore, license policy

### SQL/ORM safety

- [ ] Запретить string interpolation для SQL; raw SQL разрешать только через параметризованные запросы, whitelist и code review.
- [ ] Добавить DB permissions by service: каждый сервис получает только нужные права, а не общий superuser-доступ.
- [ ] Добавить тесты и static checks против SQL injection, unsafe raw queries и mass-assignment уязвимостей.

### Data protection / encryption

- [ ] Пароли не шифровать, а хранить только через сильный password hashing: Argon2id/bcrypt/PBKDF2 с salt и актуальными параметрами.
- [ ] OAuth tokens, refresh tokens, payment provider identifiers, external storage tokens и другие секретные пользовательские данные хранить encrypted-at-application-layer.
- [ ] Использовать envelope encryption: data encryption key для данных, master key в secrets manager/KMS/Vault/SOPS/production secret store.
- [ ] Включить TLS everywhere: browser -> edge, edge -> app, app -> internal services, workers -> DB/object storage/Kafka where possible.
- [ ] Шифровать backups и object storage artifacts at rest; отдельно проверять restore из encrypted backup.
- [ ] Не логировать access tokens, refresh tokens, cookies, payment payloads, authorization headers и raw PII.
- [ ] Псевдонимизировать PII в ClickHouse/logs: user_id/account_id вместо email/phone/name; IP/user-agent хранить осторожно, с hash/truncation и retention policy.
- [ ] Secure cookies: HttpOnly, Secure, SameSite, session rotation after login, CSRF protection for BFF forms/API.
- [ ] Добавить RBAC/ABAC, admin MFA, audit log, rate limits, lockout/backoff для auth и sensitive operations.
- [ ] Подготовить incident response: forced token rotation, revoke all sessions, disable provider connection, quarantine suspicious uploads.

### Legal/license/backup

- [ ] Подготовить RBAC/ABAC и audit log для пользовательских и админских операций.
- [ ] Заложить delete account/export data/anonymize analytics flows.
- [ ] Ввести backup/restore policy для PostgreSQL, ClickHouse и object storage; регулярно проверять restore drill.
- [ ] Добавить dependency license scanning и SBOM: отдельно для Python, Go, Rust и frontend dependencies.
- [ ] Зафиксировать allowed/blocked licenses, чтобы не затащить AGPL/SSPL/неподходящие коммерческие ограничения случайной зависимостью.

## Phase 18 — Zero-downtime migrations и feature flags

- [ ] Принять правило миграций: expand -> backfill -> switch -> contract.
- [ ] Добавить feature flags для WebSocket statuses, Kafka events, ClickHouse analytics, new storage backend, Pro queues, new player, karaoke pipeline, inference serving.
- [ ] Новые backend-механизмы включать постепенно, с rollback path.
- [ ] Не удалять старые поля/эндпоинты до завершения backfill и переходного периода.

## Phase 19 — Storage quotas and external user-owned storage

- [ ] Storage quota считать по всем owned artifacts: original, processed, cover, waveform cache, lyrics/transcription artifacts, temporary uploads после grace period.
- [ ] При достижении quota не удалять данные молча; блокировать новые uploads/processing и показывать пользователю, что нужно освободить место или перейти на внешний storage/paid plan.
- [ ] Не давать пользователям public admin API для массового управления storage через скрипты.
- [ ] Дать возможность подключить Google/Yandex Drive как user-owned storage.
- [ ] External drive connection должен иметь явные состояния: `auth_started`, `permission_denied`, `connected`, `token_expired`, `revoked`, `sync_failed`, `disabled_by_user`.
- [ ] Если пользователь начал OAuth, но не выдал права, сохранять controlled state `permission_denied`, а не падать ошибками в sync/upload pipeline.
- [ ] Любая операция с external drive обязана проверять актуальное состояние connection и иметь graceful fallback/error message.

## Phase 20 — Public library, reactions and anti-abuse

- [ ] Для общей библиотеки ввести `TrackVisibility`, `PublicationStatus`, `download_policy`.
- [ ] Для free-пользователей публикация должна требовать подтверждение прав и ответственности.
- [ ] По умолчанию public library отдаёт stream-only, а не public download.
- [ ] Добавить likes/dislikes через `TrackReaction` с unique constraint `(track_id, user_id)`.
- [ ] Топ считать не только по лайкам, а через weighted score: likes, dislikes, completion_rate, replay_rate, age_decay, abuse_penalty.
- [ ] Добавить anti-bot слой: rate limits, account age weighting, trust_score, abuse_score, suspicious reaction throttling, moderation queue.
- [ ] Использовать ClickHouse для поиска аномалий: резкие накрутки, одинаковые подсети, новые аккаунты, необычная активность.

## Phase 21 — Edge protection, Cloudflare fallback and emergency access

- [ ] Cloudflare использовать как edge protection: WAF, DDoS protection, bot rules, tunnel/edge ingress.
- [ ] Не делать Cloudflare core auth dependency; приложение должно иметь собственные auth/rate limits/session checks.
- [ ] Предусмотреть fallback direct domain, например `direct.example.net`, защищённый Nginx rate limits, firewall/fail2ban/nftables и app-level throttling.
- [ ] Для social login заранее зарегистрировать fallback OAuth redirect URLs.
- [ ] Предусмотреть emergency status page и degraded mode на случай падения Cloudflare.
- [ ] Не открывать admin routes через fallback без дополнительных ограничений.

## Phase 22 — Legal readiness, rights confirmation and terms versioning

- [ ] Финальным этапом проверить актуальные законы и требования по пользовательскому контенту, персональным данным, платежам и публичной библиотеке.
- [ ] Подготовить Terms of Service, Privacy Policy, Content Policy, Copyright/Takedown Policy.
- [ ] Ввести `TermsAcceptance` с `terms_version`, `accepted_at`, `ip_hash/user_agent_hash`, `locale`.
- [ ] Ввести `ContentRightsConfirmation` для загрузки/публикации треков.
- [ ] Пользователь должен подтверждать, что имеет права на загрузку, обработку и публикацию материала.
- [ ] Версионировать юридические документы и требовать повторное согласие при существенных изменениях.

## Phase 23 — Account recovery, sessions and device security

- [ ] Ввести `UserSession`/`DeviceSession`: user, device label, created_at, last_seen_at, ip_hash, user_agent_hash, revoked_at.
- [ ] Дать пользователю список активных сессий и кнопку logout from all devices.
- [ ] Добавить session rotation после login, provider link/unlink, password reset, privilege escalation и suspicious activity.
- [ ] Поддержать trusted devices для снижения лишних проверок, но хранить их с expiration и revoke path.
- [ ] Подготовить account recovery flow: lost provider access, provider account changed, email verification if email/password появится позже.
- [ ] Для админов обязательно MFA, отдельные admin sessions, shorter TTL и audit log всех действий.
- [ ] Добавить suspicious login detection: новая страна/ASN/device, резкая смена IP, слишком много попыток входа.
- [ ] Ввести lockout/backoff не только на password flow, но и на sensitive OAuth/account-link actions.

## Phase 24 — Moderation, copyright and takedown pipeline

- [ ] Ввести `ContentReport`, `ModerationCase`, `ModerationAction`, `Appeal`, `TakedownRequest`.
- [ ] Поддержать user reports: copyright, spam, abuse, wrong metadata, offensive cover/text, illegal content.
- [ ] Добавить статусы: pending_review, hidden, blocked, restored, appealed, takedown_received, takedown_resolved.
- [ ] Сделать возможность быстро скрыть public track без удаления оригинальных данных владельца.
- [ ] Добавить repeat offender policy и abuse score по аккаунту.
- [ ] Заложить audio fingerprint/content hash для поиска повторных загрузок заблокированного контента.
- [ ] Все moderation actions должны идти через audit log и быть обратимыми, где это юридически допустимо.
- [ ] Подготовить отдельную очередь/панель для ручной модерации публичной библиотеки.

## Phase 25 — Search, indexing and media delivery

### Search/indexing

- [ ] Начать с PostgreSQL full-text/trigram indexes для публичной библиотеки.
- [ ] Индексировать title, artist, album, genre, mood, language, tags, metadata, public status.
- [ ] Добавить отдельные query models для recent, trending, top, by genre, by mood, by language.
- [ ] Позже рассмотреть Meilisearch/OpenSearch как отдельный read-model, но не вводить сразу.
- [ ] Search index update делать через events/outbox, а не синхронно внутри upload/metadata update flow.

### Media delivery

- [ ] Django не должен становиться файловым сервером для постоянной раздачи медиа.
- [ ] Поддержать range requests, cache headers, signed media URLs и stream-only policy.
- [ ] Разделить original, processed, preview clip, cover, waveform, lyrics/transcription artifacts.
- [ ] Подготовить preview clips для публичной библиотеки и ограничения download policy.
- [ ] Позже рассмотреть HLS/DASH для длинных файлов или streaming-режима.
- [ ] Все media URLs должны проходить через entitlement/visibility checks и истекать по времени.

## Phase 26 — CI/CD, testing, load testing and cost control

### CI/CD and quality gates

- [ ] Добавить обязательные checks: lint, format, typecheck, unit tests, integration tests, migration tests.
- [ ] Добавить security checks: dependency audit, license scan, secret scan, unsafe raw SQL scan.
- [ ] Добавить Docker build checks для `web`, workers и будущих сервисов.
- [ ] Добавить smoke tests для upload -> process -> play -> delete flow.
- [ ] Проверять migrations на пустой базе и на базе с legacy fixtures.
- [ ] Добавить contract tests для HTTP/Kafka/WebSocket schemas.

### Load testing and cost control

- [ ] Ввести load/stress tests для upload, streaming, waveform, processing queue, WebSocket, public library feed.
- [ ] Считать cost per job: CPU time, GPU time, RAM/VRAM, storage growth, egress, external API usage.
- [ ] Ввести capacity model для Free/Standard/Pro: concurrent jobs, max file length, queue priority, retry budget.
- [ ] Добавить queue saturation alerts и graceful degradation: disable AI temporarily, delay heavy jobs, preserve playback.
- [ ] Заложить ClickHouse/Kafka retention cost и cleanup policies.
- [ ] Не обещать Pro-лимиты, пока не измерена реальная стоимость AI/DSP обработки.

## Phase 27 — Notifications, support tooling and ADR

### Notifications

- [ ] Добавить in-app notifications как первый канал.
- [ ] События уведомлений: processing completed/failed, quota almost full, storage full, subscription expiring, payment failed, external drive disconnected, moderation decision, takedown request.
- [ ] Позже добавить email/telegram/etc через отдельный NotificationProviderAdapter.
- [ ] Уведомления делать идемпотентными и хранить delivery attempts.
- [ ] Дать пользователю настройки уведомлений и quiet hours.

### Support tooling

- [ ] Сделать support/admin panel: find user, view quota, view jobs, recalculate storage usage, retry/cancel job, hide public track, disable suspicious account.
- [ ] Любое support/admin действие должно иметь RBAC/ABAC, reason, audit log и, где нужно, approval.
- [ ] Разделить роли: support, moderator, billing_admin, system_admin.
- [ ] Не показывать support-ролям лишние PII/секреты; sensitive fields masked by default.
- [ ] Добавить safe impersonation/debug mode без раскрытия токенов и паролей.

### ADR

- [ ] Завести `docs/adr/` для архитектурных решений.
- [ ] Первые ADR: PostgreSQL as source of truth, Kafka KRaft, ClickHouse analytics, avoid MinIO, Django as BFF, StorageService abstraction.
- [ ] Каждый ADR должен фиксировать context, decision, consequences, alternatives.
- [ ] Новые крупные инфраструктурные решения принимать через ADR, чтобы не терять причины выбора.

## Suggested first implementation order

1. Settings split + Docker Compose baseline.
2. PostgreSQL migration.
3. Modular package split + typing.
4. `Track`/`AudioAsset`/`ProcessingJob`/`AudioMetrics`.
5. Repositories + Unit of Work boundaries.
6. Celery workers and processing queues.
7. Accounts/AuthIdentity and anonymous/read-only policy.
8. Plans/Entitlements/UsageLedger/QuotaReservation without real payments.
9. Storage quotas and `StorageService` abstraction.
10. WebSocket statuses with Redis/Channels.
11. Account sessions, audit log and admin MFA baseline.
12. Public library moderation/reporting baseline.
13. Search/read models and media delivery policy.
14. Outbox/Inbox and Kafka KRaft.
15. ClickHouse analytics consumers.
16. CI/CD quality gates, security checks and smoke tests.
17. Observability, encryption and backup/restore drill.
18. Load testing and cost model before expanding Pro/AI limits.
19. External drive integrations.
20. FakePaymentProvider, then real payment provider after full testing.
21. Notifications and support tooling.
22. ADR documents for all major architecture choices.

## Notes

- Это дорожная карта, не runtime-код.
- Порядок можно менять, но нельзя пропускать transaction/idempotency/security/storage abstractions, иначе later-stage features будут дорогими.
- Любая новая инфраструктура должна приходить с feature flag, fallback и manual recovery path.
