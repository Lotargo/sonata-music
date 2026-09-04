# [Phase A] Studio Experience: Stereo L/R Spectrogram, A/B Player, Scalar Docs & Audio Tools

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase A (ФАЗА А: Лёгкая сложность / Quick Wins / Высокий визуальный эффект) from the root ROADMAP.md, delivering a dual-panel stereo L/R spectrogram, seamless A/B comparison with Delta Solo, modal upgrade with Pro-Q pre-filter, ComfyUI_MusicTools DSP ports, and Scalar OpenAPI 3.1 interactive documentation. (Note: CLI Provider Layer Adapter deferred to later per user request).

**Architecture:** Extend `MetricsService` and Web Audio API for dual-channel stereo L/R analysis and clickless A/B crossfading; enhance `StudioDSP` with targeted de-mudding and audio repair (de-clip, de-click, DC offset); add OpenAPI 3.1 schema and Scalar documentation template at `/api/docs/`.

**Tech Stack:** Python 3.12, Django 5, NumPy, SciPy, Pedalboard, SoundFile, Web Audio API, WaveSurfer.js, Canvas 2D, Scalar OpenAPI UI.

---

### Task 1: Stereo L/R Metrics & Dual-Panel Spectrogram

**Files:**
- Modify: `music/services/metrics.py`
- Modify: `music/templates/music/components/details_modal.html`
- Modify: `music/static/music/js/details.js`
- Test: `tests/test_phase_a_stereo_metrics.py`

- [ ] **Step 1: Write test for stereo metrics and correlation**
- [ ] **Step 2: Implement stereo metrics calculation in `MetricsService`**
- [ ] **Step 3: Update details modal HTML and JS for Stereo Spectrogram L/R view**
- [ ] **Step 4: Run tests and verify**
- [ ] **Step 5: Commit**

---

### Task 2: Seamless Synchronous A/B Comparison Player with Delta Solo

**Files:**
- Modify: `music/templates/music/components/details_modal.html`
- Modify: `music/static/music/js/details.js`

- [ ] **Step 1: Add Delta Solo button and GainNode crossfade graph in `details.js`**
- [ ] **Step 2: Verify smooth 5ms crossfade between Original and Result without clicks**
- [ ] **Step 3: Commit**

---

### Task 3: Modal Upgrade with Engine Selector, Presets & Pro-Q Pre-Filter

**Files:**
- Modify: `music/templates/music/components/upload_modal.html`
- Modify: `music/static/music/js/upload.js`
- Modify: `music/services/dsp.py`

- [ ] **Step 1: Add engine selector (`Stealth`, `AudioSR Ultra`, `Apollo`, `FLowHigh`) and presets**
- [ ] **Step 2: Add interactive Pro-Q pre-filter canvas widget in modal**
- [ ] **Step 3: Commit**

---

### Task 4: ComfyUI_MusicTools Deconstruction in StudioDSP

**Files:**
- Modify: `music/services/dsp.py`
- Test: `tests/test_phase_a_dsp_repair.py`

- [ ] **Step 1: Write tests for `apply_music_fix` and `apply_audio_repair`**
- [ ] **Step 2: Implement targeted 200–500 Hz de-mud and audio repair (DC removal, de-clip, de-click)**
- [ ] **Step 3: Run tests and verify**
- [ ] **Step 4: Commit**

---

### Task 5: Interactive Scalar API Map (`/api/docs/`)

**Files:**
- Create: `music/openapi.py`
- Create: `music/templates/music/scalar_docs.html`
- Modify: `music/views.py`
- Modify: `music/urls.py`
- Test: `tests/test_phase_a_scalar.py`

- [ ] **Step 1: Write tests for `/api/openapi.json` and `/api/docs/`**
- [ ] **Step 2: Create OpenAPI 3.1 specification in `music/openapi.py`**
- [ ] **Step 3: Create Scalar template and register routes in `urls.py` and `views.py`**
- [ ] **Step 4: Run tests and verify**
- [ ] **Step 5: Update ROADMAP.md Phase A checkboxes**
- [ ] **Step 6: Commit**
