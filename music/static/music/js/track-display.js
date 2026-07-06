function getDisplayFilenameFromUrl(value) {
    if (!value) return '';
    const clean = String(value).split('?')[0].split('#')[0];
    const name = clean.substring(clean.lastIndexOf('/') + 1);
    try {
        return decodeURIComponent(name);
    } catch (_) {
        return name;
    }
}

function isFileLikeAudioTitle(title, originalName) {
    const normalized = (title || '').trim().toLowerCase();
    if (!normalized) return true;
    if (originalName && normalized === originalName.toLowerCase()) return true;
    return /\.(mp3|wav|flac|ogg|m4a|aac|aiff|aif)$/i.test(normalized);
}

function getPlayableDisplayTitle(track) {
    if (!track) return '';
    const originalName = track.filename || getDisplayFilenameFromUrl(track.audio_url);
    const processedName = getDisplayFilenameFromUrl(track.processed_path);
    if (track.status === 'completed' && processedName && isFileLikeAudioTitle(track.title, originalName)) {
        return processedName;
    }
    return track.title || processedName || originalName || 'Без названия';
}

function normalizeTrackDisplayTitles() {
    if (!Array.isArray(window.tracks)) return;
    window.tracks.forEach(track => {
        track.display_title = getPlayableDisplayTitle(track);
        if (isFileLikeAudioTitle(track.title, track.filename) && track.display_title) {
            track.title = track.display_title;
        }
    });
}

document.addEventListener('libraryLoaded', normalizeTrackDisplayTitles);
normalizeTrackDisplayTitles();
