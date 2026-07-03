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

// Elements
const audio = document.getElementById('audio-player');
const playPauseBtn = document.getElementById('play-pause-btn');
const progressBar = document.getElementById('progress-bar');
const currentTimeEl = document.getElementById('current-time');
const durationEl = document.getElementById('duration');
const volumeSlider = document.getElementById('volume-slider');
const playerTitle = document.getElementById('player-title');
const playerArtist = document.getElementById('player-artist');
const playerCover = document.getElementById('player-cover');
const playerCoverPlaceholder = document.getElementById('player-cover-placeholder');
const likeBtn = document.getElementById('like-btn');
const karaokeLink = document.getElementById('karaoke-link');
const muteBtn = document.getElementById('mute-btn');
let lastNonZeroVolume = 1;

// Init
async function initPlayer() {
    await fetchLibrary();
    startVisualizationLoop();

    // Restore volume
    const savedVol = localStorage.getItem('player_volume');
    if (savedVol !== null) {
        audio.volume = parseFloat(savedVol);
        if(volumeSlider) volumeSlider.value = audio.volume;
    }
    lastNonZeroVolume = audio.volume > 0 ? audio.volume : 1;
    updateMuteButton();
}

async function fetchLibrary() {
    try {
        const response = await fetch('/library/');
        if (response.ok) {
            window.tracks = await response.json();
            // Trigger event for other components if needed
            document.dispatchEvent(new CustomEvent('libraryLoaded'));
        }
    } catch (e) {
        console.error("Failed to fetch library", e);
    }
}

// Global Play Function
window.playTrack = async (id) => {
    // If library not loaded, wait or fetch
    if (!window.tracks.length) await fetchLibrary();

    const track = window.tracks.find(t => t.id === id);
    if (!track) return;

    if (currentTrackId === id) {
        togglePlay();
        return;
    }

    currentTrackId = id;
    loadTrack(track);
    setupAudioAnalysis();
    audio.play();
    setIsPlaying(true);

    // Update Background
    if (typeof updateBackground === 'function') {
        updateBackground(track.cover_path);
    }
};

function setupAudioAnalysis() {
    if (!window.AudioContext && !window.webkitAudioContext) return;
    if (analyser) {
        if (audioContext && audioContext.state === 'suspended') {
            audioContext.resume().catch(() => {});
        }
        return;
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioContextClass();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 128;
    analyser.smoothingTimeConstant = 0.85;
    frequencyData = new Uint8Array(analyser.frequencyBinCount);
    mediaSource = audioContext.createMediaElementSource(audio);
    mediaSource.connect(analyser);
    analyser.connect(audioContext.destination);
}

function loadTrack(track) {
    // Determine URL: Processed > Original
    // track.processed_path is typically a full URL (e.g., /media/processed/file.flac)
    // track.audio_url is the original file URL (e.g., /media/uploads/file.mp3)

    let url = '';
    if (track.status === 'completed' && track.processed_path) {
        url = track.processed_path;
    } else if (track.audio_url) {
        url = track.audio_url;
    } else {
        // Fallback if audio_url is missing for some reason
        url = `/media/uploads/${track.filename}`;
    }

    audio.src = url;

    // Update UI
    playerTitle.textContent = track.title || track.filename;
    playerArtist.textContent = track.artist || 'Unknown Artist';

    if (track.cover_path) {
        playerCover.src = track.cover_path;
        playerCover.classList.remove('hidden');
        playerCoverPlaceholder.classList.add('hidden');
    } else {
        playerCover.classList.add('hidden');
        playerCoverPlaceholder.classList.remove('hidden');
    }

    // Karaoke
    if (karaokeLink) {
        karaokeLink.href = `/karaoke/${track.id}/`;
        karaokeLink.classList.remove('hidden');
    }

    // Like State
    updateLikeBtn(track.is_liked);

    // Record Play
    fetch(`/api/play/${track.id}/`, { method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken')} });
}

// Controls
window.togglePlay = () => {
    if (!currentTrackId) return;

    if (audio.paused) {
        audio.play();
        setIsPlaying(true);
    } else {
        audio.pause();
        setIsPlaying(false);
    }
};

function setIsPlaying(playing) {
    isPlaying = playing;
    playPauseBtn.innerHTML = playing
        ? '<i data-lucide="pause" class="fill-current w-4 h-4"></i>'
        : '<i data-lucide="play" class="fill-current w-4 h-4 ml-0.5"></i>';
    lucide.createIcons();

    // Also update any play buttons in the list if visible
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
    // Look for buttons with data-track-id="id"
    const btns = document.querySelectorAll(`.play-btn[data-track-id="${id}"]`);
    btns.forEach(btn => {
        btn.innerHTML = playing
            ? '<i data-lucide="pause" class="fill-current w-4 h-4"></i>'
            : '<i data-lucide="play" class="fill-current w-4 h-4 ml-1"></i>';
    });
    // Reset others
    document.querySelectorAll(`.play-btn:not([data-track-id="${id}"])`).forEach(btn => {
        btn.innerHTML = '<i data-lucide="play" class="fill-current w-4 h-4 ml-1"></i>';
    });
    lucide.createIcons();
}

// Events
audio.addEventListener('timeupdate', () => {
    const percent = (audio.currentTime / audio.duration) * 100;
    progressBar.style.width = `${percent}%`;
    currentTimeEl.innerText = formatTime(audio.currentTime);
    durationEl.innerText = formatTime(audio.duration || 0);
});

audio.addEventListener('ended', () => {
    if (isRepeat) {
        audio.currentTime = 0;
        audio.play();
    } else {
        playNext();
    }
});

audio.addEventListener('pause', () => {
    setIsPlaying(false);
});

audio.addEventListener('play', () => {
    setIsPlaying(true);
    if (audioContext && audioContext.state === 'suspended') {
        audioContext.resume().catch(() => {});
    }
});

// Seek
window.seek = (e) => {
    if (!audio.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percent = x / rect.width;
    audio.currentTime = percent * audio.duration;
};

// Volume
if (volumeSlider) {
    volumeSlider.addEventListener('input', (e) => {
        audio.volume = parseFloat(e.target.value);
        if (audio.volume > 0) {
            lastNonZeroVolume = audio.volume;
        }
        localStorage.setItem('player_volume', audio.volume);
        updateMuteButton();
    });
}

if (muteBtn) {
    muteBtn.addEventListener('click', () => {
        if (audio.volume > 0) {
            lastNonZeroVolume = audio.volume;
            audio.volume = 0;
        } else {
            audio.volume = lastNonZeroVolume || 1;
        }

        if (volumeSlider) {
            volumeSlider.value = audio.volume;
        }
        localStorage.setItem('player_volume', audio.volume);
        updateMuteButton();
    });
}

// Next/Prev
function playNext() {
    if (!window.tracks.length) return;
    const idx = window.tracks.findIndex(t => t.id === currentTrackId);
    let nextIdx = idx + 1;
    if (nextIdx >= window.tracks.length) nextIdx = 0; // Loop

    if (isShuffle) {
        nextIdx = Math.floor(Math.random() * window.tracks.length);
    }

    playTrack(window.tracks[nextIdx].id);
}

function playPrev() {
    if (!window.tracks.length) return;
    const idx = window.tracks.findIndex(t => t.id === currentTrackId);
    let prevIdx = idx - 1;
    if (prevIdx < 0) prevIdx = window.tracks.length - 1;

    playTrack(window.tracks[prevIdx].id);
}

// Attach to global scope or buttons if needed
// The buttons in base.html don't have onclicks yet for prev/next
document.addEventListener('DOMContentLoaded', () => {
    // Attach handlers
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
    } catch(e) {
        console.error(e);
    }
};

function updateLikeBtn(isLiked) {
    if (isLiked) {
        likeBtn.classList.add('text-red-500', 'fill-current');
        likeBtn.classList.remove('text-gray-500');
    } else {
        likeBtn.classList.add('text-gray-500');
        likeBtn.classList.remove('text-red-500', 'fill-current');
    }
}

function updateMuteButton() {
    if (!muteBtn) return;

    const isMuted = audio.volume === 0;
    muteBtn.classList.toggle('is-muted', isMuted);
    muteBtn.title = isMuted ? 'Включить звук' : 'Выключить звук';
    muteBtn.setAttribute('aria-label', muteBtn.title);
    muteBtn.innerHTML = isMuted
        ? '<i data-lucide="volume-x"></i>'
        : '<i data-lucide="volume-2"></i>';
    lucide.createIcons();
}
