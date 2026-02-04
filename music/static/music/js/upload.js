// Global state
let currentUploadTrackId = null;

// --- Modal Controls ---

function openUploadModal() {
    const modal = document.getElementById('upload-modal');
    modal.classList.remove('hidden');
    // Trigger reflow for transition
    setTimeout(() => {
        modal.querySelector('div').classList.remove('scale-95', 'opacity-0');
    }, 10);
}

function closeUploadModal() {
    const modal = document.getElementById('upload-modal');
    // Animate out (optional, skipping for simplicity)
    modal.classList.add('hidden');
    resetUpload();
}

// --- Drag & Drop ---

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

if (dropZone && fileInput) {
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
}

async function handleFileSelect(file) {
    // Show Loading state
    dropZone.innerHTML = '<div class="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full mx-auto"></div><p class="mt-4 font-bold">Uploading & Analyzing...</p>';
    dropZone.classList.add('pointer-events-none');

    const formData = new FormData();
    formData.append('audio_file', file);

    try {
        const response = await fetch('/upload/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrftoken
            }
        });

        if (response.ok) {
            const track = await response.json();
            currentUploadTrackId = track.id;
            showConfigUI(track);
        } else {
            // Robust error handling for non-JSON responses
            try {
                const err = await response.json();
                alert('Upload failed: ' + (err.error || 'Unknown error'));
            } catch (jsonErr) {
                console.error("Non-JSON error response:", await response.text());
                alert('Upload failed: Server error (check console)');
            }
            resetUploadUI();
        }
    } catch (e) {
        console.error(e);
        alert('Upload failed. Check console.');
        resetUploadUI();
    }
}

function showConfigUI(track) {
    document.getElementById('drop-zone').classList.add('hidden');
    document.getElementById('upload-config').classList.remove('hidden');
    document.getElementById('start-process-btn').disabled = false;

    // Fill Track Info
    document.getElementById('input-title').value = track.title || '';
    document.getElementById('input-artist').value = track.artist || 'Unknown Artist';

    const coverImg = document.getElementById('upload-cover-preview');
    const coverPlace = document.getElementById('upload-cover-placeholder');

    if (track.cover_url) {
        coverImg.src = track.cover_url;
        coverImg.classList.remove('hidden');
        coverPlace.classList.add('hidden');
    } else {
        coverImg.classList.add('hidden');
        coverPlace.classList.remove('hidden');
    }

    // Init Logic
    setUploadMode('ai'); // Default
    updateBitrateOptions();
}

function resetUpload() {
    // Reset Vars
    currentUploadTrackId = null;

    // Safely clear file input if it exists (it might be gone if loading spinner is shown)
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';

    // Reset UI (this re-creates the file input anyway)
    resetUploadUI();

    const titleInput = document.getElementById('input-title');
    if (titleInput) titleInput.value = '';

    const artistInput = document.getElementById('input-artist');
    if (artistInput) artistInput.value = '';
    document.getElementById('start-process-btn').disabled = true;
    document.getElementById('start-process-btn').innerHTML = 'Start Processing';
}

function resetUploadUI() {
    const dz = document.getElementById('drop-zone');
    dz.classList.remove('hidden', 'pointer-events-none');
    dz.innerHTML = `
        <div class="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition">
            <i data-lucide="music" class="w-8 h-8 text-indigo-500"></i>
        </div>
        <p class="text-xl font-bold mb-2">Drag & drop or click to select</p>
        <p class="text-slate-400 text-sm">MP3, WAV, FLAC, OGG (Max 50MB)</p>
        <input type="file" id="file-input" class="hidden" accept="audio/*">
    `;
    document.getElementById('upload-config').classList.add('hidden');
    lucide.createIcons();
}

// --- Mode Logic ---

function setUploadMode(mode) {
    document.getElementById('processing-mode').value = mode;

    // Update Buttons
    ['ai', 'hybrid', 'restoration', 'dsp'].forEach(m => {
        const btn = document.getElementById(`mode-${m}`);
        if (m === mode) {
            btn.classList.add('bg-indigo-600', 'text-white', 'shadow-sm');
            btn.classList.remove('text-slate-400');
        } else {
            btn.classList.remove('bg-indigo-600', 'text-white', 'shadow-sm');
            btn.classList.add('text-slate-400');
        }
    });

    // Update Sections
    const aiSettings = document.getElementById('ai-settings');
    const dspSettings = document.getElementById('dsp-settings');
    const modeDesc = document.getElementById('mode-desc');
    const dspLabel = document.getElementById('dsp-label');

    if (mode === 'ai') {
        aiSettings.classList.remove('hidden');
        dspSettings.classList.remove('hidden');
        dspLabel.textContent = "Pre-Processing DSP Preset (Optional)";
        modeDesc.innerHTML = `<span class="text-indigo-400 font-bold">Generative AI:</span> Uses AudioSR AI to hallucinate missing high frequencies. Includes DSP pre-processing. Best for low-quality sources.`;
    } else if (mode === 'hybrid') {
        aiSettings.classList.add('hidden');
        dspSettings.classList.remove('hidden');
        dspLabel.textContent = "Mastering DSP Preset";
        modeDesc.innerHTML = `<span class="text-indigo-400 font-bold">Hybrid Re-Mix:</span> Separates stems, polishes them individually (DSP), and remixes. Best for complex, distorted tracks.`;
    } else if (mode === 'restoration') {
        aiSettings.classList.add('hidden');
        dspSettings.classList.add('hidden');
        modeDesc.innerHTML = `<span class="text-indigo-400 font-bold">Restoration:</span> Fixed 'Suno Enhancer' pipeline. Demucs Re-synthesis -> Soft Bass & Air DSP Polish. No manual settings.`;
    } else {
        // DSP
        aiSettings.classList.add('hidden');
        dspSettings.classList.remove('hidden');
        dspLabel.textContent = "DSP Preset";
        modeDesc.innerHTML = `<span class="text-indigo-400 font-bold">Studio DSP:</span> Professional DSP chain (EQ, Comp, Limiter) without AI generation. Best for good sources.`;
    }
}

// --- Settings Logic ---

function updateQualityPreset() {
    const preset = document.getElementById('quality-preset').value;
    const steps = document.getElementById('ddim-steps');
    const guidance = document.getElementById('guidance-scale');

    if (preset === 'custom') {
        steps.disabled = false;
        guidance.disabled = false;
        steps.classList.remove('opacity-50');
        guidance.classList.remove('opacity-50');
    } else {
        steps.disabled = true;
        guidance.disabled = true;
        steps.classList.add('opacity-50');
        guidance.classList.add('opacity-50');

        if (preset === 'fast') steps.value = 25;
        else if (preset === 'balanced') steps.value = 50;
        else if (preset === 'high') steps.value = 100;

        guidance.value = 3.5;
        document.getElementById('guidance-value').innerText = "3.5";
    }
}

function updateDspPreset() {
    const preset = document.getElementById('dsp-preset').value;
    const presets = {
        "mastering": { stereo: 100, bass: 0, clarity: 0, comp: 50, rev: false },
        "deep_bass": { stereo: 100, bass: 6, clarity: 1.5, comp: 60, rev: false },
        "clear": { stereo: 110, bass: -2, clarity: 5, comp: 40, rev: false },
        "warm": { stereo: 90, bass: 2, clarity: -1, comp: 60, rev: true, revSize: 30, revMix: 10 },
        "punchy": { stereo: 100, bass: 4, clarity: 2, comp: 80, rev: false }
    };

    const config = presets[preset];
    if (config) {
        setVal('stereo-width', config.stereo);
        setVal('bass-boost', config.bass);
        setVal('voice-clarity', config.clarity);
        setVal('compressor-amount', config.comp);

        const revCheck = document.getElementById('reverb-enabled');
        revCheck.checked = config.rev;
        toggleReverbControls(); // update UI

        if (config.rev) {
            setVal('reverb-size', config.revSize || 50);
            setVal('reverb-amount', config.revMix || 30);
        }
    }
}

function setVal(id, val) {
    const el = document.getElementById(id);
    if(el) {
        el.value = val;
        // Trigger oninput if needed to update labels
        const label = document.getElementById(id.replace('reverb-amount', 'reverb-mix').replace('stereo-width', 'val-stereo').replace('bass-boost', 'val-bass').replace('voice-clarity', 'val-clarity').replace('compressor-amount', 'val-comp').replace('reverb-size', 'val-rev-size').replace('reverb-amount', 'val-rev-mix'));
        // Mapping is messy, let's just do manual label update
        // Or rely on the slider listeners I'll add below
        el.dispatchEvent(new Event('input'));
    }
}

// Sliders Label Update
const sliderMap = {
    'stereo-width': { id: 'val-stereo', unit: '%' },
    'bass-boost': { id: 'val-bass', unit: 'dB' },
    'voice-clarity': { id: 'val-clarity', unit: '' },
    'compressor-amount': { id: 'val-comp', unit: '%' },
    'reverb-size': { id: 'val-rev-size', unit: '%' },
    'reverb-amount': { id: 'val-rev-mix', unit: '%' }
};

Object.keys(sliderMap).forEach(key => {
    const el = document.getElementById(key);
    if (el) {
        el.oninput = () => {
            const map = sliderMap[key];
            document.getElementById(map.id).innerText = el.value + map.unit;
        };
    }
});

function toggleDspAdvanced() {
    const el = document.getElementById('dsp-advanced');
    el.classList.toggle('hidden');
}

const revEnabled = document.getElementById('reverb-enabled');
if(revEnabled) {
    revEnabled.onchange = toggleReverbControls;
}

function toggleReverbControls() {
    const ctrls = document.getElementById('reverb-controls');
    if (document.getElementById('reverb-enabled').checked) {
        ctrls.classList.remove('opacity-50', 'pointer-events-none');
    } else {
        ctrls.classList.add('opacity-50', 'pointer-events-none');
    }
}

function updateBitrateOptions() {
    const format = document.getElementById('target-format').value;
    const select = document.getElementById('target-bitrate');
    const label = document.getElementById('bitrate-label');

    select.innerHTML = '';

    if (format === 'mp3' || format === 'ogg') {
        label.innerText = 'Bitrate';
        const opts = [
            {v: '128k', t: '128 kbps'},
            {v: '192k', t: '192 kbps'},
            {v: '320k', t: '320 kbps (High)'}
        ];
        opts.forEach(o => {
            const opt = document.createElement('option');
            opt.value = o.v; opt.text = o.t;
            if(o.v === '320k') opt.selected = true;
            select.appendChild(opt);
        });
    } else {
        label.innerText = 'Bit Depth';
        const opts = [
            {v: '16-bit', t: '16-bit (CD)'},
            {v: '24-bit', t: '24-bit (Studio)'},
            {v: '32-bit', t: '32-bit Float'}
        ];
        opts.forEach(o => {
            const opt = document.createElement('option');
            opt.value = o.v; opt.text = o.t;
            if(o.v === '24-bit') opt.selected = true;
            select.appendChild(opt);
        });
    }
}

// --- Submit ---

async function startProcessing() {
    if (!currentUploadTrackId) return;

    const btn = document.getElementById('start-process-btn');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" class="animate-spin w-5 h-5"></i> Processing...';
    lucide.createIcons();

    // Collect Data
    const payload = {
        title: document.getElementById('input-title').value,
        artist: document.getElementById('input-artist').value,
        mode: document.getElementById('processing-mode').value,
        format: document.getElementById('target-format').value,
        sample_rate: document.getElementById('target-sr').value,
        bitrate: document.getElementById('target-bitrate').value,

        // AI
        steps: document.getElementById('ddim-steps').value,
        guidance: document.getElementById('guidance-scale').value,

        // DSP
        dsp_preset: document.getElementById('dsp-preset').value,
        stereo_width: document.getElementById('stereo-width').value,
        bass_boost: document.getElementById('bass-boost').value,
        voice_clarity: document.getElementById('voice-clarity').value,
        compressor_amount: document.getElementById('compressor-amount').value,
        reverb_enabled: document.getElementById('reverb-enabled').checked,
        reverb_size: document.getElementById('reverb-size').value,
        reverb_amount: document.getElementById('reverb-amount').value
    };

    try {
        const response = await fetch(`/process/${currentUploadTrackId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            closeUploadModal();
            // Refresh library or notify user
            // Assuming there is a function to refresh library in parent
            if (typeof fetchLibrary === 'function') fetchLibrary();
            else window.location.reload();
        } else {
            // Robust error handling for non-JSON responses
            try {
                const err = await response.json();
                alert('Error: ' + err.error);
            } catch (jsonErr) {
                console.error("Non-JSON error response:", await response.text());
                alert('Server Error: ' + response.statusText);
            }
            btn.disabled = false;
            btn.innerHTML = 'Start Processing';
        }
    } catch (e) {
        console.error(e);
        alert('Network Error: ' + e.message);
        btn.disabled = false;
        btn.innerHTML = 'Start Processing';
    }
}
