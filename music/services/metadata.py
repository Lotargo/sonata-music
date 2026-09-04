import os
import logging
from pathlib import Path
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TPE1, TPE2, TALB, TDRC, TYER, TRCK, TPOS,
    TCON, COMM, TBPM, TKEY, TSSE, TCOP, APIC, ID3NoHeaderError
)
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from werkzeug.utils import secure_filename
from django.conf import settings

logger = logging.getLogger(__name__)


def extract_metadata(filepath, output_dir=None):
    """
    Extract title, artist, and cover image from an audio file.
    If output_dir is provided, saves the cover image there.
    Returns a dictionary with metadata and the relative path to the cover.
    """
    metadata = {"title": None, "artist": None, "cover_path": None}
    path = Path(filepath)

    if output_dir is None:
        output_path = Path(settings.MEDIA_ROOT) / 'covers'
    else:
        output_path = Path(output_dir)

    try:
        audio = File(str(path))
        if audio is None:
            return metadata

        # Extract title and artist
        metadata["title"] = audio.get("title", [None])[0] if "title" in audio else None
        metadata["artist"] = (
            audio.get("artist", [None])[0] if "artist" in audio else None
        )

        # Try to find a cover image
        cover_data = None

        if path.suffix.lower() == ".mp3":
            try:
                tags = ID3(str(path))
                for tag in tags.values():
                    if isinstance(tag, APIC):
                        cover_data = tag.data
                        break
            except Exception:
                pass
        else:
            # For other formats, mutagen might have 'pictures' or 'artwork'
            if hasattr(audio, "pictures") and audio.pictures:
                cover_data = audio.pictures[0].data
            elif "covr" in audio:  # MP4 / M4A
                cover_data = audio["covr"][0]

        if cover_data:
            output_path.mkdir(parents=True, exist_ok=True)
            # Replace extension with .jpg
            cover_filename = f"cover_{secure_filename(path.stem)}.jpg"
            cover_file = output_path / cover_filename

            cover_file.write_bytes(cover_data)

            # Return path relative to MEDIA_ROOT
            rel_path = str(cover_file.relative_to(settings.MEDIA_ROOT)).replace('\\', '/')
            metadata["cover_path"] = rel_path

    except Exception as e:
        logger.error(f"Error extracting metadata from {filepath}: {e}")

    return metadata


def clean_and_embed_metadata(
    filepath,
    title=None,
    artist=None,
    album=None,
    cover_image_path=None,
    year=None,
    track_num=None,
    total_tracks=None,
    album_artist=None,
    genre=None,
    disc_num=None,
    total_discs=None,
    comment=None,
    bpm=None,
    key=None,
    copyright=None,
):
    """
    Cleans unwanted AI-generator and technical encoder tags, and embeds clean metadata (title,
    artist, album, year, track number, genre, cover art, etc.) into the target audio file.
    Supports MP3, M4A, FLAC, OGG, Opus.
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"File not found for metadata embedding: {filepath}")
        return False

    cover_bytes = None
    if cover_image_path:
        cover_file = Path(cover_image_path)
        if not cover_file.exists() and hasattr(settings, 'MEDIA_ROOT'):
            media_candidate = Path(settings.MEDIA_ROOT) / cover_image_path
            if media_candidate.exists():
                cover_file = media_candidate

        if cover_file.exists():
            try:
                cover_bytes = cover_file.read_bytes()
            except Exception as e:
                logger.warning(f"Failed to read cover image {cover_file}: {e}")

    ext = path.suffix.lower()

    try:
        if ext == ".mp3":
            try:
                tags = ID3(str(path))
            except ID3NoHeaderError:
                tags = ID3()

            # Clean out AI-generator footprints (UUIDs, prompt comments, encoder traces)
            for k in list(tags.keys()):
                if k.startswith("COMM") or k.startswith("TXXX") or k in ("TSSE", "TENC"):
                    del tags[k]

            if title:
                tags["TIT2"] = TIT2(encoding=3, text=str(title))
            if artist:
                tags["TPE1"] = TPE1(encoding=3, text=str(artist))
            if album_artist or artist:
                tags["TPE2"] = TPE2(encoding=3, text=str(album_artist or artist))
            if album:
                tags["TALB"] = TALB(encoding=3, text=str(album))
            if year:
                tags["TDRC"] = TDRC(encoding=3, text=str(year))
                tags["TYER"] = TYER(encoding=3, text=str(year))
            if track_num is not None:
                trck_str = f"{track_num}/{total_tracks}" if total_tracks else str(track_num)
                tags["TRCK"] = TRCK(encoding=3, text=trck_str)
            if disc_num is not None:
                disc_str = f"{disc_num}/{total_discs}" if total_discs else str(disc_num)
                tags["TPOS"] = TPOS(encoding=3, text=disc_str)
            if genre:
                tags["TCON"] = TCON(encoding=3, text=str(genre))
            if comment:
                tags["COMM"] = COMM(encoding=3, lang='eng', desc='', text=str(comment))
            if bpm:
                try:
                    tags["TBPM"] = TBPM(encoding=3, text=str(int(round(float(bpm)))))
                except Exception:
                    tags["TBPM"] = TBPM(encoding=3, text=str(bpm))
            if key:
                tags["TKEY"] = TKEY(encoding=3, text=str(key))
            if copyright:
                tags["TCOP"] = TCOP(encoding=3, text=str(copyright))

            # Set clean studio encoder header
            tags["TSSE"] = TSSE(encoding=3, text="LAME 3.100")

            if cover_bytes:
                mime = 'image/png' if cover_bytes.startswith(b'\x89PNG') else 'image/jpeg'
                tags.delall("APIC")
                tags.add(APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=cover_bytes
                ))

            tags.save(str(path), v2_version=3)
            logger.info(f"Embedded clean MP3 tags for {path.name}")
            return True

        elif ext in (".m4a", ".mp4"):
            audio = MP4(str(path))
            # Clean comments and tool markers
            for k in list(audio.keys()):
                if k in ('\xa9cmt', '\xa9too', '\xa9enc', 'cprt'):
                    del audio[k]

            if title:
                audio['\xa9nam'] = [str(title)]
            if artist:
                audio['\xa9ART'] = [str(artist)]
            if album_artist or artist:
                audio['aART'] = [str(album_artist or artist)]
            if album:
                audio['\xa9alb'] = [str(album)]
            if year:
                audio['\xa9day'] = [str(year)]
            if track_num is not None:
                tr_num = int(track_num)
                tr_tot = int(total_tracks) if total_tracks else 0
                audio['trkn'] = [(tr_num, tr_tot)]
            if disc_num is not None:
                d_num = int(disc_num)
                d_tot = int(total_discs) if total_discs else 0
                audio['disk'] = [(d_num, d_tot)]
            if genre:
                audio['\xa9gen'] = [str(genre)]
            if comment:
                audio['\xa9cmt'] = [str(comment)]
            if copyright:
                audio['cprt'] = [str(copyright)]

            if cover_bytes:
                imageformat = MP4Cover.FORMAT_PNG if cover_bytes.startswith(b'\x89PNG') else MP4Cover.FORMAT_JPEG
                audio['covr'] = [MP4Cover(cover_bytes, imageformat=imageformat)]

            audio.save(str(path))
            logger.info(f"Embedded clean M4A tags for {path.name}")
            return True

        elif ext == ".flac":
            audio = FLAC(str(path))
            # Wipe comments
            if "comment" in audio:
                del audio["comment"]

            if title:
                audio["title"] = str(title)
            if artist:
                audio["artist"] = str(artist)
            if album_artist or artist:
                audio["albumartist"] = str(album_artist or artist)
            if album:
                audio["album"] = str(album)
            if year:
                audio["date"] = str(year)
            if track_num is not None:
                audio["tracknumber"] = str(track_num)
            if total_tracks is not None:
                audio["tracktotal"] = str(total_tracks)
            if disc_num is not None:
                audio["discnumber"] = str(disc_num)
            if genre:
                audio["genre"] = str(genre)
            if comment:
                audio["comment"] = str(comment)
            if bpm:
                audio["bpm"] = str(bpm)
            if key:
                audio["key"] = str(key)
            if copyright:
                audio["copyright"] = str(copyright)

            if cover_bytes:
                pic = Picture()
                pic.data = cover_bytes
                pic.type = 3
                pic.mime = 'image/png' if cover_bytes.startswith(b'\x89PNG') else 'image/jpeg'
                pic.desc = 'Cover'
                audio.clear_pictures()
                audio.add_picture(pic)

            audio.save(str(path))
            logger.info(f"Embedded clean FLAC tags for {path.name}")
            return True

        elif ext == ".ogg":
            try:
                audio = OggVorbis(str(path))
                if title:
                    audio["title"] = str(title)
                if artist:
                    audio["artist"] = str(artist)
                if album:
                    audio["album"] = str(album)
                if year:
                    audio["date"] = str(year)
                if track_num is not None:
                    audio["tracknumber"] = str(track_num)
                if genre:
                    audio["genre"] = str(genre)
                audio.save(str(path))
                logger.info(f"Embedded clean OGG tags for {path.name}")
                return True
            except Exception as e:
                logger.warning(f"Failed to write OGG tags: {e}")

        elif ext == ".opus":
            try:
                audio = OggOpus(str(path))
                if title:
                    audio["title"] = str(title)
                if artist:
                    audio["artist"] = str(artist)
                if album:
                    audio["album"] = str(album)
                if year:
                    audio["date"] = str(year)
                if track_num is not None:
                    audio["tracknumber"] = str(track_num)
                if genre:
                    audio["genre"] = str(genre)
                audio.save(str(path))
                logger.info(f"Embedded clean Opus tags for {path.name}")
                return True
            except Exception as e:
                logger.warning(f"Failed to write Opus tags: {e}")

    except Exception as e:
        logger.error(f"Failed to clean and embed metadata for {filepath}: {e}")

    return False
