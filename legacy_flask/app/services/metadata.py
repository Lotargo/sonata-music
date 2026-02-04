import os
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from werkzeug.utils import secure_filename


def extract_metadata(filepath, static_covers_dir):
    """
    Extract title, artist, and cover image from an audio file.
    Saves the cover image to static_covers_dir.
    """
    metadata = {"title": None, "artist": None, "cover_path": None}

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
            # Save cover data to file
            filename = os.path.basename(filepath)
            cover_filename = f"cover_{secure_filename(filename)}.jpg"
            cover_path = os.path.join(static_covers_dir, cover_filename)

            with open(cover_path, "wb") as f:
                f.write(cover_data)

            # Return path relative to static
            metadata["cover_path"] = f"static/covers/{cover_filename}"

    except Exception as e:
        print(f"Error extracting metadata from {filepath}: {e}")

    return metadata
