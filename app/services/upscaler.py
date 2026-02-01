import os
import torch
import torchaudio
import logging
import subprocess
import traceback
import tempfile
import gc
import queue
from concurrent.futures import ThreadPoolExecutor
from audiosr.pipeline import build_model, super_resolution, make_batch_for_super_resolution
# Explicitly import where we need to patch
import audiosr.utils
import audiosr.pipeline
import soundfile as sf
import numpy as np
from pydub import AudioSegment

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

    if(duration > 10.24):
        logger.warning(f"Audio is {duration:.2f}s, which is longer than 10.24s. It will be truncated/chunked.")

    if(duration % 5.12 != 0):
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

# Apply monkey patch to audiosr.utils
logger.info("Applying monkey-patch to audiosr.utils.read_wav_file")
audiosr.utils.read_wav_file = safe_read_wav_file

class UpscalerService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.ffmpeg_available = self._check_ffmpeg()
        logger.info(f"UpscalerService initialized on {self.device}. FFmpeg available: {self.ffmpeg_available}")

    def _check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

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
            squared = waveform ** 2
            squared = squared.unsqueeze(0)
            envelope = torch.nn.functional.avg_pool1d(squared, kernel_size=win_size, stride=1, padding=padding, count_include_pad=False)
            envelope = torch.sqrt(envelope + 1e-8)
            return envelope.squeeze(0)

        env_source = compute_envelope(source, window_size, pad)
        env_target = compute_envelope(target, window_size, pad)

        gain = env_source / (env_target + 1e-6)
        matched_waveform = target * gain

        return matched_waveform

    def _prepare_batch_cpu(self, input_files):
        """
        Runs the CPU-heavy preprocessing (loading, resampling, STFT) for a batch.
        Returns a dict of tensors (on CPU).
        """
        import audiosr.pipeline as pipeline

        batched_inputs = {
            "waveform": [],
            "stft": [],
            "log_mel_spec": [],
            "lowpass_mel": [],
            "waveform_lowpass": [],
            "sampling_rate": 48000
        }

        for f in input_files:
            mini_batch, _ = make_batch_for_super_resolution(f)
            for k in batched_inputs.keys():
                if k != "sampling_rate" and k in mini_batch:
                     batched_inputs[k].append(mini_batch[k])

        # Concatenate tensors
        final_batch = {}
        for k in batched_inputs.keys():
            if k == "sampling_rate":
                final_batch[k] = batched_inputs[k]
            elif len(batched_inputs[k]) > 0:
                final_batch[k] = torch.cat(batched_inputs[k], dim=0) # [B, ...]
                # Keep on CPU

        return final_batch

    def _run_inference_gpu(self, final_batch, ddim_steps, guidance_scale, seed):
        """
        Runs the GPU inference on a pre-prepared batch.
        """
        import audiosr.pipeline as pipeline
        pipeline.seed_everything(int(seed))
        max_duration = 5.12

        # Move to GPU just before inference
        for k in final_batch.keys():
            if isinstance(final_batch[k], torch.Tensor):
                final_batch[k] = final_batch[k].to(self.device)

        if self.device == "cuda":
             with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
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

        # Move back to CPU immediately
        if isinstance(waveforms, torch.Tensor):
            waveforms = waveforms.detach().cpu()
        elif isinstance(waveforms, np.ndarray):
            # Should not happen usually, but for safety
            pass

        return waveforms

    def _process_channel_waveform(self, waveform, sr, ddim_steps, guidance_scale, seed, batch_size=4, fixed_norm_scale=None):
        """
        Processes a single-channel waveform using Overlap-Add (OLA) and Pipelined Batching.
        """
        # Normalize waveform
        if fixed_norm_scale is not None:
            max_val = fixed_norm_scale
        else:
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

        logger.info(f"Processing {num_segments} segments (OLA) with batch size {batch_size} (Pipelined)...")

        # Prepare output buffer and weight buffer
        output_waveform = torch.zeros_like(waveform)
        output_weights = torch.zeros_like(waveform)

        # Create Hanning window
        window = torch.hann_window(segment_length).to(waveform.device)

        segments_info = [] # List of (start, end, temp_file_path)

        # ThreadPool for Pipelining
        # We need 1 worker to prepare the NEXT batch while MAIN thread runs inference on CURRENT batch.
        executor = ThreadPoolExecutor(max_workers=1)

        try:
            # 1. Slice and Save all segments
            for i in range(num_segments):
                start = i * stride
                end = start + segment_length
                segment = waveform[:, start:end]
                if segment.shape[-1] < segment_length:
                    pad_amt = segment_length - segment.shape[-1]
                    segment = torch.nn.functional.pad(segment, (0, pad_amt))

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_seg:
                    temp_seg_path = tmp_seg.name
                sf.write(temp_seg_path, segment.T.numpy(), sr)
                segments_info.append({"start": start, "end": end, "path": temp_seg_path})

            # 2. Pipelined Processing
            num_batches = (len(segments_info) + batch_size - 1) // batch_size

            # Prepare first batch immediately
            first_batch_files = [s["path"] for s in segments_info[0 : batch_size]]
            future_batch = executor.submit(self._prepare_batch_cpu, first_batch_files)

            for i in range(num_batches):
                logger.info(f"Processing batch {i + 1}/{num_batches}")

                # Get current prepared batch (waits if CPU is slow, usually CPU is faster than GPU)
                current_batch_tensors = future_batch.result()

                # Submit NEXT batch preparation (if exists)
                next_batch_idx = i + 1
                if next_batch_idx < num_batches:
                    start_idx = next_batch_idx * batch_size
                    end_idx = start_idx + batch_size
                    next_files = [s["path"] for s in segments_info[start_idx : end_idx]]
                    future_batch = executor.submit(self._prepare_batch_cpu, next_files)

                # Run Inference on GPU (while CPU is preparing next batch)
                out_batch = self._run_inference_gpu(current_batch_tensors, ddim_steps, guidance_scale, seed)

                # 3. Overlap-Add (CPU)
                start_segment_idx = i * batch_size

                for j, out_tensor in enumerate(out_batch):
                    idx = start_segment_idx + j
                    if idx >= len(segments_info): break

                    info = segments_info[idx]
                    start = info["start"]

                    # Robust type conversion
                    if isinstance(out_tensor, np.ndarray):
                        out_tensor = torch.from_numpy(out_tensor)

                    if out_tensor.dim() == 2:
                        out_tensor = out_tensor.squeeze(0)

                    out_tensor = out_tensor.float().to(waveform.device) # Move to same device as buffers

                    # Apply Window
                    if out_tensor.shape[-1] > segment_length:
                            out_tensor = out_tensor[:segment_length]
                    elif out_tensor.shape[-1] < segment_length:
                            out_tensor = torch.nn.functional.pad(out_tensor, (0, segment_length - out_tensor.shape[-1]))

                    weighted_seg = out_tensor * window

                    valid_len = min(segment_length, output_waveform.shape[-1] - start)
                    output_waveform[:, start : start + valid_len] += weighted_seg[:valid_len]
                    output_weights[:, start : start + valid_len] += window[:valid_len]

            # 4. Normalize
            mask = output_weights > 1e-6
            output_waveform[mask] /= output_weights[mask]

            return output_waveform

        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}")
            raise e
        finally:
            executor.shutdown(wait=False)
            for info in segments_info:
                 if os.path.exists(info["path"]):
                     try:
                         os.remove(info["path"])
                     except:
                         pass

    def process_track(self, input_path, output_path, ddim_steps=50, guidance_scale=3.5, seed=42,
                      target_format="wav", target_sample_rate=48000, target_bitrate="320k", batch_size=2):
        """
        Upscale the audio file at input_path and save to output_path.
        Supports FP16, custom steps, guidance, seed.
        """
        try:
            self.load_model()

            logger.info(f"Starting upscaling: {input_path} -> {output_path} "
                        f"(format: {target_format}, sr: {target_sample_rate}, "
                        f"br: {target_bitrate}, steps: {ddim_steps}, "
                        f"guidance: {guidance_scale}, seed: {seed}, batch: {batch_size})")

            temp_wav = None

            # Read file using soundfile
            try:
                data, sr = sf.read(input_path)
                if data.ndim == 1:
                    data = data[None, :]
                else:
                    data = data.T # Convert to [channels, samples]
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
                upscaled_waveform = self._process_channel_waveform(waveform, sr, ddim_steps, guidance_scale, seed, batch_size)
            elif channels == 2:
                # Process Stereo - USE MID-SIDE PROCESSING
                logger.info("Stereo detected. Converting to Mid-Side (M/S)...")

                # Encode M/S
                mid_channel = (waveform[0:1, :] + waveform[1:2, :]) * 0.5
                side_channel = (waveform[0:1, :] - waveform[1:2, :]) * 0.5

                # Calculate Global Max for Normalization Preservation
                global_max = max(torch.max(torch.abs(mid_channel)), torch.max(torch.abs(side_channel)))
                if global_max == 0: global_max = 1.0

                logger.info(f"Processing Mid Channel (Global Max: {global_max:.4f})...")
                out_mid = self._process_channel_waveform(mid_channel, sr, ddim_steps, guidance_scale, seed, batch_size, fixed_norm_scale=global_max)

                logger.info("Processing Side Channel...")
                out_side = self._process_channel_waveform(side_channel, sr, ddim_steps, guidance_scale, seed, batch_size, fixed_norm_scale=global_max)

                # Combine
                min_len = min(out_mid.shape[-1], out_side.shape[-1])
                out_mid = out_mid[..., :min_len]
                out_side = out_side[..., :min_len]

                # Decode M/S
                out_left = out_mid + out_side
                out_right = out_mid - out_side

                upscaled_waveform = torch.cat([out_left, out_right], dim=0)
            else:
                 # For > 2 channels, just mix to mono for now
                 logger.warning(f"Unsupported channel count {channels}. Downmixing to mono.")
                 waveform = torch.mean(waveform, dim=0, keepdim=True)
                 upscaled_waveform = self._process_channel_waveform(waveform, sr, ddim_steps, guidance_scale, seed, batch_size)

            # --- Global Envelope Matching (Parent-Child) ---
            if upscaled_waveform is not None:
                upscaled_waveform = self._match_envelope(waveform, upscaled_waveform, sr, window_ms=100)

            logger.info(f"Generated waveform shape: {upscaled_waveform.shape}, dtype: {upscaled_waveform.dtype}, device: {upscaled_waveform.device}")

            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # --- FIX: Restore temp_wav initialization ---
            if target_format.lower() == "wav":
                temp_wav = output_path
            else:
                temp_wav = output_path + ".tmp.wav"

            # Resample if needed
            if target_sample_rate != 48000:
                logger.info(f"Resampling from 48000 to {target_sample_rate}")
                resampler = torchaudio.transforms.Resample(orig_freq=48000, new_freq=target_sample_rate)
                upscaled_waveform = resampler(upscaled_waveform)
                logger.info(f"Resampled waveform shape: {upscaled_waveform.shape}")

            # Save as WAV first
            if target_format.lower() in ["wav", "flac"]:
                logger.info("Attempting to save as 24-bit WAV")
                try:
                    sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate, subtype='PCM_24')
                except Exception as e:
                    logger.error(f"Failed to save 24-bit with sf: {e}")
                    try:
                        logger.warning("Falling back to 16-bit WAV...")
                        sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate, subtype='PCM_16')
                    except Exception as e2:
                        logger.error(f"Failed to save 16-bit with sf: {e2}")
                        raise e2
            else:
                try:
                    sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate)
                except Exception as e:
                    logger.error(f"Failed to save temporary WAV with sf: {e}")
                    raise e

            if target_format.lower() != "wav":
                if not self.ffmpeg_available:
                    logger.error("FFmpeg not found! Cannot convert to lossy formats or FLAC.")
                else:
                    logger.info(f"Converting to {target_format} using pydub")
                    audio = AudioSegment.from_wav(temp_wav)

                    format_map = {
                        'mp3': 'mp3',
                        'flac': 'flac',
                        'ogg': 'ogg',
                        'vorbis': 'ogg'
                    }
                    out_fmt = format_map.get(target_format.lower(), target_format.lower())

                    if out_fmt in ['mp3', 'ogg']:
                        audio.export(output_path, format=out_fmt, bitrate=target_bitrate)
                    else:
                        audio.export(output_path, format=out_fmt)

                    if temp_wav and os.path.exists(temp_wav) and temp_wav != output_path:
                        os.remove(temp_wav)

            logger.info(f"Successfully saved upscaled audio to {output_path}. Final file size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")
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

# Create a singleton instance
upscaler = UpscalerService()
