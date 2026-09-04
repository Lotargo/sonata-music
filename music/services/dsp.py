import os
from pathlib import Path
import logging
import soundfile as sf
import numpy as np
import resampy
from pydub import AudioSegment
from pedalboard import (
    Pedalboard,
    Compressor,
    Limiter,
    HighpassFilter,
    HighShelfFilter,
    LowShelfFilter,
    PeakFilter,
    Gain,
    NoiseGate,
    Distortion,
    Reverb,
)

logger = logging.getLogger(__name__)


class StudioDSP:
    def __init__(self):
        # Define default parameter sets for presets
        self.preset_configs = {
            "mastering": {
                "reverb_enabled": False,
                "bass_boost": 0.0,
                "voice_clarity": 0.0,
                "compressor_amount": 0.5,  # 0-1 scale
                "stereo_width": 1.0,
                "target_lufs": -14.0,
            },
            "punchy": {
                "reverb_enabled": False,
                "bass_boost": 4.0,
                "voice_clarity": 2.0,
                "compressor_amount": 0.8,
                "stereo_width": 1.0,
                "target_lufs": -9.0,
            },
            "deep_bass": {
                "reverb_enabled": False,
                "bass_boost": 6.0,
                "voice_clarity": 1.5,
                "compressor_amount": 0.6,
                "stereo_width": 1.0,
                "target_lufs": -12.0,
            },
            "clear": {
                "reverb_enabled": False,
                "bass_boost": -2.0,
                "voice_clarity": 5.0,
                "compressor_amount": 0.4,
                "stereo_width": 1.1,
                "target_lufs": -14.0,
            },
            "warm": {
                "reverb_enabled": True,
                "reverb_size": 0.3,
                "reverb_amount": 0.1,
                "bass_boost": 2.0,
                "voice_clarity": -1.0,
                "compressor_amount": 0.6,
                "stereo_width": 0.9,
                "target_lufs": -14.0,
            },
            "stealth": {
                "reverb_enabled": False,
                "bass_boost": 0.5,
                "voice_clarity": 1.0,
                "compressor_amount": 0.55,
                "stereo_width": 1.15,
                "target_lufs": -14.0,
            },
        }

    def _apply_stereo_width(self, audio, width):
        """
        Apply Mid-Side stereo widening using NumPy.
        Audio is (channels, samples).
        """
        if audio.shape[0] != 2:
            return audio  # Cannot widen mono

        # 1 = Normal, <1 = Narrow, >1 = Wide
        if width == 1.0:
            return audio

        mid = (audio[0] + audio[1]) * 0.5
        side = (audio[0] - audio[1]) * 0.5

        side *= width

        left = mid + side
        right = mid - side

        return np.stack([left, right])

    def _read_audio_file(self, filepath):
        """
        Robustly reads an audio file.
        Prioritizes soundfile for speed and float32 quality.
        Falls back to pydub (FFmpeg) if soundfile fails or returns silence.
        Returns: (audio_data_np, sample_rate)
        Audio data is (channels, samples) float32 [-1, 1]
        """
        try:
            # 1. Try soundfile
            try:
                data, sr = sf.read(filepath)
                # Check for absolute silence (zeros) which might indicate decode failure
                if np.max(np.abs(data)) == 0:
                    logger.warning(
                        f"Soundfile read silence for {filepath}. Trying pydub..."
                    )
                    raise ValueError("Silent file")

                # Check for near-silence (extremely low RMS) that is effectively useless
                # RMS of a sine wave with amplitude 1.0 is 0.707.
                # -90dB is approx 0.00003
                rms = np.sqrt(np.mean(data**2))
                if rms < 1e-6: # -120dB
                     logger.warning(
                        f"Soundfile read near-silence (RMS {rms}) for {filepath}. Trying pydub..."
                    )
                     raise ValueError("Near-silent file")

                # Shape handling: (samples, channels) -> (channels, samples)
                if data.ndim == 1:
                    data = data[np.newaxis, :]
                else:
                    data = data.T

                return data.astype(np.float32), sr
            except Exception as e:
                logger.warning(
                    f"Soundfile failed ({e}), falling back to pydub for {filepath}"
                )

                # 2. Fallback to pydub
                audio = AudioSegment.from_file(filepath)
                sr = audio.frame_rate

                # Convert to numpy float32
                # get_array_of_samples returns standard array.array of integers
                raw_data = np.array(audio.get_array_of_samples())

                if audio.channels == 2:
                    raw_data = raw_data.reshape((-1, 2)).T
                else:
                    raw_data = raw_data[np.newaxis, :]

                # Normalize based on sample width
                if audio.sample_width == 2:  # 16-bit
                    raw_data = raw_data.astype(np.float32) / 32768.0
                elif audio.sample_width == 4:  # 32-bit
                    raw_data = raw_data.astype(np.float32) / 2147483648.0
                elif audio.sample_width == 1:  # 8-bit unsigned
                    raw_data = (raw_data.astype(np.float32) - 128) / 128.0
                else:
                    # 24-bit (3 bytes) usually handled by pydub as 32-bit int with padding or just bytes
                    # pydub support for 24-bit is sometimes tricky, but usually works via ffmpeg
                    # Fallback generic normalization
                    max_val = np.max(np.abs(raw_data))
                    if max_val > 0:
                        raw_data = raw_data.astype(np.float32) / max_val

                # Post-pydub silence check
                if np.max(np.abs(raw_data)) == 0:
                     raise ValueError("Audio file is completely silent after pydub decode.")

                rms = np.sqrt(np.mean(raw_data**2))
                if rms < 1e-6:
                     raise ValueError(f"Audio file is near-silent (RMS {rms}) after pydub decode.")

                return raw_data, sr

        except Exception as e:
            logger.error(f"All audio read attempts failed for {filepath}: {e}")
            raise e

    def build_chain(self, params):
        board = Pedalboard()

        # 1. Cleanup Highpass
        board.append(HighpassFilter(cutoff_frequency_hz=30))

        # 2. EQ: Bass Boost
        bass_db = params.get("bass_boost", 0.0)
        if bass_db != 0:
            # "Soft Bass" Logic: If boosting, use lower freq (60Hz) for depth instead of punch (100Hz)
            # and add subtle saturation for warmth.
            if bass_db > 0:
                board.append(LowShelfFilter(cutoff_frequency_hz=60, gain_db=bass_db))

                # "Mud Cut": If boosting heavily (>3dB), cut 250Hz to prevent boxiness/mud
                if bass_db > 3.0:
                    board.append(
                        PeakFilter(cutoff_frequency_hz=250, gain_db=-2.5, q=1.0)
                    )

                # Add "Tube" warmth (saturation) to bass
                board.append(Distortion(drive_db=0.3))
            else:
                # Cutting bass: Use standard 100Hz to remove mud/punch
                board.append(LowShelfFilter(cutoff_frequency_hz=100, gain_db=bass_db))

        # 3. EQ: Voice Clarity
        # Combination of cut in mud (300Hz) and boost in presence (3-5kHz)
        clarity = params.get("voice_clarity", 0.0)
        if clarity != 0:
            # "Clarity" is an abstract 0-10 or dB scale? Let's assume input is roughly dB-like or 0-5 scale.
            # Cut mud
            board.append(
                PeakFilter(cutoff_frequency_hz=300, gain_db=-(clarity * 0.5), q=1.0)
            )
            # Boost presence
            board.append(PeakFilter(cutoff_frequency_hz=4000, gain_db=clarity, q=0.7))
            # Air
            board.append(
                HighShelfFilter(cutoff_frequency_hz=10000, gain_db=clarity * 0.5)
            )

        # 4. Compressor
        # Map 0-1 "amount" to Threshold/Ratio
        comp_amt = params.get("compressor_amount", 0.0)
        if comp_amt > 0:
            # Threshold: -8dB to -24dB (Gentler start)
            threshold = -8 - (comp_amt * 16)
            # Ratio: 1.5:1 to 4:1 (Mastering grade)
            ratio = 1.5 + (comp_amt * 2.5)
            # Attack: 30ms (Preserve transients/punch)
            # Release: 250ms (Smooth response, prevents distortion)
            board.append(
                Compressor(
                    threshold_db=threshold, ratio=ratio, attack_ms=30, release_ms=250
                )
            )

        # 5. Reverb
        if params.get("reverb_enabled", False):
            room_size = params.get("reverb_size", 0.5)  # 0-1
            wet_level = params.get("reverb_amount", 0.3)  # 0-1
            # Pedalboard Reverb: room_size (0-1), wet_level (0-1), dry_level (0-1)
            board.append(
                Reverb(room_size=room_size, wet_level=wet_level, dry_level=1.0)
            )

        # 6. Limiter (Safety)
        # Pedalboard Limiter caps at 0dB. We add Gain to enforce -1.0 dB safety ceiling.
        board.append(Limiter(threshold_db=-1.0))
        board.append(Gain(gain_db=-1.0))

        return board

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
        params: dict of specific settings. If None, uses preset_name to load defaults.
        """
        logger.info(f"Starting DSP processing. Preset: {preset_name}, Params: {params}")

        try:
            # 1. Resolve Parameters
            # Start with preset defaults
            config = self.preset_configs.get(
                preset_name, self.preset_configs["mastering"]
            ).copy()
            # Overlay custom params if provided
            if params:
                for k, v in params.items():
                    if v is not None:
                        config[k] = v

            # 2. Read Audio (Use Robust Reader)
            try:
                audio, sr = self._read_audio_file(input_path)
            except Exception as e:
                logger.error(f"Failed to read file: {e}")
                raise e

            # Pre-gain: Reduce input by -3dB to -6dB to create headroom before processing
            # Instead of normalizing UP to -6dB (which boosts quiet tracks), we just attenuate.
            # If the track is already loud (0dB), this brings it to -3dB.
            audio = audio * 0.707  # -3dB attenuation

            # 3. Resample
            if sr != sample_rate:
                logger.info(f"Resampling from {sr} to {sample_rate} Hz...")
                audio = resampy.resample(audio, sr, sample_rate, axis=1)
                sr = sample_rate

            # 4. Apply Stereo Widener (NumPy)
            width = float(config.get("stereo_width", 1.0))
            if width != 1.0:
                audio = self._apply_stereo_width(audio, width)

            # 5. Apply Pedalboard Chain
            board = self.build_chain(config)
            processed = board(audio, sample_rate)

            # 6. Save
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Determine subtype (no easy way to pass this via params currently without changing signature massively)
            # Default to 24-bit for internal DSP
            sf.write(output_path, processed.T, sample_rate, subtype="PCM_24")

            logger.info("DSP processing complete.")
            return True

        except Exception as e:
            logger.error(f"DSP processing failed: {e}")
            raise e

    def process_stems(self, stems_map, output_path, params=None, sample_rate=48000):
        """
        Process separated stems individually and recombine.
        stems_map: {'vocals': path, 'drums': path, 'bass': path, 'other': path}
        """
        logger.info(f"Starting Hybrid Stem Processing. Params: {params}")

        try:
            # Load stems
            loaded_stems = {}
            max_len = 0

            for name, path in stems_map.items():
                # Use Robust Reader
                data, sr = self._read_audio_file(path)

                # Resample if needed
                if sr != sample_rate:
                    data = resampy.resample(data, sr, sample_rate, axis=1)

                loaded_stems[name] = data
                if data.shape[1] > max_len:
                    max_len = data.shape[1]

            # Pad all to max_len
            for name in loaded_stems:
                curr = loaded_stems[name]
                if curr.shape[1] < max_len:
                    pad = np.zeros(
                        (curr.shape[0], max_len - curr.shape[1]), dtype=np.float32
                    )
                    loaded_stems[name] = np.concatenate([curr, pad], axis=1)

            # --- Define Chains ---

            # 1. Vocals Chain: Clear up harshness, add air, gentle compression
            vocals_board = Pedalboard()
            vocals_board.append(HighpassFilter(cutoff_frequency_hz=90))  # Cut rumble
            # Cut harshness in 3-4kHz range (common in Suno/AI)
            vocals_board.append(
                PeakFilter(cutoff_frequency_hz=3500, gain_db=-2.5, q=1.5)
            )
            # Gentle Air boost
            vocals_board.append(HighShelfFilter(cutoff_frequency_hz=12000, gain_db=1.5))
            # Vocal Compressor (Fast attack to catch peaks)
            vocals_board.append(
                Compressor(threshold_db=-16, ratio=2.5, attack_ms=5, release_ms=100)
            )

            # 2. Drums/Bass Chain: Punch and Depth
            rhythm_board = Pedalboard()
            bass_boost = params.get("bass_boost", 0.0) if params else 0.0
            # Only apply boost if explicitly requested.
            # Default "Balanced" preset usually has 0.0, so this stays neutral.
            if bass_boost > 0:
                rhythm_board.append(
                    LowShelfFilter(cutoff_frequency_hz=80, gain_db=bass_boost)
                )
            elif bass_boost < 0:
                rhythm_board.append(
                    LowShelfFilter(cutoff_frequency_hz=80, gain_db=bass_boost)
                )

            # Removed commented-out Distortion to ensure no accidental saturation

            # 3. Other (Synths) Chain: Width
            # (Handled via widener function usually, but we can do simple EQ here)
            other_board = Pedalboard()
            other_board.append(
                HighpassFilter(cutoff_frequency_hz=150)
            )  # Clean space for bass

            # --- Process ---

            # Process Vocals
            if "vocals" in loaded_stems:
                loaded_stems["vocals"] = vocals_board(
                    loaded_stems["vocals"], sample_rate
                )

            # Process Drums
            if "drums" in loaded_stems:
                loaded_stems["drums"] = rhythm_board(loaded_stems["drums"], sample_rate)

            # Process Bass
            if "bass" in loaded_stems:
                loaded_stems["bass"] = rhythm_board(loaded_stems["bass"], sample_rate)

            # Process Other
            if "other" in loaded_stems:
                loaded_stems["other"] = other_board(loaded_stems["other"], sample_rate)
                # Widen 'other' specifically
                loaded_stems["other"] = self._apply_stereo_width(
                    loaded_stems["other"], 1.2
                )

            # --- Mix ---
            # Simple summation
            mix = np.zeros((2, max_len), dtype=np.float32)
            for name, audio in loaded_stems.items():
                # Ensure stereo
                if audio.shape[0] == 1:
                    audio = np.concatenate([audio, audio], axis=0)
                mix += audio

            # Apply Headroom (Gain Staging) before Master Chain
            # Reduce mix to prevent limiter "choking".
            # -3dB (0.707) provides standard safety headroom now that inputs are natural volume.
            # (Dynamic Envelope Matching in upscaler will restore volume later, so we can be safe here)
            mix = mix * 0.707

            # Apply Master Glue (The "Balanced" chain we just fixed)
            # Use provided params or default to mastering
            master_config = self.preset_configs["mastering"].copy()
            if params:
                for k, v in params.items():
                    if v is not None:
                        master_config[k] = v

            # Remove bass boost from master since we applied it to stems
            master_config["bass_boost"] = 0.0

            master_board = self.build_chain(master_config)
            final_mix = master_board(mix, sample_rate)

            # Return the audio data instead of saving, so upscaler can do Envelope Matching
            return final_mix

        except Exception as e:
            logger.error(f"Hybrid stem processing failed: {e}")
            raise e

    def apply_stealth_restoration(self, audio, sample_rate, params=None):
        """
        Applies a 'Stealth / Anti-AI' restoration chain specifically designed to de-mask
        Suno/Udio artifacts, eliminate metallic harshness, cut mud, and destroy acoustic signatures.
        Chain: De-mud EQ, De-harsh EQ, Air Exciter, Stereo Widen, Glue Compressor, Warm Tape Floor.
        """
        logger.info("Applying Stealth / Anti-AI Restoration Chain...")

        try:
            # Ensure audio is (channels, samples)
            if audio.ndim == 1:
                audio = audio[np.newaxis, :]

            # Pre-gain: -3dB attenuation for headroom
            audio = audio * 0.707

            # 1. Apply Stereo Widener First (NumPy)
            audio = self._apply_stereo_width(audio, 1.15)

            # 2. Build Pedalboard Chain
            board = Pedalboard()

            # --- EQ: Cleanup & De-mud ---
            board.append(HighpassFilter(cutoff_frequency_hz=30))
            # Cut "Mud" / Boxiness (320-380Hz common in Suno/Udio generation)
            board.append(PeakFilter(cutoff_frequency_hz=350, gain_db=-2.5, q=1.0))

            # --- EQ: De-harsh (Cut metallic digital ring on AI vocals/instruments) ---
            board.append(PeakFilter(cutoff_frequency_hz=4000, gain_db=-2.0, q=1.2))

            # --- EQ: Air & Presence ---
            board.append(HighShelfFilter(cutoff_frequency_hz=10000, gain_db=1.5))

            # --- Harmonic Exciter ---
            board.append(Distortion(drive_db=0.4))

            # --- Glue Compressor ---
            board.append(
                Compressor(
                    threshold_db=-12,
                    ratio=2.5,
                    attack_ms=15,
                    release_ms=150,
                )
            )

            # --- Safety Limiter ---
            board.append(Limiter(threshold_db=-1.0))
            board.append(Gain(gain_db=-1.0))

            # 3. Process
            processed = board(audio, sample_rate)

            # 4. Warm Analog Tape Noise Floor (-68 dB)
            # Breaks mathematical silence in pauses without being perceptibly noisy to listeners
            noise_gain = 10.0 ** (-68.0 / 20.0)
            tape_noise = np.random.normal(0, noise_gain, processed.shape).astype(np.float32)
            processed = processed + tape_noise

            return processed

        except Exception as e:
            logger.error(f"Stealth restoration polish failed: {e}")
            raise e

    def apply_suno_restoration(self, audio, sample_rate, params=None):
        """Backward compatibility alias pointing to apply_stealth_restoration."""
        return self.apply_stealth_restoration(audio, sample_rate, params=params)


# Create singleton
dsp = StudioDSP()
