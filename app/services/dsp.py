import os
import logging
import soundfile as sf
import numpy as np
import resampy
from pedalboard import (
    Pedalboard,
    Compressor,
    Limiter,
    HighpassFilter,
    HighShelfFilter,
    PeakFilter,
    Gain,
    NoiseGate,
    Distortion
)

logger = logging.getLogger(__name__)

class StudioDSP:
    def __init__(self):
        self.presets = {
            "mastering": self._build_mastering_chain,
            "clear": self._build_clear_chain,
            "warm": self._build_warm_chain,
            "punchy": self._build_punchy_chain
        }

    def _build_mastering_chain(self):
        """Standard professional mastering chain."""
        return Pedalboard([
            HighpassFilter(cutoff_frequency_hz=30),
            # "Exciter" - boost air
            HighShelfFilter(cutoff_frequency_hz=10000, gain_db=2.0),
            # Compressor to glue (transparent)
            Compressor(threshold_db=-12, ratio=2.5, attack_ms=10, release_ms=100),
            # Limiter for safety
            Limiter(threshold_db=-0.1)
        ])

    def _build_clear_chain(self):
        """Focus on clarity, vocal presence, and de-mudding."""
        return Pedalboard([
            HighpassFilter(cutoff_frequency_hz=50),
            # Cut mud
            PeakFilter(cutoff_frequency_hz=300, gain_db=-2.5, q=1.0),
            # Boost presence
            PeakFilter(cutoff_frequency_hz=3000, gain_db=2.0, q=0.7),
            HighShelfFilter(cutoff_frequency_hz=8000, gain_db=3.0),
            Compressor(threshold_db=-15, ratio=3, attack_ms=5, release_ms=50),
            Limiter(threshold_db=-0.1)
        ])

    def _build_warm_chain(self):
        """Vintage vibe, tube distortion, reduced highs."""
        return Pedalboard([
            HighpassFilter(cutoff_frequency_hz=30),
            # Warmth
            PeakFilter(cutoff_frequency_hz=200, gain_db=2.0, q=0.8),
            # Soften highs
            HighShelfFilter(cutoff_frequency_hz=12000, gain_db=-2.0),
            # Tube-like distortion (very subtle)
            Distortion(drive_db=5.0),
            Compressor(threshold_db=-10, ratio=2, attack_ms=20, release_ms=200),
            Limiter(threshold_db=-0.1)
        ])

    def _build_punchy_chain(self):
        """Aggressive, drum-focused, bass-heavy."""
        return Pedalboard([
            HighpassFilter(cutoff_frequency_hz=40),
            # Thump
            PeakFilter(cutoff_frequency_hz=80, gain_db=3.0, q=1.0),
            # Snap
            PeakFilter(cutoff_frequency_hz=4000, gain_db=2.0, q=1.0),
            # Slow attack to let transients through, high ratio
            Compressor(threshold_db=-15, ratio=4, attack_ms=30, release_ms=100),
            Limiter(threshold_db=-0.1)
        ])

    def process(self, input_path, output_path, preset_name="mastering", sample_rate=48000):
        logger.info(f"Starting DSP processing: {input_path} -> {output_path} (Preset: {preset_name})")

        try:
            # 1. Read Audio
            try:
                data, sr = sf.read(input_path)
            except Exception as e:
                logger.error(f"Failed to read file with sf.read: {e}")
                raise e

            # Handle shape: sf returns (samples, channels) usually.
            # Pedalboard expects (channels, samples).
            if data.ndim == 1:
                # Mono: (samples,) -> (1, samples)
                data = data[np.newaxis, :]
            else:
                # Stereo: (samples, channels) -> (channels, samples)
                data = data.T

            # Convert to float32
            audio = data.astype(np.float32)

            # Normalize inputs to prevent clipping before processing if they are crazy loud?
            # Actually pedalboard works in float32 so headroom is fine.
            # But let's peak normalize to -3dB to give headroom for EQ boosts.
            max_val = np.max(np.abs(audio))
            if max_val > 0:
                target_peak = 10 ** (-3.0 / 20) # -3dB
                if max_val > target_peak:
                    audio = audio * (target_peak / max_val)

            # 2. Resample if needed
            if sr != sample_rate:
                logger.info(f"Resampling from {sr} to {sample_rate} Hz...")
                audio = resampy.resample(audio, sr, sample_rate, axis=1)
                sr = sample_rate

            # 3. Get Chain
            builder = self.presets.get(preset_name, self._build_mastering_chain)
            board = builder()

            # 4. Process
            # Board expects (channels, samples) and sample_rate
            processed = board(audio, sample_rate)

            # 5. Save
            # sf.write expects (samples, channels)
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            sf.write(output_path, processed.T, sample_rate, subtype='PCM_24')

            logger.info("DSP processing complete.")
            return True

        except Exception as e:
            logger.error(f"DSP processing failed: {e}")
            raise e

# Create singleton
dsp = StudioDSP()
