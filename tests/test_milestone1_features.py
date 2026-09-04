import sys
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import soundfile as sf
from mutagen import File
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggopus import OggOpus

from music.services.upscaler import upscaler
from music.services.dsp import dsp
from music.services.metadata import clean_and_embed_metadata
from music.views import normalize_processing_payload


def test_payload_normalization():
    print("Testing payload normalization for direct, stealth, and new formats...")
    # Direct mode with m4a
    payload_direct = normalize_processing_payload({'mode': 'direct', 'format': 'm4a', 'bitrate': '256k'})
    assert payload_direct['mode'] == 'direct', f"Expected direct mode, got {payload_direct['mode']}"
    assert payload_direct['format'] == 'm4a', f"Expected m4a format, got {payload_direct['format']}"
    assert payload_direct['bitrate'] == '256k', f"Expected 256k bitrate, got {payload_direct['bitrate']}"

    # Stealth mode with opus
    payload_stealth = normalize_processing_payload({'mode': 'stealth', 'format': 'opus', 'bitrate': '160k'})
    assert payload_stealth['mode'] == 'stealth', f"Expected stealth mode, got {payload_stealth['mode']}"
    assert payload_stealth['format'] == 'opus', f"Expected opus format, got {payload_stealth['format']}"
    assert payload_stealth['bitrate'] == '160k', f"Expected 160k bitrate, got {payload_stealth['bitrate']}"

    print("Payload normalization tests PASSED!")


def test_direct_conversion_and_metadata():
    print("Testing direct conversion and metadata embedding with sample album tracks...")
    sample_dir = Path(".samples/Album 1")
    sample_track = sample_dir / "00 - Tape 00_ Toluca Overlook (Prologue).wav"
    cover_image = sample_dir / "covers/cover_01_found-photograph_room-302.png"

    assert sample_track.exists(), f"Sample track not found: {sample_track}"
    assert cover_image.exists(), f"Cover image not found: {cover_image}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Test Direct Conversion to MP3
        mp3_out = tmp_path / "test_converted.mp3"
        success = upscaler.process_track(
            input_path=str(sample_track),
            output_path=str(mp3_out),
            mode="direct",
            target_format="mp3",
            target_bitrate="320k",
            title="Toluca Overlook",
            artist="Silent Hill Survivor",
            album="Echoes of Room 302",
            cover_image_path=str(cover_image),
        )
        assert success, "Direct conversion to MP3 failed!"
        assert mp3_out.exists() and mp3_out.stat().st_size > 0, "MP3 file is empty or missing!"

        # Verify MP3 metadata
        id3 = ID3(str(mp3_out))
        assert "TIT2" in id3 and str(id3["TIT2"]) == "Toluca Overlook"
        assert "TPE1" in id3 and str(id3["TPE1"]) == "Silent Hill Survivor"
        assert any(k.startswith("APIC") for k in id3.keys()), "MP3 has no embedded cover art APIC frame!"
        print(f"Direct MP3 conversion verified ({mp3_out.stat().st_size / 1024:.1f} KB)")

        # 2. Test Direct Conversion to M4A (AAC)
        m4a_out = tmp_path / "test_converted.m4a"
        success_m4a = upscaler.process_track(
            input_path=str(sample_track),
            output_path=str(m4a_out),
            mode="direct",
            target_format="m4a",
            target_bitrate="256k",
            title="Toluca Overlook",
            artist="Silent Hill Survivor",
            album="Echoes of Room 302",
            cover_image_path=str(cover_image),
        )
        assert success_m4a, "Direct conversion to M4A failed!"
        assert m4a_out.exists() and m4a_out.stat().st_size > 0, "M4A file is empty or missing!"

        # Verify M4A metadata
        mp4 = MP4(str(m4a_out))
        assert '\xa9nam' in mp4 and mp4['\xa9nam'] == ["Toluca Overlook"]
        assert '\xa9ART' in mp4 and mp4['\xa9ART'] == ["Silent Hill Survivor"]
        assert 'covr' in mp4 and len(mp4['covr']) > 0, "M4A has no embedded cover art!"
        print(f"Direct M4A conversion verified ({m4a_out.stat().st_size / 1024:.1f} KB)")

        # 3. Test Direct Conversion to Opus
        opus_out = tmp_path / "test_converted.opus"
        success_opus = upscaler.process_track(
            input_path=str(sample_track),
            output_path=str(opus_out),
            mode="direct",
            target_format="opus",
            target_bitrate="160k",
            title="Toluca Overlook",
            artist="Silent Hill Survivor",
            album="Echoes of Room 302",
        )
        assert success_opus, "Direct conversion to Opus failed!"
        assert opus_out.exists() and opus_out.stat().st_size > 0, "Opus file is empty or missing!"

        ogg_opus = OggOpus(str(opus_out))
        assert "title" in ogg_opus and ogg_opus["title"] == ["Toluca Overlook"]
        print(f"Direct Opus conversion verified ({opus_out.stat().st_size / 1024:.1f} KB)")

        # 4. Test Direct Conversion to FLAC
        flac_out = tmp_path / "test_converted.flac"
        success_flac = upscaler.process_track(
            input_path=str(sample_track),
            output_path=str(flac_out),
            mode="direct",
            target_format="flac",
            title="Toluca Overlook",
            artist="Silent Hill Survivor",
            cover_image_path=str(cover_image),
        )
        assert success_flac, "Direct conversion to FLAC failed!"
        assert flac_out.exists() and flac_out.stat().st_size > 0, "FLAC file is empty or missing!"

        flac = FLAC(str(flac_out))
        assert "title" in flac and flac["title"] == ["Toluca Overlook"]
        assert len(flac.pictures) > 0, "FLAC has no embedded cover art!"
        print(f"Direct FLAC conversion verified ({flac_out.stat().st_size / 1024:.1f} KB)")

    print("Direct conversion and metadata tests PASSED!")


def test_stealth_dsp_processing():
    print("Testing Stealth Anti-AI DSP processing...")
    sample_dir = Path(".samples/Album 1")
    sample_track = sample_dir / "00 - Tape 00_ Toluca Overlook (Prologue).wav"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        stealth_out = tmp_path / "test_stealth.mp3"

        # Run DSP mode with stealth preset
        success = upscaler.process_track(
            input_path=str(sample_track),
            output_path=str(stealth_out),
            mode="dsp",
            dsp_preset="stealth",
            target_format="mp3",
            target_bitrate="320k",
            title="Stealth Clean Track",
            artist="AI Anonymizer",
        )
        assert success, "Stealth DSP processing failed!"
        assert stealth_out.exists() and stealth_out.stat().st_size > 0, "Stealth output is empty or missing!"
        print(f"Stealth DSP processing verified ({stealth_out.stat().st_size / 1024:.1f} KB)")

    print("Stealth Anti-AI DSP tests PASSED!")


if __name__ == "__main__":
    test_payload_normalization()
    test_direct_conversion_and_metadata()
    test_stealth_dsp_processing()
    print("\nALL MILESTONE 1 TESTS PASSED SUCCESSFULLY!")
