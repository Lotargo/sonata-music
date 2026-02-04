import os
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from werkzeug.utils import secure_filename
from django.conf import settings

def extract_metadata(filepath, output_dir=None):
    """
    Extract title, artist, and cover image from an audio file.
    If output_dir is provided, saves the cover image there.
    Returns a dictionary with metadata and the relative path to the cover.
    """
    metadata = {"title": None, "artist": None, "cover_path": None}

    # Default output dir to MEDIA_ROOT/covers if not specified
    if output_dir is None:
        output_dir = os.path.join(settings.MEDIA_ROOT, 'covers')

    try:
        audio = File(filepath)
        if audio is None:
            return metadata

        # Extract title and artist
        metadata["title"] = audio.get("title", [None])[0] if "title" in audio else None
        metadata["artist"] = (
            audio.get("artist", [None])[0] if "artist" in audio else None
        )

        # Try to find a cover image
        cover_data = None

        if filepath.lower().endswith(".mp3"):
            try:
                tags = ID3(filepath)
                for tag in tags.values():
                    if isinstance(tag, APIC):
                        cover_data = tag.data
                        break
            except Exception:
                pass
        else:
            # For other formats, mutagen might have 'pics' or 'artwork'
            if hasattr(audio, "pictures") and audio.pictures:
                cover_data = audio.pictures[0].data
            elif "covr" in audio:  # MP4
                cover_data = audio["covr"][0]

        if cover_data:
            os.makedirs(output_dir, exist_ok=True)
            # Save cover data to file
            filename = os.path.basename(filepath)
            # Replace extension with .jpg (naive but works for most embedded art)
            base_name = os.path.splitext(filename)[0]
            cover_filename = f"cover_{secure_filename(base_name)}.jpg"
            cover_path = os.path.join(output_dir, cover_filename)

            with open(cover_path, "wb") as f:
                f.write(cover_data)

            # Return path relative to MEDIA_ROOT
            # Assuming output_dir is inside MEDIA_ROOT
            rel_path = os.path.relpath(cover_path, settings.MEDIA_ROOT)
            metadata["cover_path"] = rel_path

    except Exception as e:
        print(f"Error extracting metadata from {filepath}: {e}")

    return metadata
