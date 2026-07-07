import logging
import os

import numpy as np
import resampy
import soundfile as sf
from pedalboard import (
    Compressor,
    Distortion,
    Gain,
    HighShelfFilter,
    HighpassFilter,
    Limiter,
    LowShelfFilter,
    PeakFilter,
    Pedalboard,
    Reverb,
)
from pydub import AudioSegment

from music.services.audio_loudness import apply_gain_db, normalize_loudness, peak_limit

logger = logging.getLogger(__name__)


class StudioDSP:
    def __init__(self):
        # Presets are product-level intent, not just raw effect values.
        # target_lufs is now applied after the effect chain.
        self.preset_configs = {
            "ai_prep": {
                "reverb_enabled": False,
                "bass_boost": 0.0,
                "voice_clarity": 0.5,
                "compressor_amount": 0.15,
                "stereo_width": 1.0,
                "pre_gain_db": -6.0,
                "target_lufs": -18.0,
                "peak_ceiling_db": -1.5,
            },
            "mastering": {
                "reverb_enabled": False,
                "bass_boost": 0.0,
                "voice_clarity": 0.0,
                "compressor_amount": 0.5,
                "stereo_width": 1.0,
                "pre_gain_db": -3.0,
                "target_lufs": -14.0,
                "peak_ceiling_db": -1.0,
            },
            "punchy": {
                "reverb_enabled": False,
                "bass_boost": 4.0,
                "voice_clarity": 2.0,
                "compressor_amount": 0.8,
                "stereo_width": 1.0,
                "pre_gain_db": -4.0,
                "target_lufs": -9.0,
                "peak_ceiling_db": -1.0,
            },
            "deep_bass": {
                "reverb_enabled": False,
                "bass_boost": 6.0,
                "voice_clarity": 1.5,
                "compressor_amount": 0.6,
                "stereo_width": 1.0,
                "pre_gain_db": -4.0,
                "target_lufs": -12.0,
                "peak_ceiling_db": -1.0,
            },
            "clear": {
                "reverb_enabled": False,
                "bass_boost": -2.0,
                "voice_clarity": 5.0,
                "compressor_amount": 0.4,
                "stereo_width": 1.1,
                "pre_gain_db": -3.0,
                "target_lufs": -14.0,
                "peak_ceiling_db": -1.0,
            },
            "warm": {
                "reverb_enabled": True,
                "reverb_size": 0.3,
                "reverb_amount": 0.1,
                "bass_boost": 2.0,
                "voice_clarity": -1.0,
                "compressor_amount": 0.6,
                "stereo_width": 0.9,
                "pre_gain_db": -3.0,
                "target_lufs": -14.0,
                "peak_ceiling_db": -1.0,
            },
        }

    def _apply_stereo_width(self, audio, width):
        """
        Apply Mid-Side stereo widening using NumPy.
        Audio is (channels, samples).
        """
        if audio.shape[0] != 2:
            return audio

        width = float(width)
        if width == 1.0:
            return audio

        mid = (audio[0] + audio[1]) * 0.5
        side = (audio[0] - audio[1]) * 0.5
        side *= width

        left = mid + side
        right = mid - side
        return np.stack([left, right]).astype(np.float32)

    def _read_audio_file(self, filepath):
        """
        Robustly reads an audio file.
        Prioritizes soundfile for speed and float32 quality.
        Falls back to pydub/FFmpeg if soundfile fails or returns silence.
        Returns: (audio_data_np, sample_rate), shaped as (channels, samples).
        """
        try:
            data, sr = sf.read(filepath, dtype="float32")

            if np.max(np.abs(data)) == 0:
                raise ValueError("Soundfile decoded silence")

            rms = float(np.sqrt(np.mean(data**2) + 1e-12))
            if rms < 1e-6:
                raise ValueError(f"Soundfile decoded near-silence (RMS {rms})")

            if data.ndim == 1:
                data = data[np.newaxis, :]
            else:
                data = data.T

            return data.astype(np.float32), sr

        except Exception as sf_error:
            logger.warning(
                "Soundfile failed (%s), falling back to pydub for %s",
                sf_error,
                filepath,
            )

        try:
            audio = AudioSegment.from_file(filepath)
            sr = audio.frame_rate
            raw_data = np.array(audio.get_array_of_samples())

            if audio.channels == 2:
                raw_data = raw_data.reshape((-1, 2)).T
            else:
                raw_data = raw_data[np.newaxis, :]

            if audio.sample_width == 2:
                raw_data = raw_data.astype(np.float32) / 32768.0
            elif audio.sample_width == 4:
                raw_data = raw_data.astype(np.float32) / 2147483648.0
            elif audio.sample_width == 1:
                raw_data = (raw_data.astype(np.float32) - 128) / 128.0
            else:
                max_val = float(np.max(np.abs(raw_data)))
                if max_val > 0:
                    raw_data = raw_data.astype(np.float32) / max_val

            if np.max(np.abs(raw_data)) == 0:
                raise ValueError("Audio file is completely silent after pydub decode")

            rms = float(np.sqrt(np.mean(raw_data**2) + 1e-12))
            if rms < 1e-6:
                raise ValueError(f"Audio file is near-silent after pydub decode (RMS {rms})")

            return raw_data.astype(np.float32), sr

        except Exception as pydub_error:
            logger.error("All audio read attempts failed for %s: %s", filepath, pydub_error)
            raise pydub_error

    def _resolve_config(self, preset_name="mastering", params=None):
        config = self.preset_configs.get(preset_name, self.preset_configs["mastering"]).copy()
        if params:
            for key, value in params.items():
                if value is not None:
                    config[key] = value
        return config

    def build_chain(self, params):
        board = Pedalboard()

        # 1. Cleanup Highpass
        board.append(HighpassFilter(cutoff_frequency_hz=30))

        # 2. EQ: Bass Boost / Cut
        bass_db = float(params.get("bass_boost", 0.0))
        if bass_db != 0.0:
            if bass_db > 0:
                board.append(LowShelfFilter(cutoff_frequency_hz=60, gain_db=bass_db))
                if bass_db > 3.0:
                    board.append(PeakFilter(cutoff_frequency_hz=250, gain_db=-2.5, q=1.0))
                board.append(Distortion(drive_db=0.3))
            else:
                board.append(LowShelfFilter(cutoff_frequency_hz=100, gain_db=bass_db))

        # 3. EQ: Voice Clarity
        clarity = float(params.get("voice_clarity", 0.0))
        if clarity != 0.0:
            board.append(PeakFilter(cutoff_frequency_hz=300, gain_db=-(clarity * 0.5), q=1.0))
            board.append(PeakFilter(cutoff_frequency_hz=4000, gain_db=clarity, q=0.7))
            board.append(HighShelfFilter(cutoff_frequency_hz=10000, gain_db=clarity * 0.5))

        # 4. Compressor
        comp_amt = float(params.get("compressor_amount", 0.0))
        if comp_amt > 0.0:
            threshold = -8 - (comp_amt * 16)
            ratio = 1.5 + (comp_amt * 2.5)
            board.append(
                Compressor(
                    threshold_db=threshold,
                    ratio=ratio,
                    attack_ms=30,
                    release_ms=250,
                )
            )

        # 5. Reverb
        if params.get("reverb_enabled", False):
            room_size = float(params.get("reverb_size", 0.5))
            wet_level = float(params.get("reverb_amount", 0.3))
            board.append(Reverb(room_size=room_size, wet_level=wet_level, dry_level=1.0))

        # 6. Safety ceiling before loudness compensation.
        board.append(Limiter(threshold_db=float(params.get("peak_ceiling_db", -1.0))))
        board.append(Gain(gain_db=-0.3))

        return board

    def _post_process_loudness(self, audio, sample_rate, config):
        return normalize_loudness(
            audio,
            sample_rate,
            target_lufs=config.get("target_lufs"),
            peak_ceiling_db=float(config.get("peak_ceiling_db", -1.0)),
        )

    def process(
        self,
        input_path,
        output_path,
        params=None,
        preset_name="mastering",
        sample_rate=48000,
    ):
        """
        Process audio with DSP.
        params: dict of specific settings. If None, uses preset_name defaults.
        """
        logger.info("Starting DSP processing. Preset: %s, Params: %s", preset_name, params)

        try:
            config = self._resolve_config(preset_name, params)
            audio, sr = self._read_audio_file(input_path)

            # Conservative pre-gain creates real headroom before EQ/compression.
            audio = apply_gain_db(audio, float(config.get("pre_gain_db", -3.0)))

            if sr != sample_rate:
                logger.info("Resampling from %s to %s Hz...", sr, sample_rate)
                audio = resampy.resample(audio, sr, sample_rate, axis=1).astype(np.float32)
                sr = sample_rate

            width = float(config.get("stereo_width", 1.0))
            audio = self._apply_stereo_width(audio, width)

            board = self.build_chain(config)
            processed = board(audio, sample_rate)
            processed = self._post_process_loudness(processed, sample_rate, config)

            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            sf.write(output_path, processed.T, sample_rate, subtype="PCM_24")
            logger.info("DSP processing complete.")
            return True

        except Exception as e:
            logger.error("DSP processing failed: %s", e)
            raise e

    def process_stems(self, stems_map, output_path, params=None, sample_rate=48000):
        """
        Process separated stems individually and recombine.
        stems_map: {'vocals': path, 'drums': path, 'bass': path, 'other': path}
        """
        logger.info("Starting Hybrid Stem Processing. Params: %s", params)

        try:
            loaded_stems = {}
            max_len = 0

            for name, path in stems_map.items():
                data, sr = self._read_audio_file(path)
                if sr != sample_rate:
                    data = resampy.resample(data, sr, sample_rate, axis=1).astype(np.float32)

                loaded_stems[name] = data
                max_len = max(max_len, data.shape[1])

            for name, curr in list(loaded_stems.items()):
                if curr.shape[1] < max_len:
                    pad = np.zeros((curr.shape[0], max_len - curr.shape[1]), dtype=np.float32)
                    loaded_stems[name] = np.concatenate([curr, pad], axis=1)

            vocals_board = Pedalboard()
            vocals_board.append(HighpassFilter(cutoff_frequency_hz=90))
            vocals_board.append(PeakFilter(cutoff_frequency_hz=3500, gain_db=-2.5, q=1.5))
            vocals_board.append(HighShelfFilter(cutoff_frequency_hz=12000, gain_db=1.5))
            vocals_board.append(Compressor(threshold_db=-16, ratio=2.5, attack_ms=5, release_ms=100))

            rhythm_board = Pedalboard()
            bass_boost = float(params.get("bass_boost", 0.0)) if params else 0.0
            if bass_boost != 0.0:
                rhythm_board.append(LowShelfFilter(cutoff_frequency_hz=80, gain_db=bass_boost))

            other_board = Pedalboard()
            other_board.append(HighpassFilter(cutoff_frequency_hz=150))

            if "vocals" in loaded_stems:
                loaded_stems["vocals"] = vocals_board(loaded_stems["vocals"], sample_rate)
            if "drums" in loaded_stems:
                loaded_stems["drums"] = rhythm_board(loaded_stems["drums"], sample_rate)
            if "bass" in loaded_stems:
                loaded_stems["bass"] = rhythm_board(loaded_stems["bass"], sample_rate)
            if "other" in loaded_stems:
                loaded_stems["other"] = other_board(loaded_stems["other"], sample_rate)
                loaded_stems["other"] = self._apply_stereo_width(loaded_stems["other"], 1.2)

            mix = np.zeros((2, max_len), dtype=np.float32)
            for audio in loaded_stems.values():
                if audio.shape[0] == 1:
                    audio = np.concatenate([audio, audio], axis=0)
                mix += audio[:2, :max_len]

            mix = apply_gain_db(mix, -3.0)

            master_config = self.preset_configs["mastering"].copy()
            if params:
                for key, value in params.items():
                    if value is not None:
                        master_config[key] = value
            master_config["bass_boost"] = 0.0

            master_board = self.build_chain(master_config)
            final_mix = master_board(mix, sample_rate)
            final_mix = self._post_process_loudness(final_mix, sample_rate, master_config)
            return final_mix

        except Exception as e:
            logger.error("Hybrid stem processing failed: %s", e)
            raise e

    def apply_suno_restoration(self, audio, sample_rate, params=None):
        """
        Applies an enhancement chain for Suno/MP3 restoration.
        Chain: de-mud EQ, subtle exciter, stereo widening, glue compressor, loudness safety.
        """
        logger.info("Applying Suno Restoration Chain...")

        try:
            if audio.ndim == 1:
                audio = audio[np.newaxis, :]

            config = {
                "target_lufs": -14.0,
                "peak_ceiling_db": -1.0,
            }
            if params:
                config.update({k: v for k, v in params.items() if v is not None})

            audio = apply_gain_db(audio, -3.0)
            audio = self._apply_stereo_width(audio, 1.15)

            board = Pedalboard()
            board.append(HighpassFilter(cutoff_frequency_hz=30))
            board.append(PeakFilter(cutoff_frequency_hz=350, gain_db=-2.5, q=1.0))
            board.append(HighShelfFilter(cutoff_frequency_hz=10000, gain_db=1.5))
            board.append(Distortion(drive_db=0.5))
            board.append(
                Compressor(
                    threshold_db=-12,
                    ratio=2.5,
                    attack_ms=15,
                    release_ms=150,
                )
            )
            board.append(Limiter(threshold_db=-1.0))
            board.append(Gain(gain_db=-0.3))

            processed = board(audio, sample_rate)
            processed = normalize_loudness(
                processed,
                sample_rate,
                target_lufs=config.get("target_lufs"),
                peak_ceiling_db=float(config.get("peak_ceiling_db", -1.0)),
            )
            return peak_limit(processed, ceiling_db=float(config.get("peak_ceiling_db", -1.0)))

        except Exception as e:
            logger.error("Suno restoration polish failed: %s", e)
            raise e


# Create singleton
dsp = StudioDSP()
