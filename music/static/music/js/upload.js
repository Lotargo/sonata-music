// Global state
let currentUploadTrackId = null;
let currentUploadFlow = 'library';

// --- Modal Controls ---

function openUploadModal(flow = 'library') {
    currentUploadFlow = flow;
    const modal = document.getElementById('upload-modal');
    modal.classList.remove('hidden');
    setUploadMode(flow === 'library' ? 'dsp' : 'restoration');
    configureUploadFlow();
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

function configureUploadFlow() {
    const title = document.getElementById('upload-modal-title');
    const libraryOptions = document.getElementById('library-upload-options');
    const processingModeSection = document.getElementById('processing-mode-section');
    const aiSettings = document.getElementById('ai-settings');
    const dspSettings = document.getElementById('dsp-settings');
    const formatSettings = document.getElementById('format-settings');
    const startBtn = document.getElementById('start-process-btn');

    const isLibraryFlow = currentUploadFlow === 'library';
    const enhanceQuality = !isLibraryFlow || document.getElementById('library-enhance-quality')?.checked;
    const selectedMode = document.getElementById('processing-mode')?.value || (isLibraryFlow ? 'dsp' : 'restoration');

    if (title) {
        title.innerHTML = isLibraryFlow
            ? '<i data-lucide="upload-cloud" class="text-[var(--yellow)]"></i> Добавить в библиотеку'
            : '<i data-lucide="wand-sparkles" class="text-[var(--yellow)]"></i> Реставрация аудио';
    }

    libraryOptions?.classList.toggle('hidden', !isLibraryFlow);
    processingModeSection?.classList.toggle('hidden', !enhanceQuality);
    formatSettings?.classList.toggle('hidden', !enhanceQuality);

    if (enhanceQuality) {
        aiSettings?.classList.toggle('hidden', selectedMode !== 'ai');
        dspSettings?.classList.toggle('hidden', selectedMode === 'restoration');
    } else {
        aiSettings?.classList.add('hidden');
        dspSettings?.classList.add('hidden');
    }

    if (startBtn) {
        startBtn.innerHTML = isLibraryFlow && !enhanceQuality ? 'Добавить в библиотеку' : 'Запустить обработку';
    }

    lucide.createIcons();
}

function updateLibraryEnhanceUI() {
    if (currentUploadFlow === 'library' && document.getElementById('library-enhance-quality')?.checked) {
        setUploadMode('dsp');
    }
    configureUploadFlow();
}

// --- Drag & Drop ---

function bindDropZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    if (!dropZone || !fileInput) return;

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

bindDropZone();

async function handleFileSelect(file) {
    const dropZone = document.getElementById('drop-zone');
    if (!dropZone) return;

    // Show Loading state
    dropZone.innerHTML = '<div class="animate-spin w-8 h-8 border-4 border-yellow-400 border-t-transparent rounded-full mx-auto"></div><p class="mt-4 font-bold">Загружаю и анализирую...</p>';
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
                alert('Загрузка не удалась: ' + (err.error || 'неизвестная ошибка'));
            } catch (jsonErr) {
                console.error("Non-JSON error response:", await response.text());
                alert('Загрузка не удалась: ошибка сервера');
            }
            resetUploadUI();
        }
    } catch (e) {
        console.error(e);
        alert('Загрузка не удалась.');
        resetUploadUI();
    }
}

function showConfigUI(track) {
    document.getElementById('drop-zone').classList.add('hidden');
    document.getElementById('upload-config').classList.remove('hidden');
    document.getElementById('start-process-btn').disabled = false;

    // Fill Track Info
    document.getElementById('input-title').value = track.title || '';
    document.getElementById('input-artist').value = track.artist || 'Неизвестный исполнитель';

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

    // Render Acoustic Badges (BPM, Key, Centroid, Duration)
    const badgesContainer = document.getElementById('acoustic-badges');
    const badgeBpm = document.getElementById('badge-bpm');
    const badgeKey = document.getElementById('badge-key');
    const badgeCentroid = document.getElementById('badge-centroid');
    const badgeDuration = document.getElementById('badge-duration');

    if (badgesContainer) {
        let hasAnyBadge = false;
        if (track.bpm && badgeBpm) {
            badgeBpm.textContent = `${track.bpm} BPM`;
            badgeBpm.parentElement.classList.remove('hidden');
            hasAnyBadge = true;
        } else if (badgeBpm) {
            badgeBpm.parentElement.classList.add('hidden');
        }

        if (track.musical_key && badgeKey) {
            badgeKey.textContent = track.musical_key;
            badgeKey.parentElement.classList.remove('hidden');
            hasAnyBadge = true;
        } else if (badgeKey) {
            badgeKey.parentElement.classList.add('hidden');
        }

        if (track.spectral_centroid && badgeCentroid) {
            badgeCentroid.textContent = `${Math.round(track.spectral_centroid)} Hz`;
            badgeCentroid.parentElement.classList.remove('hidden');
            hasAnyBadge = true;
        } else if (badgeCentroid) {
            badgeCentroid.parentElement.classList.add('hidden');
        }

        if (track.duration && badgeDuration) {
            const mins = Math.floor(track.duration / 60);
            const secs = Math.floor(track.duration % 60).toString().padStart(2, '0');
            badgeDuration.textContent = `${mins}:${secs}`;
            badgeDuration.parentElement.classList.remove('hidden');
            hasAnyBadge = true;
        } else if (badgeDuration) {
            badgeDuration.parentElement.classList.add('hidden');
        }

        badgesContainer.classList.toggle('hidden', !hasAnyBadge);
    }

    // Init Logic
    if (currentUploadFlow === 'library') {
        if (document.getElementById('library-enhance-quality')?.checked) {
            setUploadMode('dsp');
        }
        configureUploadFlow();
    } else {
        setUploadMode('restoration');
        updateBitrateOptions();
    }

    setTimeout(() => {
        initProQCanvas();
    }, 60);
}

function resetUpload() {
    // Reset Vars
    currentUploadTrackId = null;

    // Safely clear file input if it exists (it might be gone if loading spinner is shown)
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';

    // Reset UI (this re-creates the file input anyway)
    resetUploadUI();
    configureUploadFlow();

    const titleInput = document.getElementById('input-title');
    if (titleInput) titleInput.value = '';

    const artistInput = document.getElementById('input-artist');
    if (artistInput) artistInput.value = '';
    const enhanceInput = document.getElementById('library-enhance-quality');
    if (enhanceInput) enhanceInput.checked = false;
    setUploadMode(currentUploadFlow === 'library' ? 'dsp' : 'restoration');
    document.getElementById('start-process-btn').disabled = true;
    document.getElementById('start-process-btn').innerHTML = currentUploadFlow === 'library' ? 'Добавить в библиотеку' : 'Запустить обработку';
}

function resetUploadUI() {
    const dz = document.getElementById('drop-zone');
    dz.classList.remove('hidden', 'pointer-events-none');
    dz.innerHTML = `
        <div class="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition">
            <i data-lucide="music" class="w-8 h-8 text-yellow-400"></i>
        </div>
        <p class="text-xl font-bold mb-2">Перетащите файл или выберите вручную</p>
        <p class="text-slate-400 text-sm">MP3, WAV, FLAC, OGG, M4A, Opus до 50MB</p>
        <input type="file" id="file-input" class="hidden" accept="audio/*">
    `;
    document.getElementById('upload-config').classList.add('hidden');
    document.getElementById('acoustic-badges')?.classList.add('hidden');
    lucide.createIcons();
    bindDropZone();
    configureUploadFlow();
}

// --- Mode Logic ---

function setUploadMode(mode) {
    document.getElementById('processing-mode').value = mode;

    // Update Buttons
    ['direct', 'stealth', 'ai', 'hybrid', 'restoration', 'dsp'].forEach(m => {
        const btn = document.getElementById(`mode-${m}`);
        if (!btn) return;
        if (m === mode) {
            btn.classList.add('bg-indigo-600', 'text-white', 'shadow-sm', 'font-bold');
            btn.classList.remove('text-slate-400', 'font-medium');
        } else {
            btn.classList.remove('bg-indigo-600', 'text-white', 'shadow-sm', 'font-bold');
            btn.classList.add('text-slate-400', 'font-medium');
        }
    });

    // Update Sections
    const aiSettings = document.getElementById('ai-settings');
    const dspSettings = document.getElementById('dsp-settings');
    const modeDesc = document.getElementById('mode-desc');
    const dspLabel = document.getElementById('dsp-label');

    if (mode === 'direct') {
        aiSettings.classList.add('hidden');
        dspSettings.classList.add('hidden');
        modeDesc.innerHTML = `<span class="text-yellow-400 font-bold">Конвертация:</span> прямое быстрое перекодирование без изменения звука нейросетями или DSP.`;
    } else if (mode === 'stealth') {
        aiSettings.classList.add('hidden');
        dspSettings.classList.add('hidden');
        modeDesc.innerHTML = `<span class="text-yellow-400 font-bold">Anti-AI Stealth:</span> разрушение водяных знаков, устранение коробочности (350 Гц), мягкий де-харш, стерео-мастеринг и очистка метаданных.`;
    } else if (mode === 'ai') {
        aiSettings.classList.remove('hidden');
        dspSettings.classList.remove('hidden');
        dspLabel.textContent = "DSP-подготовка";
        modeDesc.innerHTML = `<span class="text-yellow-400 font-bold">AI-апскейл:</span> восстанавливает верхние частоты и мягко подготавливает трек DSP-цепочкой.`;
    } else if (mode === 'hybrid') {
        aiSettings.classList.add('hidden');
        dspSettings.classList.remove('hidden');
        dspLabel.textContent = "Mastering DSP";
        modeDesc.innerHTML = `<span class="text-yellow-400 font-bold">Hybrid:</span> разделяет трек на stems, полирует их отдельно и собирает обратно.`;
    } else if (mode === 'restoration') {
        aiSettings.classList.add('hidden');
        dspSettings.classList.add('hidden');
        modeDesc.innerHTML = `<span class="text-yellow-400 font-bold">Реставрация:</span> фиксированная цепочка восстановления без ручных настроек.`;
    } else {
        // DSP
        aiSettings.classList.add('hidden');
        dspSettings.classList.remove('hidden');
        dspLabel.textContent = "DSP-пресет";
        modeDesc.innerHTML = `<span class="text-yellow-400 font-bold">Studio DSP:</span> эквалайзер, компрессия и лимитер без AI-генерации.`;
    }

    if (currentUploadFlow === 'library' && !document.getElementById('library-enhance-quality')?.checked) {
        configureUploadFlow();
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

// --- AI Engine Selector ---

function setAiEngine(engine) {
    const input = document.getElementById('ai-engine');
    if (input) input.value = engine;

    ['stealth', 'audiosr', 'apollo', 'flowhigh'].forEach(eng => {
        const btn = document.getElementById(`engine-${eng}`);
        if (!btn) return;
        const firstSpan = btn.querySelector('span:first-child');
        if (eng === engine) {
            btn.className = 'ai-engine-btn px-2.5 py-2 rounded-lg text-xs font-semibold bg-indigo-600/30 border border-indigo-500 text-white shadow transition text-left';
            if (firstSpan) firstSpan.className = 'block text-indigo-300 font-bold';
        } else {
            btn.className = 'ai-engine-btn px-2.5 py-2 rounded-lg text-xs font-semibold bg-slate-800 border border-white/10 text-slate-300 hover:text-white hover:border-indigo-500/50 transition text-left';
            if (firstSpan) firstSpan.className = 'block text-white font-bold';
        }
    });
}

// --- Pro-Q 3 Canvas Pre-Filter State & Drawing ---

let proQState = {
    crossoverFreq: 15500,
    mudNotchDb: -1.5,
    mudFreq: 350,
    draggingNode: null,
    isInitialized: false
};

function initProQCanvas() {
    const canvas = document.getElementById('pro-q-canvas');
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
        setTimeout(initProQCanvas, 60);
        return;
    }

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    drawProQCurve();

    if (!proQState.isInitialized) {
        bindProQInteractions(canvas);
        proQState.isInitialized = true;
    }
}

function freqToX(freq, width) {
    const minF = 20;
    const maxF = 22000;
    const ratio = (Math.log10(freq) - Math.log10(minF)) / (Math.log10(maxF) - Math.log10(minF));
    return Math.max(0, Math.min(width, ratio * width));
}

function xToFreq(x, width) {
    const minF = 20;
    const maxF = 22000;
    const ratio = Math.max(0, Math.min(1, x / width));
    return Math.pow(10, Math.log10(minF) + ratio * (Math.log10(maxF) - Math.log10(minF)));
}

function dbToY(db, height) {
    const minDb = -6.0;
    const maxDb = 6.0;
    const ratio = 1 - (db - minDb) / (maxDb - minDb);
    return height * (0.15 + ratio * 0.7);
}

function yToDb(y, height) {
    const minDb = -6.0;
    const maxDb = 6.0;
    const ratio = (y - height * 0.15) / (height * 0.7);
    const db = maxDb - ratio * (maxDb - minDb);
    return Math.max(-6, Math.min(0, db));
}

function drawProQCurve() {
    const canvas = document.getElementById('pro-q-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Grid lines: 100Hz, 1kHz, 10kHz
    const gridFreqs = [100, 1000, 10000];
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.07)';
    ctx.lineWidth = 1 * dpr;
    gridFreqs.forEach(f => {
        const x = freqToX(f, width);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();

        ctx.fillStyle = 'rgba(148, 163, 184, 0.4)';
        ctx.font = `${9 * dpr}px monospace`;
        ctx.fillText(f >= 1000 ? `${f / 1000}k` : `${f}`, x + 3 * dpr, 12 * dpr);
    });

    // Zero dB line
    const zeroY = dbToY(0, height);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.setLineDash([4 * dpr, 4 * dpr]);
    ctx.beginPath();
    ctx.moveTo(0, zeroY);
    ctx.lineTo(width, zeroY);
    ctx.stroke();
    ctx.setLineDash([]);

    // AI Super-Resolution shaded band (above crossover frequency)
    const crossX = freqToX(proQState.crossoverFreq, width);
    const gradAir = ctx.createLinearGradient(crossX, 0, width, 0);
    gradAir.addColorStop(0, 'rgba(245, 158, 11, 0.05)');
    gradAir.addColorStop(1, 'rgba(245, 158, 11, 0.22)');
    ctx.fillStyle = gradAir;
    ctx.fillRect(crossX, 0, width - crossX, height);

    // Crossover vertical dashed line
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.85)';
    ctx.lineWidth = 1.5 * dpr;
    ctx.setLineDash([3 * dpr, 3 * dpr]);
    ctx.beginPath();
    ctx.moveTo(crossX, 0);
    ctx.lineTo(crossX, height);
    ctx.stroke();
    ctx.setLineDash([]);

    // Curve rendering
    const points = [];
    const steps = 150;
    for (let i = 0; i <= steps; i++) {
        const x = (i / steps) * width;
        const f = xToFreq(x, width);

        // Bell Notch at mudFreq (350 Hz, Q=1.6)
        const diffLn = Math.log(f) - Math.log(proQState.mudFreq);
        const notchAtten = proQState.mudNotchDb * Math.exp(-(diffLn * diffLn) / (2 * 0.45 * 0.45));

        const y = dbToY(notchAtten, height);
        points.push({ x, y });
    }

    // Fill under curve
    ctx.beginPath();
    ctx.moveTo(0, height);
    points.forEach((pt) => {
        ctx.lineTo(pt.x, pt.y);
    });
    ctx.lineTo(width, height);
    ctx.closePath();
    const fillGrad = ctx.createLinearGradient(0, 0, 0, height);
    fillGrad.addColorStop(0, 'rgba(99, 102, 241, 0.25)');
    fillGrad.addColorStop(1, 'rgba(99, 102, 241, 0.01)');
    ctx.fillStyle = fillGrad;
    ctx.fill();

    // Draw main curve stroke
    ctx.beginPath();
    points.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
    });
    ctx.strokeStyle = '#818cf8';
    ctx.lineWidth = 2 * dpr;
    ctx.stroke();

    // De-Mud Node circle at 350 Hz
    const notchX = freqToX(proQState.mudFreq, width);
    const notchY = dbToY(proQState.mudNotchDb, height);

    ctx.beginPath();
    ctx.arc(notchX, notchY, 5 * dpr, 0, Math.PI * 2);
    ctx.fillStyle = '#6366f1';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5 * dpr;
    ctx.stroke();

    // Crossover handle circle at top of crossover line
    const crossHandleY = 16 * dpr;
    ctx.beginPath();
    ctx.arc(crossX, crossHandleY, 5 * dpr, 0, Math.PI * 2);
    ctx.fillStyle = '#f59e0b';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5 * dpr;
    ctx.stroke();
}

function bindProQInteractions(canvas) {
    const dpr = window.devicePixelRatio || 1;

    const getPos = (e) => {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (e.clientX - rect.left) * dpr,
            y: (e.clientY - rect.top) * dpr
        };
    };

    canvas.addEventListener('mousedown', (e) => {
        const pos = getPos(e);
        const crossX = freqToX(proQState.crossoverFreq, canvas.width);
        const notchX = freqToX(proQState.mudFreq, canvas.width);
        const notchY = dbToY(proQState.mudNotchDb, canvas.height);

        if (Math.abs(pos.x - crossX) < 16 * dpr) {
            proQState.draggingNode = 'crossover';
        } else if (Math.hypot(pos.x - notchX, pos.y - notchY) < 18 * dpr) {
            proQState.draggingNode = 'notch';
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!proQState.draggingNode) return;
        const pos = getPos(e);

        if (proQState.draggingNode === 'crossover') {
            const freq = Math.round(xToFreq(pos.x, canvas.width));
            const clamped = Math.max(10000, Math.min(19000, freq));
            const slider = document.getElementById('crossover-slider');
            if (slider) slider.value = clamped;
            updateProQCrossover(clamped);
        } else if (proQState.draggingNode === 'notch') {
            const db = yToDb(pos.y, canvas.height);
            const stepped = Math.round(db * 2) / 2; // 0.5 step
            const clamped = Math.max(-6, Math.min(0, stepped));
            const slider = document.getElementById('notch-slider');
            if (slider) slider.value = clamped;
            updateProQNotch(clamped);
        }
    });

    window.addEventListener('mouseup', () => {
        proQState.draggingNode = null;
    });
}

function updateProQCrossover(val) {
    proQState.crossoverFreq = Number(val);
    const khz = (proQState.crossoverFreq / 1000).toFixed(1);
    const label = document.getElementById('crossover-marker-label');
    const badge = document.getElementById('crossover-val');
    if (label) label.textContent = `Crossover: ${khz} kHz`;
    if (badge) badge.textContent = `${khz} kHz`;
    drawProQCurve();
}

function updateProQNotch(val) {
    proQState.mudNotchDb = Number(val);
    const badge = document.getElementById('notch-val');
    if (badge) badge.textContent = `${proQState.mudNotchDb > 0 ? '+' : ''}${proQState.mudNotchDb.toFixed(1)} dB`;
    drawProQCurve();
}

window.addEventListener('resize', () => {
    initProQCanvas();
});

function updateDspPreset() {
    const preset = document.getElementById('dsp-preset').value;
    const presets = {
        "mastering": { stereo: 100, bass: 0, clarity: 0, comp: 50, rev: false, notch: -1.5 },
        "vocal_polish": { stereo: 110, bass: -1.5, clarity: 4.5, comp: 55, rev: true, revSize: 35, revMix: 15, notch: -2.0 },
        "club_bass": { stereo: 115, bass: 5, clarity: 1.0, comp: 65, rev: false, notch: -1.0 },
        "broadcast": { stereo: 100, bass: 0, clarity: 2.0, comp: 75, rev: false, notch: -1.5 },
        "tape_warmth": { stereo: 95, bass: 1.5, clarity: 0.5, comp: 45, rev: true, revSize: 25, revMix: 10, notch: -1.0 },
        "natural_air": { stereo: 120, bass: 0, clarity: 3.0, comp: 40, rev: false, notch: -1.5 },
        "music_fix": { stereo: 105, bass: 0, clarity: 1.0, comp: 50, rev: false, notch: -2.5 },
        "audio_repair": { stereo: 100, bass: 0, clarity: 0, comp: 45, rev: false, notch: 0.0 },
        "deep_bass": { stereo: 100, bass: 6, clarity: 1.5, comp: 60, rev: false, notch: -1.0 },
        "clear": { stereo: 110, bass: -2, clarity: 5, comp: 40, rev: false, notch: -2.0 },
        "warm": { stereo: 90, bass: 2, clarity: -1, comp: 60, rev: true, revSize: 30, revMix: 10, notch: -1.0 },
        "punchy": { stereo: 100, bass: 4, clarity: 2, comp: 80, rev: false, notch: -1.5 },
        "stealth": { stereo: 115, bass: 0.5, clarity: 1.0, comp: 55, rev: false, notch: -2.0 }
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

        if (config.notch !== undefined) {
            const notchSlider = document.getElementById('notch-slider');
            if (notchSlider) notchSlider.value = config.notch;
            updateProQNotch(config.notch);
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

const libraryEnhance = document.getElementById('library-enhance-quality');
if (libraryEnhance) {
    libraryEnhance.onchange = updateLibraryEnhanceUI;
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

    if (['mp3', 'ogg', 'm4a', 'opus'].includes(format)) {
        label.innerText = 'Bitrate';
        let opts = [];
        if (format === 'opus') {
            opts = [
                {v: '96k', t: '96 kbps (Voice/Light)'},
                {v: '128k', t: '128 kbps'},
                {v: '160k', t: '160 kbps (High Quality)'},
                {v: '192k', t: '192 kbps'},
                {v: '256k', t: '256 kbps (Ultra)'}
            ];
        } else if (format === 'm4a') {
            opts = [
                {v: '128k', t: '128 kbps (Standard)'},
                {v: '192k', t: '192 kbps'},
                {v: '256k', t: '256 kbps (Apple Music / Pro)'},
                {v: '320k', t: '320 kbps (Max)'}
            ];
        } else {
            opts = [
                {v: '128k', t: '128 kbps'},
                {v: '192k', t: '192 kbps'},
                {v: '256k', t: '256 kbps'},
                {v: '320k', t: '320 kbps (High)'}
            ];
            if (format === 'ogg') {
                opts.push({v: '500k', t: '500 kbps (Max)'});
            }
        }

        const defaultVal = format === 'opus' ? '160k' : (format === 'm4a' ? '256k' : '320k');
        opts.forEach(o => {
            const opt = document.createElement('option');
            opt.value = o.v; opt.text = o.t;
            if (o.v === defaultVal) opt.selected = true;
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
            if (o.v === '24-bit') opt.selected = true;
            select.appendChild(opt);
        });
    }
}

// --- Submit ---

async function startProcessing() {
    if (!currentUploadTrackId) return;

    const btn = document.getElementById('start-process-btn');
    btn.disabled = true;
    btn.innerHTML = currentUploadFlow === 'library'
        ? '<i data-lucide="loader-2" class="animate-spin w-5 h-5"></i> Добавляю...'
        : '<i data-lucide="loader-2" class="animate-spin w-5 h-5"></i> Обработка...';
    lucide.createIcons();

    const title = document.getElementById('input-title').value;
    const artist = document.getElementById('input-artist').value;
    const enhanceQuality = document.getElementById('library-enhance-quality')?.checked;
    const shouldProcess = currentUploadFlow !== 'library' || enhanceQuality;

    if (!shouldProcess) {
        try {
            const response = await fetch(`/edit/${currentUploadTrackId}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({ title, artist })
            });

            if (!response.ok) throw new Error(response.statusText);

            closeUploadModal();
            if (typeof fetchLibrary === 'function') fetchLibrary();
            else window.location.reload();
        } catch (e) {
            console.error(e);
            alert('Не удалось добавить трек в библиотеку: ' + e.message);
            btn.disabled = false;
            btn.innerHTML = 'Добавить в библиотеку';
        }
        return;
    }

    const percentToRatio = (id, fallback = 0) => {
        const value = Number(document.getElementById(id)?.value ?? fallback);
        return Number.isFinite(value) ? value / 100 : fallback / 100;
    };

    // Collect Data
    const payload = {
        title,
        artist,
        mode: document.getElementById('processing-mode').value,
        format: document.getElementById('target-format').value,
        sample_rate: document.getElementById('target-sr').value,
        bitrate: document.getElementById('target-bitrate').value,

        // AI
        engine: document.getElementById('ai-engine')?.value || 'audiosr',
        quality_preset: document.getElementById('quality-preset').value,
        steps: document.getElementById('ddim-steps').value,
        guidance: document.getElementById('guidance-scale').value,
        seed: document.getElementById('ai-seed').value,
        batch_size: document.getElementById('ai-batch-size').value,

        // DSP
        dsp_preset: document.getElementById('dsp-preset').value,
        crossover_freq: Number(document.getElementById('crossover-slider')?.value || 15500),
        mud_cut_db: Number(document.getElementById('notch-slider')?.value || -1.5),
        stereo_width: percentToRatio('stereo-width', 100),
        bass_boost: document.getElementById('bass-boost').value,
        voice_clarity: document.getElementById('voice-clarity').value,
        compressor_amount: percentToRatio('compressor-amount', 50),
        reverb_enabled: document.getElementById('reverb-enabled').checked,
        reverb_size: percentToRatio('reverb-size', 50),
        reverb_amount: percentToRatio('reverb-amount', 30)
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
            btn.innerHTML = currentUploadFlow === 'library' ? 'Добавить в библиотеку' : 'Запустить обработку';
        }
    } catch (e) {
        console.error(e);
        alert('Ошибка сети: ' + e.message);
        btn.disabled = false;
        btn.innerHTML = currentUploadFlow === 'library' ? 'Добавить в библиотеку' : 'Запустить обработку';
    }
}
