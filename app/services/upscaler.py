import os
import torch
import torchaudio
import logging
import subprocess
import traceback
import tempfile
import gc
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
            "sampling_rate": 48000
        }

        max_duration = 5.12 # Standard for AudioSR

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
                final_batch[k] = torch.cat(batched_inputs[k], dim=0) # [B, ...]
                # Move to device
                final_batch[k] = final_batch[k].to(self.device)

        # 2. Run Inference
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

        return waveforms # [B, 1, samples]

    def _process_channel_waveform(self, waveform, sr, ddim_steps, guidance_scale, seed, batch_size=4):
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

        logger.info(f"Processing {num_segments} segments (OLA) with batch size {batch_size}...")

        # Prepare output buffer and weight buffer
        output_waveform = torch.zeros_like(waveform)
        output_weights = torch.zeros_like(waveform)

        # Create Hanning window
        window = torch.hann_window(segment_length).to(waveform.device)

        segments_info = [] # List of (start, end, temp_file_path)

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
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_seg:
                    temp_seg_path = tmp_seg.name

                # Write
                sf.write(temp_seg_path, segment.T.numpy(), sr)
                segments_info.append({"start": start, "end": end, "path": temp_seg_path})

            # 2. Process in Batches
            for i in range(0, len(segments_info), batch_size):
                batch_files = [s["path"] for s in segments_info[i : i + batch_size]]
                logger.info(f"Processing batch {i // batch_size + 1}/{(len(segments_info) + batch_size - 1) // batch_size}")

                try:
                    # Run batch inference
                    out_batch = self._batched_super_resolution(batch_files, ddim_steps, guidance_scale, seed)

                    # 3. Overlap-Add
                    for j, out_tensor in enumerate(out_batch):
                        idx = i + j
                        info = segments_info[idx]
                        start = info["start"]

                        # out_tensor is [1, samples] or [samples]
                        if out_tensor.dim() == 2:
                            out_tensor = out_tensor.squeeze(0)

                        # Ensure on CPU
                        out_tensor = out_tensor.detach().cpu().float()

                        # Apply Window
                        # Ensure lengths match
                        if out_tensor.shape[-1] != segment_length:
                            # Trim or pad? AudioSR output should be correct duration usually
                            # but sometimes it differs slightly due to internal resizing.
                            # Resample to match exact sample count if needed?
                            # Usually AudioSR output matches 5.12s @ 48kHz
                            pass

                        # If output length differs from window length (e.g. slight rounding in model), trim/pad
                        if out_tensor.shape[-1] > segment_length:
                             out_tensor = out_tensor[:segment_length]
                        elif out_tensor.shape[-1] < segment_length:
                             out_tensor = torch.nn.functional.pad(out_tensor, (0, segment_length - out_tensor.shape[-1]))

                        weighted_seg = out_tensor * window.cpu()

                        # Add to buffer
                        # Handle last segment boundary check
                        valid_len = min(segment_length, output_waveform.shape[-1] - start)

                        output_waveform[:, start : start + valid_len] += weighted_seg[:valid_len]
                        output_weights[:, start : start + valid_len] += window.cpu()[:valid_len]

                except Exception as e:
                    logger.error(f"Batch processing failed: {e}")
                    raise e

            # 4. Normalize by weights
            # Avoid division by zero
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

    def process_track(self, input_path, output_path, ddim_steps=25, guidance_scale=3.5, seed=42,
                      target_format="wav", target_sample_rate=48000, target_bitrate="320k", batch_size=4):
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
                # Process Stereo - Split channels
                logger.info("Stereo detected. Processing Left Channel...")
                left_channel = waveform[0:1, :]
                out_left = self._process_channel_waveform(left_channel, sr, ddim_steps, guidance_scale, seed, batch_size)

                logger.info("Stereo detected. Processing Right Channel...")
                right_channel = waveform[1:2, :]
                out_right = self._process_channel_waveform(right_channel, sr, ddim_steps, guidance_scale, seed, batch_size)

                # Combine
                min_len = min(out_left.shape[-1], out_right.shape[-1])
                out_left = out_left[..., :min_len]
                out_right = out_right[..., :min_len]

                upscaled_waveform = torch.cat([out_left, out_right], dim=0)
            else:
                 # For > 2 channels, just mix to mono for now
                 logger.warning(f"Unsupported channel count {channels}. Downmixing to mono.")
                 waveform = torch.mean(waveform, dim=0, keepdim=True)
                 upscaled_waveform = self._process_channel_waveform(waveform, sr, ddim_steps, guidance_scale, seed, batch_size)

            logger.info(f"Generated waveform shape: {upscaled_waveform.shape}, dtype: {upscaled_waveform.dtype}, device: {upscaled_waveform.device}")

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
                resampler = torchaudio.transforms.Resample(orig_freq=48000, new_freq=target_sample_rate)
                upscaled_waveform = resampler(upscaled_waveform)
                logger.info(f"Resampled waveform shape: {upscaled_waveform.shape}")

            # Save as WAV first
            if target_format.lower() in ["wav", "flac"]:
                logger.info("Attempting to save as 24-bit WAV")
                try:
                    # waveform is [channels, samples]
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
