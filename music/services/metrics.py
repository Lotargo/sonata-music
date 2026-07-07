import os
import json
import logging
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class MetricsService:
    def __init__(self):
        pass

    def _calculate_metrics(self, data):
        """
        Calculates basic audio metrics for a numpy array.
        data: (samples, channels) or (samples,)
        """
        if data.ndim == 2:
            # Mix to mono for simple metrics
            mono = np.mean(data, axis=1)
        else:
            mono = data

        # Peak Amplitude
        peak = np.max(np.abs(mono))
        peak_db = 20 * np.log10(peak + 1e-9)

        # RMS Amplitude
        rms = np.sqrt(np.mean(mono**2))
        rms_db = 20 * np.log10(rms + 1e-9)

        # Crest Factor / simple dynamic range approximation
        crest_factor = peak / (rms + 1e-9)
        crest_db = 20 * np.log10(crest_factor + 1e-9)

        return {
            "peak_db": float(round(peak_db, 2)),
            "rms_db": float(round(rms_db, 2)),
            "dynamic_range_db": float(round(crest_db, 2)),
            "crest_factor": float(round(crest_factor, 2)),
        }

    def _file_info(self, path, data, sample_rate):
        """Collect display-safe file metadata for the comparison modal."""
        basename = os.path.basename(path) if path else ""
        ext = os.path.splitext(basename)[1].lstrip(".").lower()
        channels = 1 if data.ndim == 1 else data.shape[1]
        frames = len(data)
        duration = frames / sample_rate if sample_rate else 0

        info = {
            "path": path,
            "filename": basename,
            "format": ext.upper() if ext else "UNKNOWN",
            "sr": int(sample_rate),
            "channels": int(channels),
            "frames": int(frames),
            "duration": float(round(duration, 3)),
        }

        try:
            sf_info = sf.info(path)
            info.update({
                "format": (sf_info.format or info["format"]).upper(),
                "subtype": sf_info.subtype,
                "duration": float(round(sf_info.duration, 3)),
                "frames": int(sf_info.frames),
                "channels": int(sf_info.channels),
            })
        except Exception as e:
            logger.warning(f"Could not read detailed audio info for {path}: {e}")

        return info

    def generate_report(self, original_path, processed_path, output_base_path):
        """
        Generates a JSON report and a PNG plot comparing original and processed audio.
        output_base_path: /path/to/debug/filename_base (without extension)
        """
        try:
            logger.info(f"Generating metrics report for {processed_path}...")

            # Read Audio
            data_orig, sr_orig = sf.read(original_path)
            data_proc, sr_proc = sf.read(processed_path)

            # Metrics
            metrics_orig = self._calculate_metrics(data_orig)
            metrics_proc = self._calculate_metrics(data_proc)
            info_orig = self._file_info(original_path, data_orig, sr_orig)
            info_proc = self._file_info(processed_path, data_proc, sr_proc)

            report = {
                "original": {**info_orig, **metrics_orig},
                "processed": {**info_proc, **metrics_proc},
            }

            # Save JSON
            json_path = output_base_path + "_metrics.json"
            with open(json_path, "w") as f:
                json.dump(report, f, indent=4)

            # Generate Plot
            plot_path = output_base_path + "_comparison.png"
            self._generate_plot(data_orig, data_proc, sr_orig, sr_proc, plot_path)

            print(f"DEBUG: Saved metrics to {json_path}")
            print(f"DEBUG: Saved plot to {plot_path}")
            return json_path

        except Exception as e:
            logger.error(f"Failed to generate metrics report: {e}")
            return None

    def _generate_plot(self, data_orig, data_proc, sr_orig, sr_proc, output_path):
        """Generates a side-by-side waveform plot."""
        try:
            # Downsample for plotting speed if too large
            target_len = 100000

            def process_for_plot(data):
                if data.ndim == 2:
                    data = np.mean(data, axis=1)  # Mono
                if len(data) > target_len:
                    step = len(data) // target_len
                    data = data[::step]
                return data

            plot_orig = process_for_plot(data_orig)
            plot_proc = process_for_plot(data_proc)

            plt.figure(figsize=(12, 6))

            # Original
            plt.subplot(2, 1, 1)
            plt.plot(plot_orig, color="blue", alpha=0.7)
            plt.title(
                f"Original (Peak: {20*np.log10(np.max(np.abs(plot_orig))+1e-9):.1f} dB)"
            )
            plt.ylim(-1.1, 1.1)
            plt.grid(True, alpha=0.3)

            # Processed
            plt.subplot(2, 1, 2)
            plt.plot(plot_proc, color="green", alpha=0.7)
            plt.title(
                f"Processed (Peak: {20*np.log10(np.max(np.abs(plot_proc))+1e-9):.1f} dB)"
            )
            plt.ylim(-1.1, 1.1)
            plt.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_path)
            plt.close()

        except Exception as e:
            logger.error(f"Failed to generate plot: {e}")


metrics_service = MetricsService()
