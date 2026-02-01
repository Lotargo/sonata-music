document.addEventListener('DOMContentLoaded', () => {
    // State
    let tracks = [];
    let currentTrack = null;
    let wavesurfer = null;

    // DOM Elements
    const libraryGrid = document.getElementById('library-grid');
    const emptyState = document.getElementById('empty-state');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadModal = document.getElementById('upload-modal');
    const closeUpload = document.getElementById('close-upload');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const filenameDisplay = document.getElementById('filename-display');
    const removeFile = document.getElementById('remove-file');
    const startUpload = document.getElementById('start-upload');
    const targetFormat = document.getElementById('target-format');
    const bitrateContainer = document.getElementById('bitrate-container');
    const playerBar = document.getElementById('player-bar');
    const playPauseBtn = document.getElementById('play-pause');
    const volumeSlider = document.getElementById('volume');
    const playerTitle = document.getElementById('player-title');
    const playerArtist = document.getElementById('player-artist');
    const playerCover = document.getElementById('player-cover');
    const currentTimeDisp = document.getElementById('current-time');
    const durationDisp = document.getElementById('duration');
    const statusBadge = document.getElementById('status-badge');
    const downloadBtn = document.getElementById('download-current');

    // Quality Presets
    const qualityPreset = document.getElementById('quality-preset');
    const ddimSteps = document.getElementById('ddim-steps');
    const guidanceScale = document.getElementById('guidance-scale');
    const guidanceValue = document.getElementById('guidance-value');

    // Initialize Wavesurfer
    wavesurfer = WaveSurfer.create({
        container: '#waveform',
        waveColor: '#475569',
        progressColor: '#6366f1',
        cursorColor: '#818cf8',
        barWidth: 2,
        barRadius: 3,
        responsive: true,
        height: 40,
        normalize: true,
        partialRender: true
    });

    // Icons initialization
    const refreshIcons = () => lucide.createIcons();

    // Quality Preset Logic
    if (qualityPreset) {
        qualityPreset.onchange = () => {
            const preset = qualityPreset.value;
            if (preset === 'fast') {
                ddimSteps.value = 25;
                guidanceScale.value = 3.5;
                ddimSteps.disabled = true;
                guidanceScale.disabled = true;
                ddimSteps.classList.add('opacity-50');
                guidanceScale.classList.add('opacity-50');
            } else if (preset === 'balanced') {
                ddimSteps.value = 50;
                guidanceScale.value = 3.5;
                ddimSteps.disabled = true;
                guidanceScale.disabled = true;
                ddimSteps.classList.add('opacity-50');
                guidanceScale.classList.add('opacity-50');
            } else if (preset === 'high') {
                ddimSteps.value = 100;
                guidanceScale.value = 3.5;
                ddimSteps.disabled = true;
                guidanceScale.disabled = true;
                ddimSteps.classList.add('opacity-50');
                guidanceScale.classList.add('opacity-50');
            } else if (preset === 'custom') {
                ddimSteps.disabled = false;
                guidanceScale.disabled = false;
                ddimSteps.classList.remove('opacity-50');
                guidanceScale.classList.remove('opacity-50');
            }
            guidanceValue.textContent = guidanceScale.value;
        };
    }

    if (guidanceScale) {
        guidanceScale.oninput = () => {
            guidanceValue.textContent = guidanceScale.value;
        };
    }

    // Library Functions
    async function fetchLibrary() {
        try {
            const response = await fetch('/library');
            tracks = await response.json();
            renderLibrary();
        } catch (error) {
            showToast('Failed to load library', 'error');
        }
    }

    function renderLibrary() {
        if (tracks.length === 0) {
            libraryGrid.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        libraryGrid.innerHTML = tracks.map(track => `
            <div class="track-card group bg-[#1e293b] rounded-xl overflow-hidden border border-white/5 hover:border-indigo-500/50 transition-all duration-300 shadow-lg" data-id="${track.id}">
                <div class="relative aspect-square overflow-hidden">
                    <img src="${track.cover_path || 'https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=400&h=400&fit=crop'}"
                         alt="${track.title}"
                         class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110">
                    <div class="play-overlay absolute inset-0 bg-black/40 opacity-0 flex items-center justify-center transition-opacity duration-300">
                        <button onclick="playTrack(${track.id})" class="bg-indigo-600 text-white w-12 h-12 rounded-full flex items-center justify-center shadow-xl transform translate-y-4 group-hover:translate-y-0 transition-transform duration-300">
                            <i data-lucide="play" class="fill-current ml-1"></i>
                        </button>
                    </div>
                    ${getStatusBadge(track.status)}
                </div>
                <div class="p-4">
                    <h4 class="font-bold truncate" title="${track.title}">${track.title}</h4>
                    <p class="text-xs text-slate-400 truncate mb-3">${track.artist}</p>
                    <div class="flex items-center justify-between">
                        <div class="flex gap-2">
                            ${track.status === 'pending' || track.status === 'failed' ?
                                `<button onclick="startProcessing(${track.id})" class="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded hover:bg-indigo-500 hover:text-white transition uppercase font-bold">Upscale</button>` : ''
                            }
                        </div>
                        <div class="flex gap-1">
                            <button onclick="editTrack(${track.id})" class="p-1.5 text-slate-500 hover:text-white transition"><i data-lucide="pencil" class="w-3.5 h-3.5"></i></button>
                            <button onclick="deleteTrack(${track.id})" class="p-1.5 text-slate-500 hover:text-red-500 transition"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
        refreshIcons();
    }

    function getStatusBadge(status) {
        const colors = {
            'pending': 'bg-amber-500/80',
            'processing': 'bg-blue-500/80 animate-pulse',
            'completed': 'bg-emerald-500/80',
            'failed': 'bg-red-500/80'
        };
        return `<span class="absolute top-2 right-2 ${colors[status] || 'bg-slate-500'} text-[10px] font-bold px-2 py-0.5 rounded text-white uppercase tracking-wider shadow-md">${status}</span>`;
    }

    // Format change handling
    targetFormat.onchange = () => {
        const format = targetFormat.value;
        if (format === 'wav' || format === 'flac') {
            bitrateContainer.classList.add('opacity-30', 'pointer-events-none');
        } else {
            bitrateContainer.classList.remove('opacity-30', 'pointer-events-none');
        }
    };

    // Upload Functions
    uploadBtn.onclick = () => uploadModal.classList.remove('hidden');
    closeUpload.onclick = () => {
        uploadModal.classList.add('hidden');
        resetUpload();
    };

    dropZone.onclick = () => fileInput.click();

    fileInput.onchange = (e) => {
        if (e.target.files.length > 0) handleFileSelect(e.target.files[0]);
    };

    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add('border-indigo-500', 'bg-indigo-500/5');
    };

    dropZone.ondragleave = () => {
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-500/5');
    };

    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-500/5');
        if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
    };

    function handleFileSelect(file) {
        filenameDisplay.textContent = file.name;
        fileInfo.classList.remove('hidden');
        dropZone.classList.add('hidden');
        startUpload.disabled = false;
        refreshIcons();
    }

    removeFile.onclick = (e) => {
        e.stopPropagation();
        resetUpload();
    };

    function resetUpload() {
        fileInput.value = '';
        fileInfo.classList.add('hidden');
        dropZone.classList.remove('hidden');
        startUpload.disabled = true;

        // Reset selectors to defaults
        document.getElementById('target-format').value = 'mp3';
        document.getElementById('target-sr').value = '48000';
        document.getElementById('target-bitrate').value = '320k';
        bitrateContainer.classList.remove('opacity-30', 'pointer-events-none');
    }

    startUpload.onclick = async () => {
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        startUpload.disabled = true;
        startUpload.innerHTML = '<i data-lucide="loader-2" class="animate-spin w-5 h-5 mx-auto"></i>';
        refreshIcons();

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const track = await response.json();

            if (response.ok) {
                showToast('Track uploaded successfully');
                // Auto start processing with selected options
                await startProcessing(track.id);
                uploadModal.classList.add('hidden');
                resetUpload();
                fetchLibrary();
            } else {
                showToast(track.error || 'Upload failed', 'error');
            }
        } catch (error) {
            showToast('Upload failed', 'error');
        } finally {
            startUpload.disabled = false;
            startUpload.textContent = 'Process & Add to Library';
            refreshIcons();
        }
    };

    // Processing
    window.startProcessing = async (id) => {
        const format = document.getElementById('target-format').value;
        const sr = document.getElementById('target-sr').value;
        const bitrate = document.getElementById('target-bitrate').value;

        // Fetch values from preset or inputs
        const steps = document.getElementById('ddim-steps').value;
        const guidance = document.getElementById('guidance-scale').value;

        try {
            const response = await fetch(`/process/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    format,
                    sample_rate: sr,
                    bitrate: bitrate,
                    steps: steps,
                    guidance: guidance
                })
            });

            if (response.ok) {
                showToast('Processing started');
                fetchLibrary();
                // Poll for status
                pollStatus(id);
            }
        } catch (error) {
            showToast('Failed to start processing', 'error');
        }
    };

    function pollStatus(id) {
        const interval = setInterval(async () => {
            const response = await fetch('/library');
            const latestTracks = await response.json();
            const track = latestTracks.find(t => t.id === id);

            if (track && track.status !== 'processing') {
                clearInterval(interval);
                fetchLibrary();
                showToast(`Track "${track.title}" ${track.status}`);
            }
        }, 3000);
    }

    // Player Functions
    window.playTrack = (id) => {
        const track = tracks.find(t => t.id === id);
        if (!track) return;

        currentTrack = track;
        playerBar.classList.remove('hidden');
        playerTitle.textContent = track.title;
        playerArtist.textContent = track.artist;
        playerCover.src = track.cover_path || 'https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=100&h=100&fit=crop';

        const url = track.status === 'completed'
            ? `/library_files/${track.processed_path.split('/').pop()}`
            : `/uploads/${track.filename}`;

        statusBadge.textContent = track.status === 'completed' ? 'Upscaled' : 'Original';
        statusBadge.className = track.status === 'completed'
            ? 'px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-400'
            : 'px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-400';

        downloadBtn.onclick = () => {
            const a = document.createElement('a');
            a.href = url;
            a.download = track.status === 'completed' ? `upscaled_${track.filename}` : track.filename;
            a.click();
        };

        wavesurfer.load(url);
        wavesurfer.on('ready', () => {
            wavesurfer.play();
            updatePlayPauseIcon(true);
            durationDisp.textContent = formatTime(wavesurfer.getDuration());
        });
    };

    playPauseBtn.onclick = () => {
        if (wavesurfer.isPlaying()) {
            wavesurfer.pause();
            updatePlayPauseIcon(false);
        } else {
            wavesurfer.play();
            updatePlayPauseIcon(true);
        }
    };

    function updatePlayPauseIcon(isPlaying) {
        playPauseBtn.innerHTML = isPlaying
            ? '<i data-lucide="pause" class="fill-current w-5 h-5"></i>'
            : '<i data-lucide="play" class="fill-current ml-1 w-5 h-5"></i>';
        refreshIcons();
    }

    wavesurfer.on('audioprocess', () => {
        currentTimeDisp.textContent = formatTime(wavesurfer.getCurrentTime());
    });

    volumeSlider.oninput = (e) => {
        wavesurfer.setVolume(e.target.value);
    };

    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // Actions
    window.deleteTrack = async (id) => {
        if (!confirm('Are you sure you want to delete this track?')) return;

        try {
            const response = await fetch(`/delete/${id}`, { method: 'DELETE' });
            if (response.ok) {
                showToast('Track deleted');
                fetchLibrary();
                if (currentTrack && currentTrack.id === id) {
                    playerBar.classList.add('hidden');
                    wavesurfer.stop();
                }
            }
        } catch (error) {
            showToast('Delete failed', 'error');
        }
    };

    window.editTrack = async (id) => {
        const track = tracks.find(t => t.id === id);
        const newTitle = prompt('Enter new title:', track.title);
        if (newTitle === null) return;
        const newArtist = prompt('Enter new artist:', track.artist);
        if (newArtist === null) return;

        try {
            const response = await fetch(`/edit/${id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle, artist: newArtist })
            });
            if (response.ok) {
                showToast('Track updated');
                fetchLibrary();
            }
        } catch (error) {
            showToast('Update failed', 'error');
        }
    };

    // Toast Helper
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-emerald-600' : 'bg-red-600';
        toast.className = `${bgColor} text-white px-6 py-3 rounded-xl shadow-2xl flex items-center gap-3 transform translate-y-20 opacity-0 transition-all duration-300`;
        toast.innerHTML = `
            <i data-lucide="${type === 'success' ? 'check-circle' : 'alert-circle'}" class="w-5 h-5"></i>
            <span class="font-medium">${message}</span>
        `;
        document.getElementById('toast-container').appendChild(toast);
        refreshIcons();

        setTimeout(() => {
            toast.classList.remove('translate-y-20', 'opacity-0');
        }, 100);

        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Initial Load
    fetchLibrary();
});
