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
        Calculates audio metrics for a numpy array, including full stereo L/R analysis.
        data: (samples, channels) or (samples,)
        """
        is_stereo = (data.ndim == 2 and data.shape[1] >= 2)

        if is_stereo:
            left = data[:, 0]
            right = data[:, 1]
            mono = np.mean(data, axis=1)
        elif data.ndim == 2:
            left = data[:, 0]
            right = data[:, 0]
            mono = data[:, 0]
        else:
            left = data
            right = data
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

        # Stereo metrics
        peak_l = np.max(np.abs(left))
        peak_l_db = 20 * np.log10(peak_l + 1e-9)
        rms_l = np.sqrt(np.mean(left**2))
        rms_l_db = 20 * np.log10(rms_l + 1e-9)

        peak_r = np.max(np.abs(right))
        peak_r_db = 20 * np.log10(peak_r + 1e-9)
        rms_r = np.sqrt(np.mean(right**2))
        rms_r_db = 20 * np.log10(rms_r + 1e-9)

        if is_stereo:
            mid = (left + right) * 0.5
            side = (left - right) * 0.5

            rms_mid = np.sqrt(np.mean(mid**2))
            rms_mid_db = 20 * np.log10(rms_mid + 1e-9)

            rms_side = np.sqrt(np.mean(side**2))
            rms_side_db = 20 * np.log10(rms_side + 1e-9)

            side_peak = np.max(np.abs(side))
            side_peak_db = 20 * np.log10(side_peak + 1e-9)

            # Pearson correlation coefficient between Left and Right channels
            std_l = np.std(left)
            std_r = np.std(right)
            if std_l > 1e-7 and std_r > 1e-7:
                corr_matrix = np.corrcoef(left, right)
                corr = float(corr_matrix[0, 1])
                if np.isnan(corr):
                    corr = 1.0 if np.allclose(left, right, atol=1e-5) else 0.0
            else:
                corr = 1.0 if np.allclose(left, right, atol=1e-5) else 0.0

            corr = float(np.clip(corr, -1.0, 1.0))
            stereo_width_ratio = float(rms_side / (rms_mid + 1e-9))
        else:
            rms_mid_db = rms_db
            rms_side_db = -120.0
            side_peak_db = -120.0
            corr = 1.0
            stereo_width_ratio = 0.0

        return {
            "peak_db": float(round(peak_db, 2)),
            "rms_db": float(round(rms_db, 2)),
            "dynamic_range_db": float(round(crest_db, 2)),
            "crest_factor": float(round(crest_factor, 2)),
            "peak_l_db": float(round(peak_l_db, 2)),
            "peak_r_db": float(round(peak_r_db, 2)),
            "rms_l_db": float(round(rms_l_db, 2)),
            "rms_r_db": float(round(rms_r_db, 2)),
            "rms_mid_db": float(round(rms_mid_db, 2)),
            "rms_side_db": float(round(rms_side_db, 2)),
            "side_peak_db": float(round(side_peak_db, 2)),
            "stereo_correlation": float(round(corr, 3)),
            "stereo_width_ratio": float(round(stereo_width_ratio, 3)),
            "is_stereo": bool(is_stereo),
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
