import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


def _db_to_gain(db_value):
    return float(10 ** (float(db_value) / 20.0))


def _as_channel_first(audio):
    """Return float32 audio shaped as (channels, samples)."""
    data = np.asarray(audio, dtype=np.float32)
    if data.ndim == 1:
        return data[np.newaxis, :]

    if data.ndim != 2:
        raise ValueError(f"Expected 1D/2D audio array, got shape {data.shape}")

    # Most internal code uses (channels, samples). If a decoded array still looks
    # like (samples, channels), flip it once at the boundary.
    if data.shape[0] > data.shape[1] and data.shape[1] <= 8:
        data = data.T

    return data


def apply_gain_db(audio, gain_db):
    return _as_channel_first(audio) * _db_to_gain(gain_db)


def peak_limit(audio, ceiling_db=-1.0):
    """
    Sample-peak safety limiter. This is not an oversampled true-peak limiter,
    but it prevents clipped exports after EQ/loudness compensation.
    """
    data = _as_channel_first(audio)
    ceiling = _db_to_gain(ceiling_db)
    peak = float(np.max(np.abs(data))) if data.size else 0.0

    if not math.isfinite(peak) or peak <= 0.0:
        return np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    if peak > ceiling:
        data = data * (ceiling / peak)

    return np.nan_to_num(data, nan=0.0, posinf=ceiling, neginf=-ceiling)


def _fallback_loudness_db(audio):
    data = _as_channel_first(audio)
    rms = float(np.sqrt(np.mean(data**2) + 1e-12))
    if rms <= 0.0 or not math.isfinite(rms):
        return None
    return 20.0 * math.log10(rms)


def measure_lufs(audio, sample_rate):
    """
    Measure integrated LUFS with pyloudnorm when available.
    Falls back to RMS-like loudness so processing never hard-fails.
    """
    data = _as_channel_first(audio)

    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(int(sample_rate))
        loudness = float(meter.integrated_loudness(data.T))
        if math.isfinite(loudness):
            return loudness
    except Exception as exc:
        logger.warning("LUFS measurement failed, using RMS fallback: %s", exc)

    return _fallback_loudness_db(data)


def normalize_loudness(
    audio,
    sample_rate,
    target_lufs=None,
    *,
    peak_ceiling_db=-1.0,
    max_boost_db=9.0,
    max_cut_db=24.0,
):
    """
    Match integrated loudness to target_lufs and keep sample peaks under ceiling.

    max_boost_db is intentionally conservative. Bad/quiet uploads should not be
    amplified into noise just because a preset asks for a target loudness.
    """
    data = _as_channel_first(audio)

    if target_lufs is None:
        return peak_limit(data, ceiling_db=peak_ceiling_db)

    try:
        target = float(target_lufs)
    except (TypeError, ValueError):
        logger.warning("Invalid target_lufs=%r; applying peak limiting only", target_lufs)
        return peak_limit(data, ceiling_db=peak_ceiling_db)

    measured = measure_lufs(data, sample_rate)
    if measured is None or not math.isfinite(measured):
        logger.warning("Could not measure loudness; applying peak limiting only")
        return peak_limit(data, ceiling_db=peak_ceiling_db)

    gain_db = target - measured
    gain_db = max(-float(max_cut_db), min(float(max_boost_db), gain_db))

    logger.info(
        "Loudness normalization: measured=%.2f LUFS, target=%.2f LUFS, gain=%.2f dB",
        measured,
        target,
        gain_db,
    )

    normalized = apply_gain_db(data, gain_db)
    return peak_limit(normalized, ceiling_db=peak_ceiling_db)
