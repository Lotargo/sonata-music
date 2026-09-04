"""
Acoustic and Musical Analysis Service.
Powered by Librosa, SoundFile, and NumPy.

Provides:
- BPM & Beat Tracking
- Musical Key and Scale Estimation (Krumhansl-Schmuckler algorithm)
- Spectral Centroid & Brightness Analysis
- Smart Silence Detection and Trimming
- Analog Drift & Micro-Deviation (Stealth / Anti-AI protection)
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import soundfile as sf

# Compatibility shim for SciPy 1.13+ where window functions were moved to scipy.signal.windows
import scipy.signal
try:
    import scipy.signal.windows as s_windows
    for _attr in ('hann', 'hamming', 'blackman', 'bartlett', 'flattop', 'boxcar'):
        if not hasattr(scipy.signal, _attr) and hasattr(s_windows, _attr):
            setattr(scipy.signal, _attr, getattr(s_windows, _attr))
except Exception:
    pass

import librosa

logger = logging.getLogger(__name__)

# Pitch names and Krumhansl-Schmuckler tonality profiles
PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def estimate_musical_key(chroma_mean: np.ndarray) -> Tuple[str, float]:
    """
    Estimate musical key (e.g. 'C Major', 'F# Minor') and correlation coefficient
    using the Krumhansl-Schmuckler key-finding algorithm against a 12-bin mean chromagram.
    """
    if chroma_mean is None or len(chroma_mean) != 12:
        return 'Unknown', 0.0

    correlations = []
    for i in range(12):
        # Circular shift for each tonic
        shifted = np.roll(chroma_mean, -i)
        
        # Pearson correlation with major and minor profiles
        maj_corr = float(np.corrcoef(shifted, MAJOR_PROFILE)[0, 1])
        min_corr = float(np.corrcoef(shifted, MINOR_PROFILE)[0, 1])

        correlations.append((maj_corr if not np.isnan(maj_corr) else -1.0, f"{PITCH_NAMES[i]} Major"))
        correlations.append((min_corr if not np.isnan(min_corr) else -1.0, f"{PITCH_NAMES[i]} Minor"))

    best_corr, best_key = max(correlations, key=lambda x: x[0])
    return best_key, max(0.0, best_corr)


def analyze_track_acoustics(
    audio_path: str | Path,
    max_duration: float = 75.0,
    sample_rate: int = 22050
) -> Dict[str, Any]:
    """
    Analyze acoustic and musical properties of an audio file:
    - BPM (Tempo)
    - Key and Scale (Major / Minor)
    - Key confidence
    - Spectral Centroid (mean brightness in Hz)
    - Full duration in seconds
    - Leading/trailing silence intervals
    """
    path = Path(audio_path)
    result: Dict[str, Any] = {
        'bpm': None,
        'musical_key': None,
        'key_confidence': None,
        'spectral_centroid': None,
        'duration': None,
        'has_silence': False,
        'trim_offset_sec': 0.0,
    }

    if not path.exists():
        logger.warning(f"[AudioAnalyzer] File not found: {path}")
        return result

    try:
        # 1. Fast metadata duration check via soundfile
        try:
            info = sf.info(str(path))
            result['duration'] = round(float(info.duration), 2)
        except Exception:
            pass

        # 2. Load mono audio downsampled to 22.05 kHz for fast, light analysis
        y, sr = librosa.load(str(path), sr=sample_rate, duration=max_duration, mono=True)
        if y.size == 0:
            return result

        if result['duration'] is None:
            result['duration'] = round(float(len(y) / sr), 2)

        # 3. Detect BPM
        try:
            tempo_result, _ = librosa.beat.beat_track(y=y, sr=sr)
            if hasattr(tempo_result, 'item'):
                tempo_val = float(tempo_result.item())
            elif isinstance(tempo_result, (list, tuple, np.ndarray)) and len(tempo_result) > 0:
                tempo_val = float(tempo_result[0])
            else:
                tempo_val = float(tempo_result)
            
            if 40.0 <= tempo_val <= 240.0:
                result['bpm'] = round(tempo_val, 1)
        except Exception as e:
            logger.debug(f"[AudioAnalyzer] BPM detection error on {path.name}: {e}")

        # 4. Key Estimation using Constant-Q Chromagram
        try:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            key, conf = estimate_musical_key(chroma_mean)
            result['musical_key'] = key
            result['key_confidence'] = round(conf, 2)
        except Exception as e:
            logger.debug(f"[AudioAnalyzer] Key estimation error on {path.name}: {e}")

        # 5. Spectral Centroid (Frequency brightness)
        try:
            cent = librosa.feature.spectral_centroid(y=y, sr=sr)
            result['spectral_centroid'] = round(float(np.mean(cent)), 1)
        except Exception as e:
            logger.debug(f"[AudioAnalyzer] Spectral centroid error on {path.name}: {e}")

        # 6. Silence detection
        try:
            _, trim_indices = librosa.effects.trim(y, top_db=45)
            leading_silence_samples = trim_indices[0]
            if leading_silence_samples > sr * 0.15: # more than 150ms of silence
                result['has_silence'] = True
                result['trim_offset_sec'] = round(leading_silence_samples / sr, 3)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[AudioAnalyzer] Failed to analyze {path}: {e}")

    return result


def trim_silence_lossless(
    input_path: str | Path,
    output_path: str | Path,
    top_db: float = 45.0
) -> Tuple[bool, float, float]:
    """
    Trims digital silence from the start and end of an audio file without re-encoding quality loss.
    Returns (success, start_trimmed_sec, end_trimmed_sec).
    """
    in_p = Path(input_path)
    out_p = Path(output_path)

    try:
        data, sr = sf.read(str(in_p), dtype='float32')
        # Check if mono or multichannel
        if data.ndim == 1:
            mono = data
        else:
            mono = np.mean(data, axis=1)

        # Detect non-silent interval
        # Compute amplitude threshold from top_db
        db = 20 * np.log10(np.maximum(np.abs(mono), 1e-7))
        max_db = np.max(db)
        threshold = max_db - top_db
        non_silent = np.where(db > threshold)[0]

        if len(non_silent) == 0:
            # Entire file is silent, do nothing
            return False, 0.0, 0.0

        start_idx = int(non_silent[0])
        end_idx = int(non_silent[-1]) + 1

        # Keep a slight margin (20ms) so attack / release isn't chopped
        margin = int(sr * 0.02)
        start_idx = max(0, start_idx - margin)
        end_idx = min(len(data), end_idx + margin)

        start_trimmed_sec = round(start_idx / sr, 3)
        end_trimmed_sec = round((len(data) - end_idx) / sr, 3)

        trimmed_data = data[start_idx:end_idx]
        out_p.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_p), trimmed_data, sr)
        return True, start_trimmed_sec, end_trimmed_sec

    except Exception as e:
        logger.error(f"[AudioAnalyzer] Silence trim failed for {in_p}: {e}")
        return False, 0.0, 0.0


def apply_analog_drift(
    audio_data: np.ndarray,
    drift_rate: float = 1.0015
) -> np.ndarray:
    """
    Applies microscopic analog tape varispeed (0.15% speed/pitch drift via bandlimited sinc-resampling)
    to disrupt deterministic AI spectral hash matches without phase-vocoder artifacts or vocal smearing.
    audio_data: shape (channels, samples) or (samples,) float32
    """
    try:
        # Clamp drift rate to ultra-safe subtle values (0.998 to 1.002)
        rate = float(np.clip(drift_rate, 0.997, 1.003))
        if abs(rate - 1.0) < 0.0001:
            return audio_data

        # True analog tape varispeed: sinc interpolation preserves 100% stereo phase coherence,
        # zero comb-filtering, razor-sharp transients, and no "hollow barrel" vocal coloration.
        import resampy
        sr_nominal = 100000
        sr_drifted = int(round(sr_nominal * rate))
        
        drifted = resampy.resample(audio_data, sr_drifted, sr_nominal, axis=-1, filter='kaiser_fast')
        return drifted.astype(np.float32)
    except Exception as e:
        logger.warning(f"[AudioAnalyzer] Analog drift error, keeping original: {e}")
        return audio_data
