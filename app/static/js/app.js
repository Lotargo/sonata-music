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

    // Mode Selector
    const modeAiBtn = document.getElementById('mode-ai');
    const modeDspBtn = document.getElementById('mode-dsp');
    const modeHybridBtn = document.getElementById('mode-hybrid');
    const modeRestorationBtn = document.getElementById('mode-restoration');
    const processingModeInput = document.getElementById('processing-mode');
    const modeDesc = document.getElementById('mode-desc');
    const aiSettings = document.getElementById('ai-settings');
    const dspSettings = document.getElementById('dsp-settings');
    const dspPreset = document.getElementById('dsp-preset');
    const dspLabel = document.getElementById('dsp-label');

    // Details Modal
    const detailsModal = document.getElementById('details-modal');
    const closeDetails = document.getElementById('close-details');
    const metricsBody = document.getElementById('metrics-body');
    const waveOrigContainer = document.getElementById('wave-orig');
    const waveProcContainer = document.getElementById('wave-proc');
    const btnListenOrig = document.getElementById('btn-listen-orig');
    const btnListenProc = document.getElementById('btn-listen-proc');
    const comparePlayBtn = document.getElementById('compare-play');
    const viewSplitBtn = document.getElementById('view-split');
    const viewOverlayBtn = document.getElementById('view-overlay');
    const waveOrigWrapper = document.getElementById('wave-orig-wrapper');
    const waveProcWrapper = document.getElementById('wave-proc-wrapper');

    let wsOrig = null;
    let wsProc = null;
    let detailsTrackId = null;
    let activeCompareAudio = 'proc'; // 'orig' or 'proc'

    // DSP Advanced Controls
    const toggleDspAdvanced = document.getElementById('toggle-dsp-advanced');
    const dspAdvanced = document.getElementById('dsp-advanced');
    const stereoWidth = document.getElementById('stereo-width');
    const bassBoost = document.getElementById('bass-boost');
    const voiceClarity = document.getElementById('voice-clarity');
    const compressorAmount = document.getElementById('compressor-amount');
    const reverbEnabled = document.getElementById('reverb-enabled');
    const reverbSize = document.getElementById('reverb-size');
    const reverbAmount = document.getElementById('reverb-amount');
    const reverbControls = document.getElementById('reverb-controls');

    // Value Labels
    const valStereo = document.getElementById('val-stereo');
    const valBass = document.getElementById('val-bass');
    const valClarity = document.getElementById('val-clarity');
    const valComp = document.getElementById('val-comp');
    const valRevSize = document.getElementById('val-rev-size');
    const valRevMix = document.getElementById('val-rev-mix');

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

    // DSP Advanced Logic
    if (toggleDspAdvanced) {
        toggleDspAdvanced.onclick = () => {
            dspAdvanced.classList.toggle('hidden');
            const icon = toggleDspAdvanced.querySelector('svg');
            // Assuming icon rotation or change, but for now just toggle visibility
        };
    }

    if (reverbEnabled) {
        reverbEnabled.onchange = () => {
            if (reverbEnabled.checked) {
                reverbControls.classList.remove('opacity-50', 'pointer-events-none');
            } else {
                reverbControls.classList.add('opacity-50', 'pointer-events-none');
            }
        };
    }

    // Slider updates
    const updateLabel = (slider, label, unit = '') => {
        if (!slider || !label) return;
        slider.oninput = () => {
            label.textContent = slider.value + unit;
        };
    };

    updateLabel(stereoWidth, valStereo, '%');
    updateLabel(bassBoost, valBass, 'dB');
    updateLabel(voiceClarity, valClarity);
    updateLabel(compressorAmount, valComp, '%');
    updateLabel(reverbSize, valRevSize, '%');
    updateLabel(reverbAmount, valRevMix, '%');

    // Preset Logic
    const dspPresets = {
        "mastering": { stereo: 100, bass: 0, clarity: 0, comp: 50, rev: false },
        "clear": { stereo: 110, bass: -2, clarity: 5, comp: 40, rev: false },
        "warm": { stereo: 90, bass: 2, clarity: -1, comp: 60, rev: true, revSize: 30, revMix: 10 },
        "punchy": { stereo: 100, bass: 4, clarity: 2, comp: 80, rev: false }
    };

    if (dspPreset) {
        dspPreset.onchange = () => {
            const config = dspPresets[dspPreset.value];
            if (config) {
                stereoWidth.value = config.stereo; valStereo.textContent = config.stereo + '%';
                bassBoost.value = config.bass; valBass.textContent = config.bass + 'dB';
                voiceClarity.value = config.clarity; valClarity.textContent = config.clarity;
                compressorAmount.value = config.comp; valComp.textContent = config.comp + '%';
                reverbEnabled.checked = config.rev;
                reverbEnabled.onchange(); // trigger UI update

                if (config.rev) {
                     reverbSize.value = config.revSize || 50; valRevSize.textContent = reverbSize.value + '%';
                     reverbAmount.value = config.revMix || 30; valRevMix.textContent = reverbAmount.value + '%';
                }
            }
        };
    }

    // Mode Switching Logic
    if (modeAiBtn && modeDspBtn && modeHybridBtn) {
        modeAiBtn.onclick = () => setMode('ai');
        modeDspBtn.onclick = () => setMode('dsp');
        modeHybridBtn.onclick = () => setMode('hybrid');
        if (modeRestorationBtn) modeRestorationBtn.onclick = () => setMode('restoration');
    }

    function setMode(mode) {
        processingModeInput.value = mode;

        // Reset all buttons
        const buttons = [modeAiBtn, modeDspBtn, modeHybridBtn, modeRestorationBtn];
        buttons.forEach(btn => {
            if (btn) {
                btn.classList.remove('bg-indigo-600', 'text-white', 'font-bold', 'shadow-sm');
                btn.classList.add('text-slate-400', 'font-medium', 'hover:text-white');
            }
        });

        // Activate selected
        let activeBtn;
        if (mode === 'ai') activeBtn = modeAiBtn;
        else if (mode === 'dsp') activeBtn = modeDspBtn;
        else if (mode === 'hybrid') activeBtn = modeHybridBtn;
        else if (mode === 'restoration') activeBtn = modeRestorationBtn;

        if (activeBtn) {
            activeBtn.classList.add('bg-indigo-600', 'text-white', 'font-bold', 'shadow-sm');
            activeBtn.classList.remove('text-slate-400', 'font-medium', 'hover:text-white');
        }

        if (mode === 'ai') {
            aiSettings.classList.remove('hidden');
            dspSettings.classList.remove('hidden'); // Enable DSP for AI Pre-processing
            if(dspLabel) dspLabel.textContent = "Pre-Processing DSP Preset (Optional)";
            modeDesc.textContent = "Generative AI with DSP Pre-processing. Cleans audio first, then uses AI to hallucinate missing high frequencies (Mid-Side mode). Best for low-quality sources.";
        } else if (mode === 'hybrid') {
             aiSettings.classList.add('hidden');
             dspSettings.classList.remove('hidden'); // Hybrid uses DSP settings
             if(dspLabel) dspLabel.textContent = "Mastering DSP Preset";
             modeDesc.textContent = "Separates stems, polishes them individually (DSP), and remixes with dynamic envelope matching. Best for complex, distorted tracks.";
        } else if (mode === 'restoration') {
             aiSettings.classList.add('hidden');
             dspSettings.classList.add('hidden'); // Fixed chain
             modeDesc.textContent = "Fixed 'Suno Enhancer' pipeline: Demucs Re-synthesis (De-artifact) -> Soft Bass & Air DSP Polish. No manual settings.";
        } else {
            dspSettings.classList.remove('hidden');
            aiSettings.classList.add('hidden');
            if(dspLabel) dspLabel.textContent = "DSP Preset";
            modeDesc.textContent = "Uses professional DSP chain (Soft Bass, Exciter, Compression, Limiter) to polish audio without AI generation. Best for good sources.";
        }
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
                                `<button onclick="startProcessing(${track.id})" class="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded hover:bg-indigo-500 hover:text-white transition uppercase font-bold">Upscale</button>` :
                                `<button onclick="openDetails(${track.id})" class="text-[10px] bg-slate-700 text-slate-300 px-2 py-1 rounded hover:bg-slate-600 hover:text-white transition uppercase font-bold flex items-center gap-1"><i data-lucide="bar-chart-2" class="w-3 h-3"></i> Details</button>`
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
    const updateBitrateOptions = () => {
        const format = targetFormat.value;
        const bitrateSelect = document.getElementById('target-bitrate');
        const bitrateLabel = document.getElementById('bitrate-label');

        bitrateSelect.innerHTML = '';
        bitrateContainer.classList.remove('opacity-30', 'pointer-events-none'); // Always enable now

        if (format === 'mp3' || format === 'ogg') {
            bitrateLabel.textContent = 'Bitrate';
            const options = [
                { val: '128k', txt: '128 kbps' },
                { val: '192k', txt: '192 kbps' },
                { val: '256k', txt: '256 kbps' },
                { val: '320k', txt: '320 kbps (Max)' }
            ];
            if (format === 'ogg') {
                 options.push({ val: '500k', txt: '500 kbps (High)' });
            }

            options.forEach(opt => {
                const el = document.createElement('option');
                el.value = opt.val;
                el.textContent = opt.txt;
                if (opt.val === '320k') el.selected = true;
                bitrateSelect.appendChild(el);
            });
        } else {
            // WAV / FLAC
            bitrateLabel.textContent = 'Bit Depth';
            const options = [
                { val: '16-bit', txt: '16-bit (CD Quality)' },
                { val: '24-bit', txt: '24-bit (Studio Quality)' },
                { val: '32-bit', txt: '32-bit Float' }
            ];

            options.forEach(opt => {
                const el = document.createElement('option');
                el.value = opt.val;
                el.textContent = opt.txt;
                if (opt.val === '24-bit') el.selected = true;
                bitrateSelect.appendChild(el);
            });
        }
    };

    targetFormat.onchange = updateBitrateOptions;

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
        updateBitrateOptions(); // Reset bitrate options
    }

    // Init
    updateBitrateOptions();

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
        const mode = document.getElementById('processing-mode').value;
        const dspPresetVal = document.getElementById('dsp-preset').value;

        // DSP Params
        const dspParams = {
            stereo_width: parseInt(stereoWidth.value) / 100, // 0-2 scale
            bass_boost: parseFloat(bassBoost.value),
            voice_clarity: parseFloat(voiceClarity.value),
            compressor_amount: parseInt(compressorAmount.value) / 100, // 0-1 scale
            reverb_enabled: reverbEnabled.checked,
            reverb_size: parseInt(reverbSize.value) / 100,
            reverb_amount: parseInt(reverbAmount.value) / 100
        };

        try {
            const payload = {
                format,
                sample_rate: sr,
                bitrate: bitrate,
                steps: steps,
                guidance: guidance,
                mode: mode,
                dsp_preset: dspPresetVal
            };

            if (mode === 'dsp' || mode === 'hybrid') {
                // Merge params into payload
                Object.assign(payload, dspParams);
            }

            const response = await fetch(`/process/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
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

    // Details Modal Logic
    if (closeDetails) {
        closeDetails.onclick = () => {
            detailsModal.classList.add('hidden');
            if (wsOrig) wsOrig.destroy();
            if (wsProc) wsProc.destroy();
            wsOrig = null;
            wsProc = null;
        };
    }

    window.openDetails = async (id) => {
        const track = tracks.find(t => t.id === id);
        if (!track || track.status !== 'completed') return;
        detailsTrackId = track.id;

        // Reset UI
        detailsModal.classList.remove('hidden');
        document.getElementById('details-title').textContent = track.title;
        metricsBody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-slate-500">Loading metrics...</td></tr>';

        // Fetch Metrics
        try {
            const res = await fetch(`/metrics/${id}`);
            if (res.ok) {
                const data = await res.json();
                renderMetricsTable(data);

                // Initialize Waveforms
                initComparisonWaveforms(track, data);
            } else {
                metricsBody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-red-400">Metrics not available.</td></tr>';
            }
        } catch (e) {
            metricsBody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-red-400">Error loading metrics.</td></tr>';
        }
    };

    function renderMetricsTable(data) {
        const orig = data.original;
        const proc = data.processed;

        document.getElementById('info-sr-orig').textContent = orig.sr + ' Hz';
        document.getElementById('info-sr-proc').textContent = proc.sr + ' Hz';

        const metrics = [
            { label: 'Peak (dB)', key: 'peak_db', diff: true },
            { label: 'RMS (dB)', key: 'rms_db', diff: true },
            { label: 'Dynamic Range (dB)', key: 'dynamic_range_db', diff: true }
        ];

        metricsBody.innerHTML = metrics.map(m => {
            const v1 = orig[m.key];
            const v2 = proc[m.key];
            const diff = (v2 - v1).toFixed(2);
            const diffColor = diff > 0 ? 'text-green-400' : (diff < 0 ? 'text-red-400' : 'text-slate-500');
            const diffSign = diff > 0 ? '+' : '';

            return `
                <tr class="hover:bg-white/5 transition">
                    <td class="px-4 py-3 font-medium text-slate-300">${m.label}</td>
                    <td class="px-4 py-3 font-mono text-slate-400">${v1}</td>
                    <td class="px-4 py-3 font-mono text-white font-bold flex items-center gap-2">
                        ${v2}
                        <span class="text-xs ${diffColor} font-normal">(${diffSign}${diff})</span>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function initComparisonWaveforms(track, data) {
        if (wsOrig) wsOrig.destroy();
        if (wsProc) wsProc.destroy();

        const commonOptions = {
            height: 192, // Matches h-48
            barWidth: 2,
            barRadius: 2,
            cursorWidth: 1,
            responsive: true,
            normalize: true,
            partialRender: true,
            interact: true
        };

        wsOrig = WaveSurfer.create({
            ...commonOptions,
            container: '#wave-orig',
            waveColor: 'rgba(59, 130, 246, 0.5)', // Blue
            progressColor: 'rgba(96, 165, 250, 0.5)',
            cursorColor: '#60a5fa',
        });

        wsProc = WaveSurfer.create({
            ...commonOptions,
            container: '#wave-proc',
            waveColor: 'rgba(34, 197, 94, 0.5)', // Green
            progressColor: 'rgba(74, 222, 128, 0.5)',
            cursorColor: '#4ade80',
        });

        // Load Audio
        // Original needs URL: /uploads/filename
        const origUrl = `/uploads/${track.filename}`;
        const procUrl = `/library_files/${track.processed_path}`; // processed_path in JSON is basename

        wsOrig.load(origUrl);
        wsProc.load(procUrl);

        // Sync Logic
        let isSeeking = false;

        wsOrig.on('seek', (p) => {
            if(!isSeeking) { isSeeking=true; wsProc.seekTo(p); isSeeking=false; }
        });
        wsProc.on('seek', (p) => {
            if(!isSeeking) { isSeeking=true; wsOrig.seekTo(p); isSeeking=false; }
        });

        wsOrig.on('play', () => wsProc.play());
        wsOrig.on('pause', () => wsProc.pause());
        wsProc.on('play', () => wsOrig.play());
        wsProc.on('pause', () => wsOrig.pause());

        // Play Button
        comparePlayBtn.onclick = () => {
            if(wsProc.isPlaying()) wsProc.pause();
            else wsProc.play();
            updateComparePlayIcon();
        };

        wsProc.on('play', updateComparePlayIcon);
        wsProc.on('pause', updateComparePlayIcon);

        // Default: Listen Processed
        setCompareAudio('proc');
    }

    function updateComparePlayIcon() {
        const isPlaying = wsProc && wsProc.isPlaying();
        comparePlayBtn.innerHTML = isPlaying
            ? '<i data-lucide="pause" class="fill-current w-5 h-5"></i>'
            : '<i data-lucide="play" class="fill-current w-5 h-5 ml-1"></i>';
        refreshIcons();
    }

    function setCompareAudio(source) {
        activeCompareAudio = source;
        if(source === 'orig') {
            wsOrig.setMute(false);
            wsProc.setMute(true);
            btnListenOrig.classList.remove('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
            btnListenOrig.classList.add('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/20');

            btnListenProc.classList.add('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
            btnListenProc.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
        } else {
            wsOrig.setMute(true);
            wsProc.setMute(false);
            btnListenProc.classList.remove('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
            btnListenProc.classList.add('bg-indigo-600', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');

            btnListenOrig.classList.add('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
            btnListenOrig.classList.remove('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/20');
        }
    }

    btnListenOrig.onclick = () => setCompareAudio('orig');
    btnListenProc.onclick = () => setCompareAudio('proc');

    // Visual Mode Toggle
    viewSplitBtn.onclick = () => setVisualMode('split');
    viewOverlayBtn.onclick = () => setVisualMode('overlay');

    function setVisualMode(mode) {
        if (mode === 'overlay') {
            viewOverlayBtn.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
            viewOverlayBtn.classList.remove('text-slate-400');
            viewSplitBtn.classList.remove('bg-slate-700', 'text-white', 'shadow', 'font-medium');
            viewSplitBtn.classList.add('text-slate-400');

            // Apply overlay CSS
            // Containers are absolute by default in our HTML structure,
            // but for split we might need to adjust height/position logic.
            // Wait, HTML structure:
            // #compare-container (h-48, relative)
            //   #wave-orig-wrapper (absolute, full)
            //   #wave-proc-wrapper (absolute, full)

            // In Overlay mode: Both visible, full height, overlapping.
            waveOrigWrapper.style.top = '0';
            waveOrigWrapper.style.height = '100%';
            waveProcWrapper.style.top = '0';
            waveProcWrapper.style.height = '100%';
            waveProcWrapper.style.opacity = '0.7'; // Blend

        } else {
            // Split mode
            viewSplitBtn.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
            viewSplitBtn.classList.remove('text-slate-400');
            viewOverlayBtn.classList.remove('bg-slate-700', 'text-white', 'shadow', 'font-medium');
            viewOverlayBtn.classList.add('text-slate-400');

            // Top half / Bottom half
            waveOrigWrapper.style.top = '0';
            waveOrigWrapper.style.height = '50%';
            waveProcWrapper.style.top = '50%';
            waveProcWrapper.style.height = '50%';
            waveProcWrapper.style.opacity = '1';
        }

        // Redraw wavesurfer to fit new container dimensions
        setTimeout(() => {
            if(wsOrig) wsOrig.drawBuffer();
            if(wsProc) wsProc.drawBuffer();
        }, 300);
    }

    // Default visual mode
    setVisualMode('split');

    // Initial Load
    fetchLibrary();
});
