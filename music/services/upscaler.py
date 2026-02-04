import os
import torch
import torchaudio
import logging
import subprocess
import traceback
import tempfile
import gc
from audiosr.pipeline import (
    build_model,
    super_resolution,
    make_batch_for_super_resolution,
)

# Explicitly import where we need to patch
import audiosr.utils
import audiosr.pipeline
import soundfile as sf
import numpy as np
from pydub import AudioSegment
from tqdm import tqdm
from music.services.dsp import dsp
from music.services.separator import separator
from music.services.metrics import metrics_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Monkey-patch audiosr.utils.read_wav_file to be more robust
def safe_read_wav_file(filename):
    # Strictly use soundfile to avoid libtorchcodec issues
    try:
        data, sr = sf.read(filename)
        # soundfile returns (samples, channels) or (samples,)
        if data.ndim == 1:
            data = data[None, :]
        else:
            data = data.T  # Convert to (channels, samples)
        waveform = torch.from_numpy(data).float()
    except Exception as e:
        logger.error(f"sf.read failed in safe_read_wav_file: {e}")
        raise e

    duration = waveform.size(-1) / sr

    if duration > 10.24:
        logger.warning(
            f"Audio is {duration:.2f}s, which is longer than 10.24s. It will be truncated/chunked."
        )

    if duration % 5.12 != 0:
        pad_duration = duration + (5.12 - duration % 5.12)
    else:
        pad_duration = duration

    target_frame = int(pad_duration * 100)

    waveform = torchaudio.functional.resample(waveform, sr, 48000)

    # audiosr logic: take first channel (mono)
    # waveform shape is [channels, samples] -> .numpy()[0, ...] gets [samples,]
    waveform = waveform.numpy()[0, ...]

    waveform = audiosr.utils.normalize_wav(waveform)

    # pad_wav pads to target_length and returns numpy array
    waveform = waveform[None, ...]
    waveform = audiosr.utils.pad_wav(waveform, target_length=int(48000 * pad_duration))
    return waveform, target_frame, pad_duration


# Monkey-patch audiosr.lowpass.lowpass_filter to prevent Wn >= 1 crash
# This occurs if AudioSR tries to lowpass a signal at/near Nyquist
import audiosr.lowpass
from scipy.signal import ellip


# Correct signature from installed library: def lowpass_filter(x, highcut, fs, order, ftype):
# We use kwargs to be safe against future changes or variations
def safe_lowpass_filter(x, highcut=None, fs=None, order=6, ftype="ellip", **kwargs):
    # Map arguments to local names
    waveform = x
    cutoff_freq = highcut
    sample_rate = fs

    # Handle kwargs fallbacks if positional args were None (unlikely given signature, but robust)
    if cutoff_freq is None:
        cutoff_freq = kwargs.get("cutoff_freq", kwargs.get("cutoff"))
    if sample_rate is None:
        sample_rate = kwargs.get("sample_rate", kwargs.get("sr"))

    if waveform is None:
        raise ValueError("safe_lowpass_filter: x (waveform) must be provided.")
    if cutoff_freq is None:
        raise ValueError("safe_lowpass_filter: highcut (cutoff_freq) must be provided.")
    if sample_rate is None:
        raise ValueError("safe_lowpass_filter: fs (sample_rate) must be provided.")

    # Clamp cutoff to be strictly less than Nyquist
    nyquist = sample_rate / 2
    if cutoff_freq >= nyquist:
        # If cutoff is >= Nyquist, we clamp it to slightly below 1.0 (e.g. 0.99)
        # to prevent scipy.signal.ellip throwing ValueError: Digital filter critical frequencies must be 0 < Wn < 1
        logger.warning(
            f"Clamping lowpass cutoff {cutoff_freq} to 0.99*Nyquist ({0.99*nyquist}) to avoid crash."
        )
        cutoff_freq = 0.99 * nyquist

    # Original logic (copied/adapted from audiosr)
    # 0.1 dB ripple, 60 dB attenuation, order determined by ellip

    from scipy.signal import sosfilt

    Wn = cutoff_freq / nyquist
    if Wn >= 1:
        Wn = 0.99

    sos = ellip(order, 0.1, 60, Wn, btype="low", output="sos")

    # Apply to tensor (AudioSR expects tensor input/output usually?)
    # audiosr.lowpass.lowpass_filter takes torch.Tensor

    is_tensor = torch.is_tensor(waveform)
    if is_tensor:
        device = waveform.device
        dtype = waveform.dtype
        waveform_np = waveform.cpu().numpy()
    else:
        waveform_np = waveform

    filtered = sosfilt(sos, waveform_np, axis=-1)

    if is_tensor:
        return torch.from_numpy(filtered.copy()).to(device=device, dtype=dtype)
    return filtered


# Apply monkey patch to audiosr.lowpass
logger.info("Applying monkey-patch to audiosr.lowpass.lowpass_filter")
audiosr.lowpass.lowpass_filter = safe_lowpass_filter

# Apply monkey patch to audiosr.utils
logger.info("Applying monkey-patch to audiosr.utils.read_wav_file")
audiosr.utils.read_wav_file = safe_read_wav_file


class UpscalerService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.ffmpeg_available = self._check_ffmpeg()
        logger.info(
            f"UpscalerService initialized on {self.device}. FFmpeg available: {self.ffmpeg_available}"
        )

    def _check_ffmpeg(self):
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def _verify_audio_output(self, filepath):
        """Checks if the audio file exists, is readable, and is not silent."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Output file not found: {filepath}")

        if os.path.getsize(filepath) < 100:
            raise ValueError(
                f"Output file is too small ({os.path.getsize(filepath)} bytes): {filepath}"
            )

        try:
            data, sr = sf.read(filepath)
            if data is None or len(data) == 0:
                raise ValueError("Audio data is empty.")

            peak = np.max(np.abs(data))
            if peak < 1e-6:
                raise ValueError(f"Audio is silent (Peak: {peak}).")

            logger.info(
                f"Audio verification passed for {filepath}. Peak: {peak:.6f}, SR: {sr}"
            )
            return True
        except Exception as e:
            logger.error(f"Audio verification failed for {filepath}: {e}")
            raise e

    def load_model(self):
        if self.model is None:
            logger.info("Loading AudioSR model...")
            try:
                # "basic" is the default model.
                self.model = build_model(model_name="basic", device=self.device)
                logger.info("AudioSR model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load AudioSR model: {e}")
                raise e

    def _convert_format(self, input_wav, output_path, target_format, bitrate_str):
        """Helper to convert WAV to other formats using pydub."""
        logger.info(
            f"Converting to {target_format} (bitrate/depth: {bitrate_str}) using pydub"
        )
        audio = AudioSegment.from_wav(input_wav)

        format_map = {"mp3": "mp3", "flac": "flac", "ogg": "ogg", "vorbis": "ogg"}
        out_fmt = format_map.get(target_format.lower(), target_format.lower())

        # Handle Bitrate clamping for lossy formats
        if out_fmt in ["mp3", "ogg"]:
            # Parse numerical bitrate
            try:
                # Remove 'k' and convert to int
                kbps = int("".join(filter(str.isdigit, bitrate_str)))
            except ValueError:
                kbps = 320  # Default fallback

            # Clamp limits
            if out_fmt == "mp3":
                kbps = min(kbps, 320)
            elif out_fmt == "ogg":
                kbps = min(kbps, 500)

            final_bitrate = f"{kbps}k"
            logger.info(f"Exporting {out_fmt} with bitrate {final_bitrate}")
            audio.export(output_path, format=out_fmt, bitrate=final_bitrate)

        elif out_fmt == "flac":
            # FLAC is lossless, bitrate arg doesn't apply to compression level directly in pydub/ffmpeg simple interface
            # We just export as FLAC. Pydub doesn't expose sample_fmt easily for export,
            # but input was saved as 24-bit WAV if possible, so FLAC should retain high quality.
            logger.info(f"Exporting {out_fmt} (lossless)")
            audio.export(output_path, format=out_fmt)

        else:
            # Fallback
            audio.export(output_path, format=out_fmt)

        logger.info(f"Conversion complete: {output_path}")

    def unload_model(self):
        """Unloads the model and frees VRAM/RAM."""
        if self.model is not None:
            logger.info("Unloading AudioSR model to free resources...")
            del self.model
            self.model = None

        # Force garbage collection
        gc.collect()

        # Clear CUDA cache if applicable
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def _match_envelope(self, source, target, sr, window_ms=100):
        """
        Applies the amplitude envelope of the source (original) to the target (upscaled).
        Acts as the 'Parent' context enforcing dynamics on the 'Child'.
        """
        logger.info(f"Applying Global Envelope Matching (Window: {window_ms}ms)...")

        # Ensure target matches source length
        if source.shape[-1] != target.shape[-1]:
            min_len = min(source.shape[-1], target.shape[-1])
            source = source[..., :min_len]
            target = target[..., :min_len]

        window_size = int(sr * (window_ms / 1000.0))
        if window_size % 2 == 0:
            window_size += 1

        pad = window_size // 2

        # Helper to compute envelope
        def compute_envelope(waveform, win_size, padding):
            squared = waveform**2
            squared = squared.unsqueeze(0)
            envelope = torch.nn.functional.avg_pool1d(
                squared,
                kernel_size=win_size,
                stride=1,
                padding=padding,
                count_include_pad=False,
            )
            envelope = torch.sqrt(envelope + 1e-8)
            return envelope.squeeze(0)

        env_source = compute_envelope(source, window_size, pad)
        env_target = compute_envelope(target, window_size, pad)

        gain = env_source / (env_target + 1e-6)
        matched_waveform = target * gain

        return matched_waveform

    def _match_global_rms(self, source, target):
        """
        Matches the global RMS (loudness) of target to source.
        Does not affect dynamics (no pumping), just overall volume.
        """
        logger.info("Applying Global RMS Normalization...")

        # Calculate RMS
        rms_source = torch.sqrt(torch.mean(source**2) + 1e-8)
        rms_target = torch.sqrt(torch.mean(target**2) + 1e-8)

        gain = rms_source / (rms_target + 1e-6)

        # Apply gentle clamping to gain to prevent massive jumps if target is silent
        gain = torch.clamp(gain, 0.1, 10.0)

        logger.info(
            f"RMS Match: Source={rms_source:.4f}, Target={rms_target:.4f}, Gain={gain:.4f}"
        )
        return target * gain

    def _batched_super_resolution(self, input_files, ddim_steps, guidance_scale, seed):
        """
        Runs super_resolution on a batch of files to maximize GPU usage.
        """
        import audiosr.pipeline as pipeline

        # 1. Prepare batch
        pipeline.seed_everything(int(seed))

        batched_inputs = {
            "waveform": [],
            "stft": [],
            "log_mel_spec": [],
            "lowpass_mel": [],
            "waveform_lowpass": [],
            "sampling_rate": 48000,
        }

        max_duration = 5.12  # Standard for AudioSR

        for f in input_files:
            # make_batch_for_super_resolution returns (batch_dict, duration)
            # where each item in batch_dict is already unsqueezed [1, ...]
            mini_batch, _ = make_batch_for_super_resolution(f)

            for k in batched_inputs.keys():
                if k != "sampling_rate" and k in mini_batch:
                    batched_inputs[k].append(mini_batch[k])

        # Concatenate
        final_batch = {}
        for k in batched_inputs.keys():
            if k == "sampling_rate":
                final_batch[k] = batched_inputs[k]
            elif len(batched_inputs[k]) > 0:
                final_batch[k] = torch.cat(batched_inputs[k], dim=0)  # [B, ...]
                # Move to device
                final_batch[k] = final_batch[k].to(self.device)

        # 2. Run Inference
        if self.device == "cuda":
            with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                with torch.no_grad():
                    waveforms = self.model.generate_batch(
                        final_batch,
                        unconditional_guidance_scale=guidance_scale,
                        ddim_steps=ddim_steps,
                        duration=max_duration,
                    )
        else:
            with torch.no_grad():
                waveforms = self.model.generate_batch(
                    final_batch,
                    unconditional_guidance_scale=guidance_scale,
                    ddim_steps=ddim_steps,
                    duration=max_duration,
                )

        return waveforms  # [B, 1, samples]

    def _process_channel_waveform(
        self, waveform, sr, ddim_steps, guidance_scale, seed, batch_size=4
    ):
        """
        Processes a single-channel waveform using Overlap-Add (OLA) and Batching.
        """
        # Normalize waveform
        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val
        else:
            logger.warning("Audio appears to be silent (max value 0).")

        total_samples = waveform.shape[-1]

        # OLA Parameters
        segment_length_sec = 5.12
        segment_length = int(segment_length_sec * sr)
        overlap = 0.5
        stride = int(segment_length * (1 - overlap))

        # Calculate number of segments
        if total_samples <= segment_length:
            num_segments = 1
        else:
            num_segments = int(np.ceil((total_samples - segment_length) / stride)) + 1

        logger.info(
            f"Processing {num_segments} segments (OLA) with batch size {batch_size}..."
        )

        # Prepare output buffer and weight buffer
        output_waveform = torch.zeros_like(waveform)
        output_weights = torch.zeros_like(waveform)

        # Create Hanning window
        window = torch.hann_window(segment_length).to(waveform.device)

        segments_info = []  # List of (start, end, temp_file_path)

        try:
            # 1. Slice and Save all segments
            for i in range(num_segments):
                start = i * stride
                end = start + segment_length

                # Pad if last segment exceeds length
                segment = waveform[:, start:end]
                if segment.shape[-1] < segment_length:
                    pad_amt = segment_length - segment.shape[-1]
                    segment = torch.nn.functional.pad(segment, (0, pad_amt))

                # Save to temp
                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False
                ) as tmp_seg:
                    temp_seg_path = tmp_seg.name

                # Write
                sf.write(temp_seg_path, segment.T.numpy(), sr)
                segments_info.append(
                    {"start": start, "end": end, "path": temp_seg_path}
                )

            # 2. Process in Batches
            for i in tqdm(
                range(0, len(segments_info), batch_size),
                desc="Upscaling Batches",
                unit="batch",
            ):
                batch_files = [s["path"] for s in segments_info[i : i + batch_size]]

                try:
                    # Run batch inference
                    out_batch = self._batched_super_resolution(
                        batch_files, ddim_steps, guidance_scale, seed
                    )

                    # 3. Overlap-Add
                    for j, out_tensor in enumerate(out_batch):
                        idx = i + j
                        info = segments_info[idx]
                        start = info["start"]

                        # Fix: Check for NumPy array first
                        if isinstance(out_tensor, np.ndarray):
                            out_tensor = torch.from_numpy(out_tensor)

                        # out_tensor is [1, samples] or [samples]
                        if out_tensor.dim() == 2:
                            out_tensor = out_tensor.squeeze(0)

                        # Ensure on CPU
                        out_tensor = out_tensor.detach().cpu().float()

                        # Apply Window
                        # Ensure lengths match
                        if out_tensor.shape[-1] != segment_length:
                            pass

                        # If output length differs from window length (e.g. slight rounding in model), trim/pad
                        if out_tensor.shape[-1] > segment_length:
                            out_tensor = out_tensor[:segment_length]
                        elif out_tensor.shape[-1] < segment_length:
                            out_tensor = torch.nn.functional.pad(
                                out_tensor, (0, segment_length - out_tensor.shape[-1])
                            )

                        weighted_seg = out_tensor * window.cpu()

                        # Add to buffer
                        valid_len = min(
                            segment_length, output_waveform.shape[-1] - start
                        )

                        output_waveform[:, start : start + valid_len] += weighted_seg[
                            :valid_len
                        ]
                        output_weights[:, start : start + valid_len] += window.cpu()[
                            :valid_len
                        ]

                except Exception as e:
                    logger.error(f"Batch processing failed: {e}")
                    raise e

            # 4. Normalize by weights
            mask = output_weights > 1e-6
            output_waveform[mask] /= output_weights[mask]

            return output_waveform

        finally:
            for info in segments_info:
                if os.path.exists(info["path"]):
                    try:
                        os.remove(info["path"])
                    except:
                        pass

    def _generate_metrics_report(self, input_path, output_path):
        """Helper to generate metrics report, reusable across modes."""
        try:
            # Use absolute path to resolve project root correctly
            # Assuming app structure: /project_root/app/services/upscaler.py
            # We want /project_root/debug_output

            # Resolve relative to THIS file to be safe
            # upscaler.py is in app/services/ -> dirname is app/services
            # .. -> app
            # .. -> project_root
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            )
            debug_dir = os.path.join(project_root, "debug_output")

            logger.info(f"Debug directory: {debug_dir}")
            os.makedirs(debug_dir, exist_ok=True)

            base_name = os.path.basename(output_path).rsplit(".", 1)[0]
            debug_path_base = os.path.join(debug_dir, base_name)

            # Ensure paths are absolute for metrics service
            abs_input = os.path.abspath(input_path)
            abs_output = os.path.abspath(output_path)

            print(f"DEBUG: Generating metrics report for {abs_output}...")
            metrics_service.generate_report(abs_input, abs_output, debug_path_base)
        except Exception as e:
            # Log strictly as error to ensure visibility even if INFO is suppressed
            print(f"DEBUG: Failed to generate metrics: {e}")
            logger.error(f"Failed to generate metrics/plot: {e}")
            traceback.print_exc()

    def process_track(
        self,
        input_path,
        output_path,
        mode="ai",
        ddim_steps=50,
        guidance_scale=3.5,
        seed=42,
        target_format="wav",
        target_sample_rate=48000,
        target_bitrate="320k",
        batch_size=2,
        dsp_preset="mastering",
        dsp_params=None,
    ):
        """
        Upscale/Process the audio file at input_path and save to output_path.
        Modes: 'ai' (AudioSR), 'dsp' (Studio DSP), or 'hybrid' (Stem Separation + DSP).
        """
        try:
            logger.info(f"Starting processing ({mode}): {input_path} -> {output_path}")

            temp_wav = None

            # --- DSP MODE ---
            if mode == "dsp":
                # Determine temp output for WAV generation
                if target_format.lower() == "wav":
                    temp_wav = output_path
                else:
                    temp_wav = output_path + ".tmp.wav"

                # Run DSP
                # dsp.process handles resampling and effect chain
                dsp.process(
                    input_path,
                    temp_wav,
                    preset_name=dsp_preset,
                    params=dsp_params,
                    sample_rate=target_sample_rate,
                )

                # Verify intermediate WAV
                self._verify_audio_output(temp_wav)

                # Convert to target format if needed
                if target_format.lower() != "wav":
                    if not self.ffmpeg_available:
                        logger.error(
                            "FFmpeg not found! Cannot convert to lossy formats."
                        )
                    else:
                        self._convert_format(
                            temp_wav, output_path, target_format, target_bitrate
                        )
                        # Verify converted file
                        self._verify_audio_output(output_path)

                        # Cleanup temp
                        if os.path.exists(temp_wav) and temp_wav != output_path:
                            os.remove(temp_wav)

                # Generate metrics before return
                self._generate_metrics_report(input_path, output_path)
                return True

            # --- HYBRID MODE (Demucs + DSP) ---
            if mode == "hybrid":
                # 1. Determine temp output
                if target_format.lower() == "wav":
                    temp_wav = output_path
                else:
                    temp_wav = output_path + ".tmp.wav"

                # 2. Separate Stems
                # Create a temp dir for stems
                with tempfile.TemporaryDirectory() as stem_dir:
                    logger.info(f"Separating stems into {stem_dir}...")
                    stems_map = separator.separate_track(input_path, stem_dir)

                    # 3. Process Stems & Mix
                    logger.info("Processing and mixing stems...")
                    # returns (channels, samples) numpy array
                    hybrid_audio = dsp.process_stems(
                        stems_map,
                        temp_wav,
                        params=dsp_params,
                        sample_rate=target_sample_rate,
                    )

                # 4. Envelope Matching (Dynamics Restoration)
                # Load original to get reference
                data, sr = sf.read(input_path)
                if data.ndim == 1:
                    data = data[None, :]
                else:
                    data = data.T  # (C, S)

                # Convert to Torch
                original_tensor = torch.from_numpy(data).float()
                hybrid_tensor = torch.from_numpy(hybrid_audio).float()

                # Use Dynamic Envelope Matching for Hybrid Mode
                # This restores the original volume contour/dynamics, fixing "brickwall" issues
                matched_waveform = self._match_envelope(
                    original_tensor, hybrid_tensor, target_sample_rate, window_ms=100
                )
                # matched_waveform = hybrid_tensor # DISABLED FOR TESTING

                # 5. Save Final Output
                # Determine subtype
                subtype = "PCM_24"
                if target_bitrate == "16-bit":
                    subtype = "PCM_16"
                elif target_bitrate == "32-bit":
                    subtype = "FLOAT"

                try:
                    sf.write(
                        temp_wav,
                        matched_waveform.numpy().T,
                        target_sample_rate,
                        subtype=subtype,
                    )
                except Exception as e:
                    logger.error(f"Failed to save hybrid output: {e}")
                    sf.write(temp_wav, matched_waveform.numpy().T, target_sample_rate)

                # Verify intermediate WAV
                self._verify_audio_output(temp_wav)

                # 6. Convert format if needed
                if target_format.lower() != "wav":
                    if not self.ffmpeg_available:
                        logger.error(
                            "FFmpeg not found! Cannot convert to lossy formats."
                        )
                    else:
                        self._convert_format(
                            temp_wav, output_path, target_format, target_bitrate
                        )
                        self._verify_audio_output(output_path)
                        if os.path.exists(temp_wav) and temp_wav != output_path:
                            os.remove(temp_wav)

                # Generate metrics before return
                self._generate_metrics_report(input_path, output_path)
                return True

            # --- RESTORATION MODE (Suno Enhancer: Demucs Filter + DSP) ---
            if mode == "restoration":
                logger.info("Starting Suno Restoration Pipeline...")

                if target_format.lower() == "wav":
                    temp_wav = output_path
                else:
                    temp_wav = output_path + ".tmp.wav"

                # 1. Demucs Separation (Re-synthesis)
                # We separate and recombine to "filter" MP3 artifacts
                with tempfile.TemporaryDirectory() as stem_dir:
                    logger.info(
                        f"Step 1: Separating stems for re-synthesis into {stem_dir}..."
                    )
                    stems_map = separator.separate_track(input_path, stem_dir)

                    # 2. Re-mix (Summation)
                    logger.info("Step 2: Summing stems (Re-synthesis)...")

                    loaded_stems = []
                    max_len = 0
                    current_sr = target_sample_rate  # Will update from first stem

                    for s_path in stems_map.values():
                        # Read as float32 to match final_mix dtype and save memory
                        s_data, s_sr = sf.read(s_path, dtype="float32")
                        current_sr = s_sr

                        if s_data.ndim == 1:
                            s_data = s_data[None, :]
                        else:
                            s_data = s_data.T  # (Channels, Samples)

                        loaded_stems.append(s_data)
                        if s_data.shape[1] > max_len:
                            max_len = s_data.shape[1]

                    # Initialize mix
                    final_mix = np.zeros(
                        (loaded_stems[0].shape[0], max_len), dtype=np.float32
                    )

                    for s_data in loaded_stems:
                        # Pad if needed
                        if s_data.shape[1] < max_len:
                            pad = np.zeros(
                                (s_data.shape[0], max_len - s_data.shape[1]),
                                dtype=np.float32,
                            )
                            s_data = np.concatenate([s_data, pad], axis=1)
                        final_mix += s_data

                # 3. DSP Polish (Suno Specific)
                logger.info("Step 3: Applying Suno DSP Polish...")
                polished = dsp.apply_suno_restoration(final_mix, current_sr)

                # 4. Save Final
                # Resample if target_sample_rate differs
                if current_sr != target_sample_rate:
                    import resampy

                    polished = resampy.resample(
                        polished, current_sr, target_sample_rate, axis=1
                    )

                # Write
                sf.write(temp_wav, polished.T, target_sample_rate)

                # Verify intermediate WAV
                self._verify_audio_output(temp_wav)

                # Convert
                if target_format.lower() != "wav":
                    if self.ffmpeg_available:
                        self._convert_format(
                            temp_wav, output_path, target_format, target_bitrate
                        )
                        self._verify_audio_output(output_path)
                        if os.path.exists(temp_wav) and temp_wav != output_path:
                            os.remove(temp_wav)

                # Generate metrics before return
                self._generate_metrics_report(input_path, output_path)
                return True

            # --- AI MODE ---
            # 1. DSP Pre-processing (Clean & Level before AI)
            # This helps reduce AI hallucinations by feeding it a cleaner, leveled signal.
            dsp_temp_wav = None
            try:
                logger.info("Step 1: Running DSP Pre-processing for AI...")
                if target_format.lower() == "wav":
                    dsp_temp_wav = output_path + ".dsp_pre.wav"
                else:
                    dsp_temp_wav = output_path + ".tmp.dsp_pre.wav"

                # Apply DSP (EQ, Comp, Limiter) to input
                # We force 48kHz here to match AudioSR expectation, saving a resample step later
                dsp.process(
                    input_path,
                    dsp_temp_wav,
                    preset_name=dsp_preset,
                    params=dsp_params,
                    sample_rate=48000,
                )

                # Update input_path to use the cleaned file for the rest of the pipeline
                input_path = dsp_temp_wav

            except Exception as e:
                logger.error(f"DSP Pre-processing failed: {e}")
                # Fallback to original input if DSP fails
                if dsp_temp_wav and os.path.exists(dsp_temp_wav):
                    os.remove(dsp_temp_wav)
                dsp_temp_wav = None

            self.load_model()

            logger.info(
                f"AI Params: steps={ddim_steps}, guidance={guidance_scale}, seed={seed}, batch={batch_size}"
            )

            # Read file using soundfile (Reload in case input_path changed due to DSP)
            try:
                data, sr = sf.read(input_path)
                if data.ndim == 1:
                    data = data[None, :]
                else:
                    data = data.T  # Convert to [channels, samples]
                waveform = torch.from_numpy(data).float()
            except Exception as e:
                logger.error(f"Failed to read input file with sf.read: {e}")
                raise e

            logger.info(f"Loaded waveform shape: {waveform.shape}, sr: {sr}")

            # Resample to 48k
            if sr != 48000:
                logger.info("Resampling to 48000Hz...")
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=48000)
                waveform = resampler(waveform)
                sr = 48000

            # Check for Stereo
            channels = waveform.shape[0]
            logger.info(f"Processing audio with {channels} channel(s)")

            upscaled_waveform = None

            if channels == 1:
                # Process Mono
                upscaled_waveform = self._process_channel_waveform(
                    waveform, sr, ddim_steps, guidance_scale, seed, batch_size
                )
            elif channels == 2:
                # Process Stereo using Mid-Side to preserve Phase/Width
                logger.info("Stereo detected. Using Mid-Side processing...")

                # 1. Convert to Mid-Side
                # Mid = (L+R)/2, Side = (L-R)/2
                mid_channel = (waveform[0:1, :] + waveform[1:2, :]) * 0.5
                side_channel = (waveform[0:1, :] - waveform[1:2, :]) * 0.5

                # 2. Upscale Mid Channel Only
                # We trust AI to improve the "core" (Mid) information, but we keep Side original to prevent
                # phase issues and "channel leakage" where AI hallucinates stereo width differently on L/R.
                logger.info("Upscaling Mid Channel...")
                mid_upscaled = self._process_channel_waveform(
                    mid_channel, sr, ddim_steps, guidance_scale, seed, batch_size
                )

                # 3. Match Dynamics on Mid Channel (Essential)
                # Restore the dynamics of the original Mid to the new High-Res Mid
                mid_upscaled = self._match_envelope(
                    mid_channel, mid_upscaled, sr, window_ms=100
                )

                # 4. Handle Side Channel (Pass-through / Resample)
                # We need side_channel to match the length and sample rate of mid_upscaled.
                # Since we force 48k at input, sr should match, but lengths might differ due to OLA/padding.

                # Ensure side matches mid length
                target_len = mid_upscaled.shape[-1]
                current_len = side_channel.shape[-1]

                if current_len != target_len:
                    # Pad or Trim
                    if current_len > target_len:
                        side_channel = side_channel[..., :target_len]
                    else:
                        pad = target_len - current_len
                        side_channel = torch.nn.functional.pad(side_channel, (0, pad))

                # 5. Reconstruct Stereo
                # New L = Mid_New + Side_Orig
                # New R = Mid_New - Side_Orig
                out_left = mid_upscaled + side_channel
                out_right = mid_upscaled - side_channel

                upscaled_waveform = torch.cat([out_left, out_right], dim=0)
            else:
                # For > 2 channels, just mix to mono for now
                logger.warning(
                    f"Unsupported channel count {channels}. Downmixing to mono."
                )
                waveform = torch.mean(waveform, dim=0, keepdim=True)
                upscaled_waveform = self._process_channel_waveform(
                    waveform, sr, ddim_steps, guidance_scale, seed, batch_size
                )

            # --- Global Envelope Matching (Parent-Child) ---
            if upscaled_waveform is not None:
                upscaled_waveform = self._match_envelope(
                    waveform, upscaled_waveform, sr, window_ms=100
                )

            logger.info(
                f"Generated waveform shape: {upscaled_waveform.shape}, dtype: {upscaled_waveform.dtype}, device: {upscaled_waveform.device}"
            )

            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Temporary wav file if we need to convert or if saving to WAV
            if target_format.lower() == "wav":
                temp_wav = output_path
            else:
                temp_wav = output_path + ".tmp.wav"

            # Resample if needed
            if target_sample_rate != 48000:
                logger.info(f"Resampling from 48000 to {target_sample_rate}")
                resampler = torchaudio.transforms.Resample(
                    orig_freq=48000, new_freq=target_sample_rate
                )
                upscaled_waveform = resampler(upscaled_waveform)
                logger.info(f"Resampled waveform shape: {upscaled_waveform.shape}")

            # Determine subtype based on request (target_bitrate holds '16-bit', '24-bit', etc for WAV/FLAC)
            subtype = "PCM_24"  # Default high quality
            if target_bitrate == "16-bit":
                subtype = "PCM_16"
            elif target_bitrate == "32-bit":
                subtype = "FLOAT"

            # Save as WAV first
            if target_format.lower() in ["wav", "flac"]:
                logger.info(f"Attempting to save intermediate WAV as {subtype}")
                try:
                    sf.write(
                        temp_wav,
                        upscaled_waveform.T.numpy(),
                        target_sample_rate,
                        subtype=subtype,
                    )
                except Exception as e:
                    logger.error(f"Failed to save with subtype {subtype}: {e}")
                    # Fallback
                    sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate)
            else:
                try:
                    sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate)
                except Exception as e:
                    logger.error(f"Failed to save temporary WAV with sf: {e}")
                    raise e

            # Verify intermediate WAV
            self._verify_audio_output(temp_wav)

            if target_format.lower() != "wav":
                if not self.ffmpeg_available:
                    logger.error(
                        "FFmpeg not found! Cannot convert to lossy formats or FLAC."
                    )
                else:
                    self._convert_format(
                        temp_wav, output_path, target_format, target_bitrate
                    )
                    self._verify_audio_output(output_path)
                    if (
                        temp_wav
                        and os.path.exists(temp_wav)
                        and temp_wav != output_path
                    ):
                        os.remove(temp_wav)

            # --- Generate Diagnostics/Metrics ---
            self._generate_metrics_report(input_path, output_path)

            logger.info(
                f"Successfully saved upscaled audio to {output_path}. Final file size: {os.path.getsize(output_path) / (1024*1024):.2f} MB"
            )
            return True

        except Exception as e:
            logger.error(f"Error during upscaling: {e}")
            traceback.print_exc()
            if temp_wav and os.path.exists(temp_wav) and temp_wav != output_path:
                try:
                    os.remove(temp_wav)
                except:
                    pass
            raise e
        finally:
            self.unload_model()
            # Cleanup DSP temp file
            if (
                "dsp_temp_wav" in locals()
                and dsp_temp_wav
                and os.path.exists(dsp_temp_wav)
            ):
                try:
                    os.remove(dsp_temp_wav)
                except:
                    pass


# Create a singleton instance
upscaler = UpscalerService()
