document.addEventListener('DOMContentLoaded', () => {
    initPlayer();
});

// State
window.tracks = [];
let currentTrackId = null;
let isPlaying = false;
let isShuffle = false;
let isRepeat = false;
let audioContext = null;
let analyser = null;
let frequencyData = null;
let mediaSource = null;
let visualTick = 0;
let libraryPollTimer = null;
let lastLibrarySignature = '';
let audioFadeFrame = null;
let backgroundPlaybackWanted = false;
let suppressBackgroundResume = false;
let isScrubbing = false;

// Elements
const audio = document.getElementById('audio-player');
const playPauseBtn = document.getElementById('play-pause-btn');
const progressTrack = document.getElementById('progress-track');
const progressBar = document.getElementById('progress-bar');
const currentTimeEl = document.getElementById('current-time');
const durationEl = document.getElementById('duration');
const volumeSlider = document.getElementById('volume-slider');
const playerTitle = document.getElementById('player-title');
const playerArtist = document.getElementById('player-artist');
const playerCover = document.getElementById('player-cover');
const playerCoverPlaceholder = document.getElementById('player-cover-placeholder');
const likeBtn = document.getElementById('like-btn');
const dislikeBtn = document.getElementById('dislike-btn');
const muteBtn = document.getElementById('mute-btn');
let lastNonZeroVolume = 1;

// Init
async function initPlayer() {
    restoreVolume();
    initScrubbing();
    await fetchLibrary({ render: true });
    startLibraryPolling();
    startVisualizationLoop();
    updateMuteButton();
}

function restoreVolume() {
    const savedVol = localStorage.getItem('player_volume');
    if (savedVol !== null) {
        audio.volume = parseFloat(savedVol);
        if(volumeSlider) volumeSlider.value = audio.volume;
    }
    lastNonZeroVolume = audio.volume > 0 ? audio.volume : 1;
}

async function fetchLibrary(options = {}) {
    try {
        const response = await fetch('/library/', { cache: 'no-store' });
        if (response.ok) {
            const nextTracks = await response.json();
            window.tracks = Array.isArray(nextTracks) ? nextTracks : [];
            if (typeof normalizeTrackDisplayTitles === 'function') {
                normalizeTrackDisplayTitles();
            }
            document.dispatchEvent(new CustomEvent('libraryLoaded', { detail: { tracks: window.tracks } }));
            if (options.render) renderLibraryFromTracks();
            return window.tracks;
        }
    } catch (e) {
        console.error("Failed to fetch library", e);
    }
    return window.tracks;
}

function startLibraryPolling() {
    if (libraryPollTimer) return;
    libraryPollTimer = window.setInterval(async () => {
        await fetchLibrary({ render: true });
    }, 3000);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function getTrackTitle(track) {
    return track?.display_title || track?.title || track?.filename || 'Без названия';
}

function getStatusLabel(track) {
    const map = {
        pending: 'Pending',
        processing: 'Processing',
        completed: 'Completed',
        failed: 'Failed'
    };
    return track?.status_display || map[track?.status] || track?.status || 'Pending';
}

function coverMarkup(track, placeholderClass = '') {
    if (track.cover_path) {
        return `<img src="${escapeHtml(track.cover_path)}" alt="" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.classList.remove('hidden');"><div class="${placeholderClass || 'cover-placeholder'} hidden"><i data-lucide="music"></i></div>`;
    }
    return placeholderClass
        ? `<div class="${placeholderClass}"><i data-lucide="music"></i></div>`
        : '<i data-lucide="music"></i>';
}

function trackRowMarkup(track) {
    const id = Number(track.id);
    const title = escapeHtml(getTrackTitle(track));
    const artist = escapeHtml(track.artist || 'Неизвестный исполнитель');
    const status = escapeHtml(track.status || 'pending');
    const statusLabel = escapeHtml(getStatusLabel(track));
    const detailsHidden = track.status === 'completed' ? '' : ' hidden';

    return `
        <article class="track-row group" data-track-row-id="${id}">
            <button onclick="playTrack(${id})" class="row-play play-btn" data-track-id="${id}" aria-label="Играть">
                <i data-lucide="play"></i>
            </button>
            <div class="row-cover">
                ${coverMarkup(track)}
            </div>
            <div class="row-main">
                <h3 title="${title}" data-track-title>${title}</h3>
                <p>${artist}</p>
            </div>
            <span class="status-badge status-${status}" data-track-status>${statusLabel}</span>
            <span class="row-stat" data-track-plays>${Number(track.play_count || 0)} просл.</span>
            <div class="row-actions">
                <button onclick="openDetails(${id})" class="icon-btn small${detailsHidden}" title="Детали" data-track-details><i data-lucide="bar-chart-2"></i></button>
                <button onclick="editTrack(${id})" class="icon-btn small" title="Переименовать"><i data-lucide="pencil"></i></button>
                <button onclick="deleteTrack(${id})" class="icon-btn small danger" title="Удалить"><i data-lucide="trash-2"></i></button>
            </div>
        </article>
    `;
}

function coverCardMarkup(track) {
    const id = Number(track.id);
    const title = escapeHtml(getTrackTitle(track));
    const artist = escapeHtml(track.artist || 'Неизвестный исполнитель');

    return `
        <article class="cover-card" onclick="playTrack(${id})" data-track-card-id="${id}">
            <div class="cover-art">
                ${coverMarkup(track, 'cover-placeholder')}
                <button class="floating-play play-btn" data-track-id="${id}" aria-label="Играть">
                    <i data-lucide="play"></i>
                </button>
            </div>
            <h3 title="${title}" data-track-title>${title}</h3>
            <p>${artist}</p>
        </article>
    `;
}

function renderLibraryFromTracks(force = false) {
    const rowTable = document.querySelector('.home-track-section .track-table');
    const coverGrid = document.querySelector('.cover-grid');
    if (!rowTable && !coverGrid) return;

    const signature = JSON.stringify(window.tracks.map(track => ({
        id: track.id,
        title: getTrackTitle(track),
        artist: track.artist,
        status: track.status,
        status_display: getStatusLabel(track),
        cover_path: track.cover_path,
        processed_path: track.processed_path,
        play_count: track.play_count,
        is_liked: track.is_liked,
    })));

    if (!force && signature === lastLibrarySignature) return;
    lastLibrarySignature = signature;

    if (rowTable) {
        rowTable.innerHTML = window.tracks.map(trackRowMarkup).join('');
    }

    if (coverGrid) {
        coverGrid.innerHTML = window.tracks.slice(0, 5).map(coverCardMarkup).join('');
    }

    if (currentTrackId) updateListPlayButtons(currentTrackId, isPlaying);
    lucide.createIcons();
}

// Global Play Function
window.playTrack = async (id) => {
    if (!window.tracks.length) await fetchLibrary({ render: true });

    const track = window.tracks.find(t => Number(t.id) === Number(id));
    if (!track) return;

    if (currentTrackId === id) {
        togglePlay();
        return;
    }

    currentTrackId = id;
    loadTrack(track);
    setupAudioAnalysis();
    await playAudioWithFade();

    if (typeof updateBackground === 'function') {
        updateBackground(track.cover_path);
    }
};

function setupAudioAnalysis() {
    if (!window.AudioContext && !window.webkitAudioContext) return;
    try {
        if (!audioContext) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            audioContext = new AudioContextClass();
        }
        if (audioContext && audioContext.state === 'suspended') {
            audioContext.resume().catch(() => {});
        }
        if (analyser) return;

        analyser = audioContext.createAnalyser();
        analyser.fftSize = 128;
        analyser.smoothingTimeConstant = 0.85;
        frequencyData = new Uint8Array(analyser.frequencyBinCount);
        mediaSource = audioContext.createMediaElementSource(audio);
        mediaSource.connect(analyser);
        analyser.connect(audioContext.destination);
    } catch (e) {
        console.warn('AudioContext / Analyser setup skipped:', e);
    }
}

function loadTrack(track) {
    let url = '';
    if (track.status === 'completed' && track.processed_path) {
        url = track.processed_path;
    } else if (track.audio_url) {
        url = track.audio_url;
    } else {
        url = `/media/uploads/${track.filename}`;
    }

    cancelAudioFade();
    audio.src = url;

    playerTitle.textContent = getTrackTitle(track);
    playerArtist.textContent = track.artist || 'Unknown Artist';
    if (currentTimeEl) currentTimeEl.textContent = '0:00';
    if (durationEl) durationEl.textContent = formatTime(track.duration || 0);
    if (progressBar) progressBar.style.width = '0%';

    if (track.cover_path) {
        playerCover.src = track.cover_path;
        playerCover.classList.remove('hidden');
        playerCoverPlaceholder.classList.add('hidden');
    } else {
        playerCover.classList.add('hidden');
        playerCoverPlaceholder.classList.remove('hidden');
    }

    updateLikeBtn(track.is_liked);
    updateDislikeBtn(track.is_disliked);
    fetch(`/api/play/${track.id}/`, { method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken')} });
}

function getTargetVolume() {
    const fromSlider = parseFloat(volumeSlider?.value ?? audio.volume ?? 1);
    if (Number.isFinite(fromSlider)) return Math.max(0, Math.min(1, fromSlider));
    return 1;
}

function cancelAudioFade() {
    if (audioFadeFrame) {
        cancelAnimationFrame(audioFadeFrame);
        audioFadeFrame = null;
    }
}

function fadeAudioTo(target, duration = 240) {
    cancelAudioFade();
    const startVolume = audio.volume;
    const targetVolume = Math.max(0, Math.min(1, target));
    const startedAt = performance.now();

    return new Promise(resolve => {
        const step = (now) => {
            const progress = Math.min(1, (now - startedAt) / duration);
            audio.volume = startVolume + ((targetVolume - startVolume) * progress);
            if (progress < 1) {
                audioFadeFrame = requestAnimationFrame(step);
            } else {
                audio.volume = targetVolume;
                audioFadeFrame = null;
                resolve();
            }
        };
        audioFadeFrame = requestAnimationFrame(step);
    });
}

async function playAudioWithFade(duration = 160) {
    if (!audio.src) return;
    cancelAudioFade();
    let targetVolume = getTargetVolume();
    if (targetVolume <= 0) {
        targetVolume = lastNonZeroVolume > 0 ? lastNonZeroVolume : 0.8;
        if (volumeSlider) volumeSlider.value = targetVolume;
        localStorage.setItem('player_volume', targetVolume);
        updateMuteButton();
    }
    audio.volume = targetVolume;
    try {
        if (audioContext && audioContext.state === 'suspended') {
            await audioContext.resume().catch(() => {});
        }
        await audio.play();
        setIsPlaying(true);
    } catch (e) {
        console.error('Playback failed:', e);
    }
}

async function pauseAudioWithFade(duration = 220) {
    if (!audio || audio.paused) {
        setIsPlaying(false);
        return;
    }

    suppressBackgroundResume = true;
    const targetVolume = getTargetVolume();
    await fadeAudioTo(0, duration);
    audio.pause();
    audio.volume = targetVolume;
    setIsPlaying(false);
    window.setTimeout(() => { suppressBackgroundResume = false; }, 250);
}

async function releaseCurrentTrackForDeletion() {
    cancelAudioFade();
    if (!audio.paused) await pauseAudioWithFade(120);
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    currentTrackId = null;
    setIsPlaying(false);
    playerTitle.textContent = 'Выберите трек';
    playerArtist.textContent = 'Музыка ждёт';
    playerCover.classList.add('hidden');
    playerCoverPlaceholder.classList.remove('hidden');
}

// Controls
window.togglePlay = () => {
    if (!currentTrackId) return;

    if (audio.paused) {
        playAudioWithFade();
    } else {
        pauseAudioWithFade();
    }
};

function setIsPlaying(playing) {
    isPlaying = playing;
    if (playPauseBtn) {
        playPauseBtn.innerHTML = playing
            ? '<i data-lucide="pause" class="fill-current w-4 h-4"></i>'
            : '<i data-lucide="play" class="fill-current w-4 h-4 ml-0.5"></i>';
    }
    lucide.createIcons();
    updateListPlayButtons(currentTrackId, playing);
}

function startVisualizationLoop() {
    const animate = () => {
        visualTick += 0.016;
        let energy = 0.18 + (Math.sin(visualTick * 0.9) * 0.03) + (Math.cos(visualTick * 0.42) * 0.02);

        if (analyser && !audio.paused) {
            analyser.getByteFrequencyData(frequencyData);
            let sum = 0;
            for (let i = 0; i < frequencyData.length; i += 1) {
                sum += frequencyData[i];
            }
            const average = sum / (frequencyData.length * 255);
            energy = 0.16 + (average * 0.7);
        }

        if (typeof setVisualEnergy === 'function') {
            setVisualEnergy(energy);
        }

        window.requestAnimationFrame(animate);
    };

    window.requestAnimationFrame(animate);
}

function updateListPlayButtons(id, playing) {
    if (!id) return;
    const btns = document.querySelectorAll(`.play-btn[data-track-id="${id}"]`);
    btns.forEach(btn => {
        btn.innerHTML = playing
            ? '<i data-lucide="pause" class="fill-current w-4 h-4"></i>'
            : '<i data-lucide="play" class="fill-current w-4 h-4 ml-1"></i>';
    });
    document.querySelectorAll(`.play-btn:not([data-track-id="${id}"])`).forEach(btn => {
        btn.innerHTML = '<i data-lucide="play" class="fill-current w-4 h-4 ml-1"></i>';
    });
    lucide.createIcons();
}

// Events
audio.addEventListener('timeupdate', () => {
    if (isScrubbing) return;
    if (!audio.duration || isNaN(audio.duration)) return;
    const percent = Math.min(100, Math.max(0, (audio.currentTime / audio.duration) * 100));
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (currentTimeEl) currentTimeEl.innerText = formatTime(audio.currentTime);
    if (durationEl) durationEl.innerText = formatTime(audio.duration || 0);
    const trackEl = progressTrack || document.getElementById('progress-track');
    if (trackEl) trackEl.setAttribute('aria-valuenow', Math.round(percent));
});

audio.addEventListener('loadedmetadata', () => {
    if (durationEl && audio.duration && !isNaN(audio.duration)) {
        durationEl.innerText = formatTime(audio.duration);
    }
});

audio.addEventListener('ended', () => {
    audio.volume = getTargetVolume();
    if (isRepeat) {
        audio.currentTime = 0;
        playAudioWithFade(120);
    } else {
        playNext();
    }
});

audio.addEventListener('pause', () => {
    if (document.hidden && backgroundPlaybackWanted && currentTrackId && !suppressBackgroundResume) {
        window.setTimeout(() => {
            if (document.hidden && audio.paused && currentTrackId && !suppressBackgroundResume) {
                audio.play().then(() => setIsPlaying(true)).catch(() => {});
            }
        }, 120);
        return;
    }
    setIsPlaying(false);
});

audio.addEventListener('play', () => {
    setIsPlaying(true);
    if (audioContext && audioContext.state === 'suspended') {
        audioContext.resume().catch(() => {});
    }
});

document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        backgroundPlaybackWanted = Boolean(currentTrackId && !audio.paused);
        return;
    }

    if (backgroundPlaybackWanted && currentTrackId && audio.paused && !suppressBackgroundResume) {
        playAudioWithFade(80);
    }
    backgroundPlaybackWanted = false;
});

// Scrubbing & Seeking
function getPercentFromEvent(e, trackEl) {
    const rect = trackEl.getBoundingClientRect();
    if (!rect.width) return 0;
    const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
    const x = clientX - rect.left;
    return Math.min(1, Math.max(0, x / rect.width));
}

function updateProgressVisuals(percent, targetTime) {
    const percentClamped = Math.min(100, Math.max(0, percent * 100));
    if (progressBar) {
        progressBar.style.width = `${percentClamped}%`;
    }
    if (currentTimeEl && Number.isFinite(targetTime)) {
        currentTimeEl.innerText = formatTime(targetTime);
    }
    const trackEl = progressTrack || document.getElementById('progress-track');
    if (trackEl) {
        trackEl.setAttribute('aria-valuenow', Math.round(percentClamped));
    }
}

function initScrubbing() {
    const trackEl = progressTrack || document.getElementById('progress-track');
    if (!trackEl) return;

    const applySeek = (e) => {
        if (!audio.duration || isNaN(audio.duration)) return;
        const percent = getPercentFromEvent(e, trackEl);
        const targetTime = percent * audio.duration;
        if (Number.isFinite(targetTime)) {
            audio.currentTime = targetTime;
            updateProgressVisuals(percent, targetTime);
        }
    };

    const onPointerDown = (e) => {
        if (!audio.duration || isNaN(audio.duration)) return;
        isScrubbing = true;
        trackEl.classList.add('is-scrubbing');
        try {
            trackEl.setPointerCapture(e.pointerId);
        } catch (_) {}

        const percent = getPercentFromEvent(e, trackEl);
        const targetTime = percent * audio.duration;
        updateProgressVisuals(percent, targetTime);
    };

    const onPointerMove = (e) => {
        if (!isScrubbing) return;
        if (!audio.duration || isNaN(audio.duration)) return;

        const percent = getPercentFromEvent(e, trackEl);
        const targetTime = percent * audio.duration;
        updateProgressVisuals(percent, targetTime);
    };

    const onPointerUp = (e) => {
        if (!isScrubbing) return;
        isScrubbing = false;
        trackEl.classList.remove('is-scrubbing');
        try {
            trackEl.releasePointerCapture(e.pointerId);
        } catch (_) {}

        applySeek(e);
    };

    trackEl.addEventListener('pointerdown', onPointerDown);
    trackEl.addEventListener('pointermove', onPointerMove);
    trackEl.addEventListener('pointerup', onPointerUp);
    trackEl.addEventListener('pointercancel', onPointerUp);
    trackEl.addEventListener('click', applySeek);

    trackEl.addEventListener('keydown', (e) => {
        if (!audio.duration || isNaN(audio.duration)) return;
        let nextTime = audio.currentTime;
        if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault();
            nextTime = Math.min(audio.duration, audio.currentTime + 5);
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault();
            nextTime = Math.max(0, audio.currentTime - 5);
        } else if (e.key === 'Home') {
            e.preventDefault();
            nextTime = 0;
        } else if (e.key === 'End') {
            e.preventDefault();
            nextTime = audio.duration;
        } else {
            return;
        }
        audio.currentTime = nextTime;
        const percent = nextTime / audio.duration;
        updateProgressVisuals(percent, nextTime);
    });
}

// Seek fallback
window.seek = (e) => {
    if (!audio.duration || isNaN(audio.duration)) return;
    const trackEl = progressTrack || document.getElementById('progress-track') || e.currentTarget;
    const percent = getPercentFromEvent(e, trackEl);
    const targetTime = percent * audio.duration;
    if (Number.isFinite(targetTime)) {
        audio.currentTime = targetTime;
        updateProgressVisuals(percent, targetTime);
    }
};

// Volume
if (volumeSlider) {
    volumeSlider.addEventListener('input', (e) => {
        const nextVolume = parseFloat(e.target.value);
        audio.volume = nextVolume;
        if (audio.volume > 0) {
            lastNonZeroVolume = audio.volume;
        }
        localStorage.setItem('player_volume', audio.volume);
        updateMuteButton();
    });
}

if (muteBtn) {
    muteBtn.addEventListener('click', () => {
        if (audio.volume > 0 || Number(volumeSlider?.value || 0) > 0) {
            lastNonZeroVolume = getTargetVolume() || lastNonZeroVolume || 1;
            audio.volume = 0;
            if (volumeSlider) volumeSlider.value = 0;
        } else {
            audio.volume = lastNonZeroVolume || 1;
            if (volumeSlider) volumeSlider.value = audio.volume;
        }
        localStorage.setItem('player_volume', volumeSlider ? volumeSlider.value : audio.volume);
        updateMuteButton();
    });
}

// Next/Prev
function playNext() {
    if (!window.tracks.length) return;
    const idx = window.tracks.findIndex(t => Number(t.id) === Number(currentTrackId));
    let nextIdx = idx + 1;
    if (nextIdx >= window.tracks.length) nextIdx = 0;

    if (isShuffle) {
        nextIdx = Math.floor(Math.random() * window.tracks.length);
    }

    playTrack(window.tracks[nextIdx].id);
}

function playPrev() {
    if (!window.tracks.length) return;
    const idx = window.tracks.findIndex(t => Number(t.id) === Number(currentTrackId));
    let prevIdx = idx - 1;
    if (prevIdx < 0) prevIdx = window.tracks.length - 1;

    playTrack(window.tracks[prevIdx].id);
}

document.addEventListener('DOMContentLoaded', () => {
    const skipBack = document.getElementById('btn-prev');
    const skipFwd = document.getElementById('btn-next');
    const shuffleBtn = document.getElementById('btn-shuffle');
    const repeatBtn = document.getElementById('btn-repeat');

    if (skipBack) skipBack.onclick = playPrev;
    if (skipFwd) skipFwd.onclick = playNext;

    if (shuffleBtn) shuffleBtn.onclick = () => {
        isShuffle = !isShuffle;
        shuffleBtn.classList.toggle('text-yandex-yellow');
        shuffleBtn.classList.toggle('text-gray-400');
    };

    if (repeatBtn) repeatBtn.onclick = () => {
        isRepeat = !isRepeat;
        repeatBtn.classList.toggle('text-yandex-yellow');
        repeatBtn.classList.toggle('text-gray-400');
    };
});

// Helpers
function formatTime(seconds) {
    if (isNaN(seconds)) return "0:00";
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${sec.toString().padStart(2, '0')}`;
}

window.toggleLikeCurrentTrack = async () => {
    if (!currentTrackId) return;

    try {
        const res = await fetch(`/api/like/${currentTrackId}/`, {
             method: 'POST',
             headers: {'X-CSRFToken': getCookie('csrftoken')}
        });
        const data = await res.json();
        updateLikeBtn(data.is_liked);
        updateDislikeBtn(data.is_disliked);
        const track = window.tracks.find(t => Number(t.id) === Number(currentTrackId));
        if (track) {
            track.is_liked = data.is_liked;
            track.is_disliked = data.is_disliked;
        }
    } catch(e) {
        console.error(e);
    }
};

window.toggleDislikeCurrentTrack = async () => {
    if (!currentTrackId) return;

    try {
        const res = await fetch(`/api/dislike/${currentTrackId}/`, {
             method: 'POST',
             headers: {'X-CSRFToken': getCookie('csrftoken')}
        });
        const data = await res.json();
        updateLikeBtn(data.is_liked);
        updateDislikeBtn(data.is_disliked);
        const track = window.tracks.find(t => Number(t.id) === Number(currentTrackId));
        if (track) {
            track.is_liked = data.is_liked;
            track.is_disliked = data.is_disliked;
        }
    } catch(e) {
        console.error(e);
    }
};

function updateLikeBtn(isLiked) {
    if (!likeBtn) return;
    likeBtn.classList.toggle('is-liked', Boolean(isLiked));
    likeBtn.classList.toggle('text-red-500', Boolean(isLiked));
    likeBtn.classList.toggle('fill-current', Boolean(isLiked));
}

function updateDislikeBtn(isDisliked) {
    if (!dislikeBtn) return;
    dislikeBtn.classList.toggle('is-disliked', Boolean(isDisliked));
}

function updateMuteButton() {
    if (!muteBtn) return;

    const isMuted = getTargetVolume() === 0;
    muteBtn.classList.toggle('is-muted', isMuted);
    muteBtn.title = isMuted ? 'Включить звук' : 'Выключить звук';
    muteBtn.setAttribute('aria-label', muteBtn.title);
    muteBtn.innerHTML = isMuted
        ? '<i data-lucide="volume-x"></i>'
        : '<i data-lucide="volume-2"></i>';
    lucide.createIcons();
}

window.pauseMainPlayerForComparison = async () => {
    if (currentTrackId && !audio.paused) {
        await pauseAudioWithFade(160);
        return true;
    }
    return false;
};

window.deleteTrack = async (id) => {
    if (!confirm('Удалить этот трек?')) return;

    const numericId = Number(id);
    try {
        if (currentTrackId === numericId) {
            await releaseCurrentTrackForDeletion();
        }

        if (typeof closeDetailsModal === 'function') {
            const detailsModal = document.getElementById('details-modal');
            if (detailsModal && !detailsModal.classList.contains('hidden')) closeDetailsModal();
        }

        const response = await fetch(`/delete/${numericId}/`, {
            method: 'DELETE',
            headers: {'X-CSRFToken': getCookie('csrftoken')}
        });

        if (!response.ok) {
            let message = 'Delete failed';
            try {
                const data = await response.json();
                message = data.error || data.message || message;
            } catch (_) {}
            throw new Error(message);
        }

        window.tracks = window.tracks.filter(track => Number(track.id) !== numericId);
        renderLibraryFromTracks(true);
        await fetchLibrary({ render: true });
    } catch(e) {
        console.error(e);
        alert('Не удалось удалить трек: ' + e.message);
    }
};
