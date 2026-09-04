# [Phase A] Studio Experience: Stereo L/R Spectrogram, A/B Player, Scalar Docs & Audio Tools

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase A (ФАЗА А: Лёгкая сложность / Quick Wins / Высокий визуальный эффект) from the root ROADMAP.md, delivering a dual-panel stereo L/R spectrogram, seamless A/B comparison with Delta Solo, modal upgrade with Pro-Q pre-filter, ComfyUI_MusicTools DSP ports, and Scalar OpenAPI 3.1 interactive documentation. (Note: CLI Provider Layer Adapter deferred to later per user request).

**Architecture:** Extend `MetricsService` and Web Audio API for dual-channel stereo L/R analysis and clickless A/B crossfading; enhance `StudioDSP` with targeted de-mudding and audio repair (de-clip, de-click, DC offset); add OpenAPI 3.1 schema and Scalar documentation template at `/api/docs/`.

**Tech Stack:** Python 3.12, Django 5, NumPy, SciPy, Pedalboard, SoundFile, Web Audio API, WaveSurfer.js, Canvas 2D, Scalar OpenAPI UI.

> **Статус проверки (2026-09-05): ✅ ВСЕ ЗАДАЧИ ВЫПОЛНЕНЫ.** Проверено по коду и тестам: `test_phase_a_stereo_metrics` (5/5 OK), `test_phase_a_dsp_repair` (5/5 OK), `test_phase_a_scalar` (4/4 OK) — итого 14/14. Реализация смержена в PR #80 (`58bea5c`), ROADMAP.md Phase A пп. 1–5 отмечены `[x]`, п. 6 (CLI Provider) deferred по просьбе пользователя. Чекбоксы ниже отмечены по факту.

---

### Task 1: Stereo L/R Metrics & Dual-Panel Spectrogram

**Files:**
- Modify: `music/services/metrics.py`
- Modify: `music/templates/music/components/details_modal.html`
- Modify: `music/static/music/js/details.js`
- Test: `tests/test_phase_a_stereo_metrics.py`

- [x] **Step 1: Write test for stereo metrics and correlation** — ✅ выполнено: `tests/test_phase_a_stereo_metrics.py` (5 тестов: mono, identical stereo, out-of-phase, wide stereo, report).
- [x] **Step 2: Implement stereo metrics calculation in `MetricsService`** — ✅ выполнено: `music/services/metrics.py:15-106` (`peak_l/r_db`, `rms_l/r_db`, `rms_mid/side_db`, `stereo_correlation`, `stereo_width_ratio`).
- [x] **Step 3: Update details modal HTML and JS for Stereo Spectrogram L/R view** — ✅ выполнено: `details_modal.html:102-145` (dual-panel `spec-canvas-left/right` + correlation/side/width метры), `details.js:653-779` (Canvas FFT heatmap, `switchSpectrogramSource`, `updateCorrelationGauge`).
- [x] **Step 4: Run tests and verify** — ✅ выполнено (2026-09-05): 5/5 OK.
- [x] **Step 5: Commit** — ✅ выполнено: смержено в PR #80 (`58bea5c`, файлы `metrics.py`, `details.js`, `details_modal.html` в составе).

---

### Task 2: Seamless Synchronous A/B Comparison Player with Delta Solo

**Files:**
- Modify: `music/templates/music/components/details_modal.html`
- Modify: `music/static/music/js/details.js`

- [x] **Step 1: Add Delta Solo button and GainNode crossfade graph in `details.js`** — ✅ выполнено: `details_modal.html:147-158` (кнопки A/B/Δ Delta Solo), `details.js:387-490` (`fadeAudioVolume` 5 мс, `trySetupWebAudioDelta` с `GainNode`, инверсия фазы B−A для Delta).
- [x] **Step 2: Verify smooth 5ms crossfade between Original and Result without clicks** — ✅ выполнено: кроссфейд 5 мс через `requestAnimationFrame` + `linearRampToValueAtTime(+0.005)`, синхронизация позиции `setTime` при переключении.
- [x] **Step 3: Commit** — ✅ выполнено: в составе PR #80.

---

### Task 3: Modal Upgrade with Engine Selector, Presets & Pro-Q Pre-Filter

**Files:**
- Modify: `music/templates/music/components/upload_modal.html`
- Modify: `music/static/music/js/upload.js`
- Modify: `music/services/dsp.py`

- [x] **Step 1: Add engine selector (`Stealth`, `AudioSR Ultra`, `Apollo`, `FLowHigh`) and presets** — ✅ выполнено: `upload_modal.html:107-128` (4 движка), `upload.js:363-379` (`setAiEngine`), пресеты `Mastering…Music Fix/Audio Repair` в `upload_modal.html:172-185` + backend `dsp.py:28-137`, `views.py:262-272` (`crossover_freq`, `mud_cut_db`), `openapi.py:429-499`.
- [x] **Step 2: Add interactive Pro-Q pre-filter canvas widget in modal** — ✅ выполнено: `upload_modal.html:187-215` (`pro-q-canvas`, слайдеры crossover 10–19 кГц и notch 350 Гц), `upload.js:381-622` (кривая АЧХ, drag nodes, `updateProQCrossover/Notch`, payload `crossover_freq/mud_cut_db` в `startProcessing`).
- [x] **Step 3: Commit** — ✅ выполнено: в составе PR #80.

---

### Task 4: ComfyUI_MusicTools Deconstruction in StudioDSP

**Files:**
- Modify: `music/services/dsp.py`
- Test: `tests/test_phase_a_dsp_repair.py`

- [x] **Step 1: Write tests for `apply_music_fix` and `apply_audio_repair`** — ✅ выполнено: `tests/test_phase_a_dsp_repair.py` (5 тестов: пресеты, de-mud 350 Гц, DC offset, de-clip, de-click).
- [x] **Step 2: Implement targeted 200–500 Hz de-mud and audio repair (DC removal, de-clip, de-click)** — ✅ выполнено: `dsp.py:605-622` (`apply_music_fix`: notch 350 Гц Q=1.6 + air shelf 11 кГц), `dsp.py:624-703` (`apply_audio_repair`: DC removal + HPF 18 Гц, полиномиальный de-clip ≤30 сэмплов, median de-click kernel=5), хуки в `process()` + пресеты `music_fix`/`audio_repair`.
- [x] **Step 3: Run tests and verify** — ✅ выполнено (2026-09-05): 5/5 OK.
- [x] **Step 4: Commit** — ✅ выполнено: в составе PR #80.

---

### Task 5: Interactive Scalar API Map (`/api/docs/`)

**Files:**
- Create: `music/openapi.py`
- Create: `music/templates/music/scalar_docs.html`
- Modify: `music/views.py`
- Modify: `music/urls.py`
- Test: `tests/test_phase_a_scalar.py`

- [x] **Step 1: Write tests for `/api/openapi.json` and `/api/docs/`** — ✅ выполнено: `tests/test_phase_a_scalar.py` (4 теста: структура спеки, JSON-эндпоинт, Scalar HTML, health).
- [x] **Step 2: Create OpenAPI 3.1 specification in `music/openapi.py`** — ✅ выполнено: `music/openapi.py` (592 строки, OpenAPI 3.1.0, теги, схемы `ProcessTrackRequest` с `engine/crossover_freq/mud_cut_db`, `StereoMetricsResponse`).
- [x] **Step 3: Create Scalar template and register routes in `urls.py` and `views.py`** — ✅ выполнено: `scalar_docs.html` (Scalar `@scalar/api-reference`, тёмная тема), `urls.py:27-28` (`api/openapi.json`, `api/docs/`), `views.py:873-883` (`openapi_spec`, `scalar_docs`).
- [x] **Step 4: Run tests and verify** — ✅ выполнено (2026-09-05): 4/4 OK.
- [x] **Step 5: Update ROADMAP.md Phase A checkboxes** — ✅ выполнено: ROADMAP.md пп. 1–5 `[x]`, п. 6 CLI Bridge `[ ]` deferred (коммит `d385b6b`).
- [x] **Step 6: Commit** — ✅ выполнено: в составе PR #80.
