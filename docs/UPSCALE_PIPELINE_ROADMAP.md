# Upscale Pipeline Roadmap

This document fixes the next roadmap for improving the audio upscale pipeline. The main goal is not to replace every model with a single new model, but to turn the pipeline into a model-aware system: input type -> pipeline -> model backend -> DSP/loudness safety.

## Current baseline

The current pipeline already has a useful foundation:

- AudioSR for general AI super-resolution.
- Demucs/HTDemucs for stem separation.
- Pedalboard-based DSP presets.
- Mid/Side handling in AI mode.
- Chunked processing for long tracks.
- Loudness and peak-safety work added in the current stabilization branch.

The main weakness is that the current model stack is too static. Every input is pushed through a small number of hardcoded model choices, even though different sources need different treatment.

## Target architecture

Introduce a model registry instead of hardcoding models directly in service classes.

```python
SEPARATION_MODELS = {
    "fast": {
        "backend": "demucs",
        "model": "htdemucs",
        "device_policy": "auto",
    },
    "quality": {
        "backend": "demucs",
        "model": "htdemucs_ft",
        "device_policy": "auto",
    },
    "pro": {
        "backend": "roformer",
        "model": "mel_band_roformer",
        "device_policy": "cuda_preferred",
    },
}
```

```python
UPSCALE_MODELS = {
    "general": {
        "backend": "audiosr",
        "model": "basic",
        "safe_default": True,
    },
    "music_experimental": {
        "backend": "music_sr",
        "model": "flow_matching_sr",
        "experimental": True,
    },
}
```

```python
RESTORATION_MODELS = {
    "basic": {
        "separator": "htdemucs_ft",
        "restorer": "dsp_loudness_chain",
    },
    "pro": {
        "separator": "mel_band_roformer",
        "restorer": "neural_waveform_restorer",
        "experimental": True,
    },
}
```

The UI should expose simple quality modes, not raw model names at first:

- Fast
- Balanced
- Quality
- Experimental

Raw model selection can later be added to a developer/debug panel.

## Phase 1: Low-risk separator upgrade

### Replace default `htdemucs` with configurable Demucs models

Priority: high
Risk: low
Expected gain: better hybrid/restoration quality with minimal integration cost

Current hardcoded behavior should be replaced by a configurable model name:

```python
SEPARATOR_MODEL=htdemucs_ft
```

Recommended defaults:

- Fast: `htdemucs`
- Balanced/Quality: `htdemucs_ft`

Why this comes first:

- It does not require a new inference backend.
- It keeps the current Demucs integration.
- It improves stem quality before we touch more complex restoration logic.

Acceptance criteria:

- Existing hybrid mode still works.
- Existing restoration mode still works.
- CPU fallback still works.
- GPU memory is released after processing.
- Output stems do not clip before final DSP/loudness stage.

## Phase 2: Add RoFormer separation backend

Priority: high
Risk: medium
Expected gain: stronger vocal/instrument separation and better restoration base

Add a second separation backend next to Demucs:

- BS-RoFormer
- Mel-Band RoFormer
- vocal-focused Mel-RoFormer variant if needed

Recommended routing:

| Input / Mode | Default backend | Alternative |
| --- | --- | --- |
| Fast separation | Demucs `htdemucs` | none |
| Balanced separation | Demucs `htdemucs_ft` | BS-RoFormer |
| Pro hybrid | Mel-Band RoFormer | BS-RoFormer |
| Vocal cleanup | Mel-RoFormer vocal | Demucs vocals stem |

Implementation notes:

- Do not remove Demucs.
- Add a backend interface like `BaseSeparator.separate(input_path, output_dir) -> stems_map`.
- Normalize all separators to the same internal stem map: `vocals`, `drums`, `bass`, `other`.
- Keep model loading/unloading isolated per backend.
- Add per-model VRAM notes.

Acceptance criteria:

- Same input can be processed by Demucs and RoFormer backends.
- Hybrid mode can switch backend from request/config.
- Stems are aligned in length and sample rate.
- Failed RoFormer run can fallback to Demucs.

## Phase 3: Keep AudioSR, but stop treating it as the only AI upscale model

Priority: medium
Risk: medium
Expected gain: cleaner product behavior and better future extensibility

AudioSR should remain the safe default for general audio super-resolution, but it should be framed as one backend, not the whole upscale strategy.

Recommended role:

- General AI upscaling.
- Poor MP3 restoration where hallucinated high-frequency detail is acceptable.
- Sound effects and mixed content.
- Default fallback when experimental music-specific SR is unavailable.

Weakness to control:

- It can invent artificial high-frequency material.
- It is not always music-mastering aware.
- It can make cymbals, air, and vocal sibilance sound fake on some inputs.

Required controls:

- Keep `ai_prep` before AudioSR.
- Add optional post-AI de-harshing EQ.
- Keep loudness normalization after AI output.
- Track metrics before and after AudioSR.

Acceptance criteria:

- AudioSR remains stable as default AI backend.
- UI copy does not imply that 96 kHz export means true neural high-resolution generation.
- AI mode has a safe preset and an advanced override path.

## Phase 4: Add music-specific experimental SR

Priority: medium
Risk: high
Expected gain: possible higher-quality music restoration, but only after evaluation

Add an experimental music-focused SR backend. Candidate class:

- flow-matching music super-resolution models
- InspireMusic-style SR backend
- future music restoration models that operate on waveform/spectrogram representations

This must be isolated behind an experimental flag.

Recommended routing:

```text
AI Upscale / General -> AudioSR
AI Upscale / Music Experimental -> music-specific SR backend
```

Implementation notes:

- Do not make this the default.
- Require explicit opt-in in UI or config.
- Run on shorter clips first.
- Cache model loading separately from AudioSR.
- Store exact backend/model/version in processing metadata.

Acceptance criteria:

- The model can process 30-60 second clips without crashing.
- Output is subjectively better than AudioSR on at least some music cases.
- Artifacts are documented, not hidden.
- Fallback to AudioSR is available.

## Phase 5: Replace basic restoration with source restoration pipeline

Priority: high after Phase 2
Risk: high
Expected gain: biggest improvement for degraded music

Current restoration is closer to:

```text
separate -> re-sum stems -> DSP polish
```

The target restoration pipeline should become:

```text
separate degraded mix -> restore stems/waveform -> re-mix -> loudness/master safety
```

Recommended versions:

```text
restoration_v1 = Demucs or RoFormer separation + DSP/loudness chain
restoration_v2 = RoFormer separator + neural waveform restorer
```

The neural waveform restorer can later be based on HiFi++-like or other music-source-restoration approaches.

Implementation notes:

- Keep v1 as stable/basic.
- Add v2 as experimental.
- Do not hide v2 behind the same label as v1.
- Store restoration version in job metadata.
- Add A/B compare in UI.

Acceptance criteria:

- Restoration v1 remains available.
- Restoration v2 is opt-in.
- Stems are not blindly summed without peak/loudness safety.
- A/B preview exists before replacing user-facing defaults.

## Phase 6: Add speech/home-recording cleanup mode

Priority: medium
Risk: low-medium
Expected gain: useful new product mode outside pure music upscaling

Add a separate mode for voice, noisy home recordings, podcast-like audio, phone recordings, and rough demos.

Recommended model family:

- DeepFilterNet-style speech enhancement

Recommended chain:

```text
DeepFilterNet -> light EQ -> loudness normalize -> optional AudioSR
```

This should not be mixed with music restoration by default. Speech cleanup and music mastering are different tasks.

Acceptance criteria:

- User can select Voice/Home Recording Cleanup.
- Noise reduction does not run automatically on finished music unless explicitly selected.
- Output remains natural and does not over-suppress ambience.

## Phase 7: Evaluation harness

Priority: high
Risk: low
Expected gain: prevents random model swapping and placebo improvements

Before making new models default, add a small evaluation harness.

Test sets:

- clean WAV reference -> degraded MP3/AAC versions
- Suno/Udio-style generated music
- noisy voice/home recordings
- bass-heavy tracks
- vocal-heavy tracks
- tracks with cymbals/high-frequency detail

Metrics:

- LUFS before/after
- true/sample peak before/after
- clipping count
- spectral centroid shift
- high-frequency energy change
- stereo correlation
- processing time
- peak memory/VRAM if available

Subjective checks:

- fake cymbal/air artifacts
- harsh sibilance
- bass smearing
- vocal phase problems
- stereo image collapse
- over-compression

Acceptance criteria:

- Every new backend has a before/after report.
- Every default switch requires evidence.
- Bad cases are documented.

## Suggested implementation order

1. Add model registry and config plumbing.
2. Change Demucs default from `htdemucs` to configurable `htdemucs_ft` for quality mode.
3. Add RoFormer separator backend behind `pro` mode.
4. Keep AudioSR as general default, but expose backend identity in metadata.
5. Add experimental music-specific SR backend.
6. Add restoration v2 with neural waveform restoration.
7. Add speech/home-recording cleanup mode.
8. Add evaluation reports and A/B comparison UI.

## Product rule

The product should not promise magic upscaling. The correct promise is:

```text
We analyze the input type, choose the safest enhancement pipeline, and preserve loudness/peak safety while improving perceived quality where possible.
```

Bad rule:

```text
Any track -> one AI model -> better quality.
```

Good rule:

```text
Input type -> matched model pipeline -> controlled DSP -> loudness-safe export.
```

## Near-term tasks

- Add `SEPARATOR_MODEL` and `SEPARATOR_QUALITY_MODE` settings.
- Update `separator.py` to accept model name from config/request.
- Add `htdemucs_ft` quality mode.
- Add model metadata to processing result.
- Add `processing_config` JSON storage in the database.
- Add evaluation script for 5-10 local audio samples.
- Rename UI label from `96 kHz quality` to `96 kHz export sample rate` if such wording exists in the UI.
- Add a debug panel or hidden developer config for model backend selection.

## Non-goals for the next step

- Do not remove AudioSR.
- Do not remove Demucs.
- Do not make experimental SR default.
- Do not add heavy research models before the evaluation harness exists.
- Do not expose raw model names to normal users before the product language is cleaned up.
