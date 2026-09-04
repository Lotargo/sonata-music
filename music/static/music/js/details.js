// State
let wsOrig = null;
let wsProc = null;
let detailsTrackId = null;
let activeCompareAudio = 'proc'; // 'orig', 'proc', or 'delta'
let isComparePlaying = false;
let compareSyncTimer = null;
let waveformReadyState = { orig: false, proc: false };
let currentVisualMode = 'split'; // 'split', 'overlay', or 'spectrogram'
let currentSpecSource = 'proc'; // 'orig' or 'proc'
let cachedAudioBuffers = { orig: null, proc: null };
let currentMetricsData = null;
let webAudioCtx = null;
let webAudioGraph = null;

// DOM Elements
const detailsModal = document.getElementById('details-modal');
const metricsBody = document.getElementById('metrics-body');
const comparePlayBtn = document.getElementById('compare-play');
const btnListenOrig = document.getElementById('btn-listen-orig');
const btnListenProc = document.getElementById('btn-listen-proc');
const btnListenDelta = document.getElementById('btn-listen-delta');
const viewSpectrogram = document.getElementById('view-spectrogram');
const spectrogramContainer = document.getElementById('spectrogram-container');
const compareContainer = document.getElementById('compare-container');

function safeLucideRefresh() {
    if (window.lucide) lucide.createIcons();
}

function basenameFromUrl(value) {
    if (!value) return '';
    const clean = String(value).split('?')[0].split('#')[0];
    const name = clean.substring(clean.lastIndexOf('/') + 1);
    try {
        return decodeURIComponent(name);
    } catch (_) {
        return name;
    }
}

function extensionFromName(value) {
    const name = basenameFromUrl(value);
    const idx = name.lastIndexOf('.');
    return idx >= 0 ? name.slice(idx + 1).toUpperCase() : '';
}

function titleLooksLikeAudioFile(title, originalName) {
    const normalized = (title || '').trim().toLowerCase();
    if (!normalized) return true;
    if (originalName && normalized === originalName.toLowerCase()) return true;
    return /\.(mp3|wav|flac|ogg|m4a|aac|aiff|aif)$/i.test(normalized);
}

function getTrackDisplayTitle(track) {
    if (!track) return 'Track Details';
    const originalName = track.filename || basenameFromUrl(track.audio_url);
    const processedName = basenameFromUrl(track.processed_path);
    if (track.status === 'completed' && processedName && titleLooksLikeAudioFile(track.title, originalName)) {
        return processedName;
    }
    return track.title || processedName || originalName || 'Track Details';
}

function formatMetricValue(value, decimals = 2) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(decimals) : '—';
}

function formatDiff(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return { text: '', className: 'text-slate-500' };
    const sign = number > 0 ? '+' : '';
    const className = number > 0 ? 'text-green-400' : (number < 0 ? 'text-red-400' : 'text-slate-500');
    return { text: `(${sign}${number.toFixed(2)})`, className };
}

function formatSeconds(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds <= 0) return '—';
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${min}:${sec}`;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value || '—';
}

// Controls
function closeDetailsModal() {
    if (detailsModal) detailsModal.classList.add('hidden');
    clearInterval(compareSyncTimer);
    compareSyncTimer = null;
    if (wsOrig) wsOrig.destroy();
    if (wsProc) wsProc.destroy();
    wsOrig = null;
    wsProc = null;
    isComparePlaying = false;
    waveformReadyState = { orig: false, proc: false };
}

window.openDetails = async (id) => {
    let track = null;
    if (window.tracks) {
        track = window.tracks.find(t => t.id === id);
    }

    if (!track) {
        try {
            const res = await fetch('/library/');
            const tracks = await res.json();
            track = tracks.find(t => t.id === id);
        } catch(e) {
            console.error(e);
        }
    }

    if (!track || track.status !== 'completed') {
        alert('Track details not available (track might not be processed yet).');
        return;
    }

    detailsTrackId = track.id;

    const modal = document.getElementById('details-modal');
    modal.classList.remove('hidden');
    document.getElementById('details-title').textContent = getTrackDisplayTitle(track);
    document.getElementById('details-subtitle').textContent = 'Analysis and Comparison';
    metricsBody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-slate-500">Loading metrics...</td></tr>';

    isComparePlaying = false;
    updateComparePlayIcon();
    renderFileInfo(track, null);
    initComparisonWaveforms(track);

    try {
        const res = await fetch(`/metrics/${id}/`);
        if (res.ok) {
            const data = await res.json();
            renderMetricsTable(data);
            renderFileInfo(track, data);
        } else {
            metricsBody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-red-400">Metrics not available.</td></tr>';
        }
    } catch (e) {
        console.error(e);
        metricsBody.innerHTML = `<tr><td colspan="3" class="px-4 py-4 text-center text-red-400">Error loading metrics: ${e.message}</td></tr>`;
    }
};

function renderMetricsTable(data) {
    currentMetricsData = data;
    const orig = data.original || {};
    const proc = data.processed || {};

    const derivedOrigCrest = Number.isFinite(Number(orig.crest_factor))
        ? Number(orig.crest_factor)
        : Math.pow(10, Number(orig.dynamic_range_db || 0) / 20);
    const derivedProcCrest = Number.isFinite(Number(proc.crest_factor))
        ? Number(proc.crest_factor)
        : Math.pow(10, Number(proc.dynamic_range_db || 0) / 20);

    const metricRows = [
        { label: 'Peak (dB)', original: orig.peak_db, processed: proc.peak_db },
        { label: 'RMS Loudness (dB)', original: orig.rms_db, processed: proc.rms_db },
        { label: 'Dynamic Range (dB)', original: orig.dynamic_range_db, processed: proc.dynamic_range_db },
        { label: 'Crest Factor', original: derivedOrigCrest, processed: derivedProcCrest },
    ];

    if (orig.is_stereo || proc.is_stereo || Number.isFinite(Number(orig.stereo_correlation)) || Number.isFinite(Number(proc.stereo_correlation))) {
        metricRows.push(
            { label: 'Peak L / R (dB)', customOrig: `${formatMetricValue(orig.peak_l_db, 1)} / ${formatMetricValue(orig.peak_r_db, 1)}`, customProc: `${formatMetricValue(proc.peak_l_db, 1)} / ${formatMetricValue(proc.peak_r_db, 1)}` },
            { label: 'RMS L / R (dB)', customOrig: `${formatMetricValue(orig.rms_l_db, 1)} / ${formatMetricValue(orig.rms_r_db, 1)}`, customProc: `${formatMetricValue(proc.rms_l_db, 1)} / ${formatMetricValue(proc.rms_r_db, 1)}` },
            { label: 'Side Signal L-R (dB)', original: orig.rms_side_db, processed: proc.rms_side_db },
            { label: 'Stereo Correlation (ρ)', original: orig.stereo_correlation, processed: proc.stereo_correlation, isCorrelation: true },
            { label: 'Stereo Width Ratio', original: orig.stereo_width_ratio, processed: proc.stereo_width_ratio }
        );
    }

    metricsBody.innerHTML = metricRows.map(row => {
        if (row.customOrig !== undefined) {
            return `
                <tr class="hover:bg-white/5 transition border-b border-white/5 last:border-0">
                    <td class="px-4 py-3 font-medium text-slate-300">${row.label}</td>
                    <td class="px-4 py-3 font-mono text-slate-400">${row.customOrig}</td>
                    <td class="px-4 py-3 font-mono text-white font-bold">${row.customProc}</td>
                </tr>
            `;
        }

        const originalNumber = Number(row.original);
        const processedNumber = Number(row.processed);
        const diffNumber = processedNumber - originalNumber;
        const diff = formatDiff(diffNumber);

        let formattedProc = formatMetricValue(row.processed);
        if (row.isCorrelation) {
            const corr = Number(row.processed);
            if (Number.isFinite(corr)) {
                const sign = corr > 0 ? '+' : '';
                formattedProc = `${sign}${corr.toFixed(3)}`;
            }
        }

        return `
            <tr class="hover:bg-white/5 transition border-b border-white/5 last:border-0">
                <td class="px-4 py-3 font-medium text-slate-300">${row.label}</td>
                <td class="px-4 py-3 font-mono text-slate-400">${formatMetricValue(row.original)}</td>
                <td class="px-4 py-3 font-mono text-white font-bold">
                    <span class="inline-flex items-center gap-2">
                        ${formattedProc}
                        ${diff.text && !row.isCorrelation ? `<span class="text-xs ${diff.className} font-normal">${diff.text}</span>` : ''}
                    </span>
                </td>
            </tr>
        `;
    }).join('');

    updateCorrelationGauge(currentSpecSource);
}

function renderFileInfo(track, data) {
    const original = data?.original || {};
    const processed = data?.processed || {};

    const originalFile = original.filename || track.filename || basenameFromUrl(track.audio_url);
    const processedFile = processed.filename || basenameFromUrl(track.processed_path);
    const originalFormat = original.format || extensionFromName(originalFile || track.audio_url);
    const processedFormat = processed.format || extensionFromName(processedFile || track.processed_path);

    setText('info-file-orig', originalFile);
    setText('info-file-proc', processedFile);
    setText('info-format-orig', originalFormat);
    setText('info-format-proc', processedFormat);
    setText('info-sr-orig', original.sr ? `${original.sr} Hz` : '—');
    setText('info-sr-proc', processed.sr ? `${processed.sr} Hz` : '—');
    setText('info-duration-orig', formatSeconds(original.duration || track.duration));
    setText('info-duration-proc', formatSeconds(processed.duration));
}

function updateWaveLoading() {
    const loading = document.getElementById('wave-loading');
    if (!loading) return;
    const bothReady = waveformReadyState.orig && waveformReadyState.proc;
    loading.classList.toggle('hidden', bothReady);
}

function initComparisonWaveforms(track) {
    clearInterval(compareSyncTimer);
    compareSyncTimer = null;
    if (wsOrig) wsOrig.destroy();
    if (wsProc) wsProc.destroy();
    wsOrig = null;
    wsProc = null;
    waveformReadyState = { orig: false, proc: false };
    updateWaveLoading();

    const commonOptions = {
        height: 256,
        barWidth: 2,
        barRadius: 2,
        cursorWidth: 1,
        responsive: true,
        normalize: true,
        partialRender: true,
        interact: true,
        autoScroll: false,
        autoCenter: false,
        hideScrollbar: true,
        fetchParams: { cache: 'force-cache' }
    };

    wsOrig = WaveSurfer.create({
        ...commonOptions,
        container: '#wave-orig',
        waveColor: 'rgba(59, 130, 246, 0.5)',
        progressColor: 'rgba(96, 165, 250, 0.8)',
        cursorColor: '#60a5fa',
    });

    wsProc = WaveSurfer.create({
        ...commonOptions,
        container: '#wave-proc',
        waveColor: 'rgba(34, 197, 94, 0.5)',
        progressColor: 'rgba(74, 222, 128, 0.8)',
        cursorColor: '#4ade80',
    });

    const origUrl = track.audio_url || `/media/uploads/${track.filename}`;
    const procUrl = track.processed_path;

    if (origUrl) wsOrig.load(origUrl);
    if (procUrl) wsProc.load(procUrl);

    let isSeeking = false;

    const syncSeek = (progress, source) => {
        if (isSeeking) return;
        isSeeking = true;
        if (source === 'orig' && wsProc) wsProc.seekTo(progress);
        if (source === 'proc' && wsOrig) wsOrig.seekTo(progress);
        isSeeking = false;
    };

    const syncByTime = (source) => {
        if (!wsOrig || !wsProc || !isComparePlaying) return;
        const lead = source === 'orig' ? wsOrig : wsProc;
        const follow = source === 'orig' ? wsProc : wsOrig;
        const leadTime = lead.getCurrentTime();
        const followTime = follow.getCurrentTime();
        if (Number.isFinite(leadTime) && Number.isFinite(followTime) && Math.abs(leadTime - followTime) > 0.08) {
            follow.setTime(leadTime);
        }
    };

    wsOrig.on('ready', () => {
        waveformReadyState.orig = true;
        updateWaveLoading();
        wsOrig.setMuted(activeCompareAudio !== 'orig');
    });
    wsProc.on('ready', () => {
        waveformReadyState.proc = true;
        updateWaveLoading();
        wsProc.setMuted(activeCompareAudio !== 'proc');
    });

    wsOrig.on('seek', (p) => syncSeek(p, 'orig'));
    wsProc.on('seek', (p) => syncSeek(p, 'proc'));
    wsOrig.on('timeupdate', () => syncByTime('orig'));
    wsProc.on('timeupdate', () => syncByTime('proc'));

    const stopCompare = () => {
        if (wsOrig) wsOrig.pause();
        if (wsProc) wsProc.pause();
        isComparePlaying = false;
        updateComparePlayIcon();
    };

    wsOrig.on('finish', stopCompare);
    wsProc.on('finish', stopCompare);
    wsOrig.on('error', (e) => console.error('Original waveform error:', e));
    wsProc.on('error', (e) => console.error('Processed waveform error:', e));

    if (comparePlayBtn) {
        comparePlayBtn.onclick = async () => {
            if (!wsOrig || !wsProc) return;

            if (isComparePlaying) {
                wsOrig.pause();
                wsProc.pause();
                isComparePlaying = false;
            } else {
                const anchor = activeCompareAudio === 'orig' ? wsOrig : wsProc;
                const anchorTime = anchor.getCurrentTime() || 0;
                wsOrig.setTime(anchorTime);
                wsProc.setTime(anchorTime);
                setCompareAudio(activeCompareAudio, true);
                await Promise.all([wsOrig.play(), wsProc.play()]);
                isComparePlaying = true;
            }
            updateComparePlayIcon();
        };
    }

    compareSyncTimer = setInterval(() => {
        if (!isComparePlaying || !wsOrig || !wsProc) return;
        syncByTime(activeCompareAudio);
    }, 250);

    setCompareAudio('proc', false);
    setVisualMode('split');

    preloadAudioBuffersForSpectrogram(origUrl, procUrl);
}

function updateComparePlayIcon() {
    if (comparePlayBtn) {
        comparePlayBtn.innerHTML = isComparePlaying
            ? '<i data-lucide="pause" class="fill-current w-6 h-6"></i>'
            : '<i data-lucide="play" class="fill-current w-6 h-6"></i>';
        safeLucideRefresh();
    }
}

// 5ms micro-crossfade helper to eliminate clicks and pops
function fadeAudioVolume(ws, targetVolume, durationMs = 5, onDone = null) {
    if (!ws) return;
    const media = ws.getMediaElement ? ws.getMediaElement() : null;
    if (!media) {
        ws.setVolume(targetVolume);
        if (onDone) onDone();
        return;
    }

    const startVol = media.volume;
    const startTime = performance.now();

    function step(now) {
        const elapsed = now - startTime;
        const progress = Math.min(1, elapsed / durationMs);
        const current = startVol + (targetVolume - startVol) * progress;
        media.volume = Math.max(0, Math.min(1, current));
        if (progress < 1) {
            requestAnimationFrame(step);
        } else {
            media.volume = Math.max(0, Math.min(1, targetVolume));
            if (onDone) onDone();
        }
    }
    requestAnimationFrame(step);
}

function trySetupWebAudioDelta() {
    if (webAudioGraph) return;
    try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;
        webAudioCtx = new AudioContextClass();

        const mediaOrig = wsOrig?.getMediaElement?.();
        const mediaProc = wsProc?.getMediaElement?.();
        if (mediaOrig && mediaProc && !mediaOrig._hasDeltaSource) {
            const srcOrig = webAudioCtx.createMediaElementSource(mediaOrig);
            const srcProc = webAudioCtx.createMediaElementSource(mediaProc);
            const gainOrig = webAudioCtx.createGain();
            const gainProc = webAudioCtx.createGain();

            srcOrig.connect(gainOrig).connect(webAudioCtx.destination);
            srcProc.connect(gainProc).connect(webAudioCtx.destination);

            mediaOrig._hasDeltaSource = true;
            mediaProc._hasDeltaSource = true;

            webAudioGraph = { srcOrig, srcProc, gainOrig, gainProc };
        }
    } catch (e) {
        console.debug('Web Audio direct graph initialization skipped:', e);
    }
}

function setCompareAudio(source, markActive = true) {
    activeCompareAudio = source;

    btnListenOrig?.classList.toggle('is-active', markActive && source === 'orig');
    btnListenProc?.classList.toggle('is-active', markActive && source === 'proc');
    btnListenDelta?.classList.toggle('is-active', markActive && source === 'delta');

    if (!wsOrig || !wsProc) return;

    if (source === 'orig') {
        wsOrig.setMuted(false);
        fadeAudioVolume(wsOrig, 1.0, 5);
        fadeAudioVolume(wsProc, 0.0, 5, () => wsProc.setMuted(true));
        if (webAudioGraph) {
            webAudioGraph.gainOrig.gain.setValueAtTime(1.0, webAudioCtx.currentTime);
            webAudioGraph.gainProc.gain.setValueAtTime(0.0, webAudioCtx.currentTime);
        }
    } else if (source === 'proc') {
        wsProc.setMuted(false);
        fadeAudioVolume(wsProc, 1.0, 5);
        fadeAudioVolume(wsOrig, 0.0, 5, () => wsOrig.setMuted(true));
        if (webAudioGraph) {
            webAudioGraph.gainOrig.gain.setValueAtTime(0.0, webAudioCtx.currentTime);
            webAudioGraph.gainProc.gain.setValueAtTime(1.0, webAudioCtx.currentTime);
        }
    } else if (source === 'delta') {
        // Delta Solo Mode: un-mute both and sum with phase inversion
        trySetupWebAudioDelta();
        wsOrig.setMuted(false);
        wsProc.setMuted(false);

        if (webAudioGraph) {
            // Precise inverted phase difference: B - A
            webAudioGraph.gainOrig.gain.linearRampToValueAtTime(-1.0, webAudioCtx.currentTime + 0.005);
            webAudioGraph.gainProc.gain.linearRampToValueAtTime(1.0, webAudioCtx.currentTime + 0.005);
        } else {
            fadeAudioVolume(wsOrig, 0.8, 5);
            fadeAudioVolume(wsProc, 0.8, 5);
        }
    }

    if (isComparePlaying && wsOrig && wsProc) {
        const anchor = source === 'orig' ? wsOrig : wsProc;
        const t = anchor.getCurrentTime() || 0;
        wsOrig.setTime(t);
        wsProc.setTime(t);
    }
}

function setVisualMode(mode) {
    currentVisualMode = mode;
    const waveOrigWrapper = document.getElementById('wave-orig-wrapper');
    const waveProcWrapper = document.getElementById('wave-proc-wrapper');
    const viewSplit = document.getElementById('view-split');
    const viewOverlay = document.getElementById('view-overlay');
    const viewSpec = document.getElementById('view-spectrogram');
    const specContainer = document.getElementById('spectrogram-container');
    const waveContainer = document.getElementById('compare-container');

    if (!waveOrigWrapper || !waveProcWrapper || !viewSplit || !viewOverlay) return;

    // Reset button states
    [viewSplit, viewOverlay, viewSpec].forEach(btn => {
        if (!btn) return;
        btn.classList.remove('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        btn.classList.add('text-slate-400');
    });

    if (mode === 'spectrogram') {
        viewSpec?.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewSpec?.classList.remove('text-slate-400');
        waveContainer?.classList.add('hidden');
        specContainer?.classList.remove('hidden');
        renderStereoSpectrogram(currentSpecSource);
    } else {
        waveContainer?.classList.remove('hidden');
        specContainer?.classList.add('hidden');

        if (mode === 'overlay') {
            viewOverlay.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
            viewOverlay.classList.remove('text-slate-400');

            waveOrigWrapper.style.top = '0';
            waveOrigWrapper.style.height = '100%';
            waveOrigWrapper.classList.remove('border-b');

            waveProcWrapper.style.top = '0';
            waveProcWrapper.style.height = '100%';
            waveProcWrapper.style.opacity = '0.7';
        } else {
            viewSplit.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
            viewSplit.classList.remove('text-slate-400');

            waveOrigWrapper.style.top = '0';
            waveOrigWrapper.style.height = '50%';
            waveOrigWrapper.classList.add('border-b');

            waveProcWrapper.style.top = '50%';
            waveProcWrapper.style.height = '50%';
            waveProcWrapper.style.opacity = '1';
        }
    }

    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 100);
}

// Pre-load audio buffers for fast client-side spectrogram rendering
async function preloadAudioBuffersForSpectrogram(origUrl, procUrl) {
    cachedAudioBuffers = { orig: null, proc: null };
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;

    const ctx = new AudioContextClass();

    const fetchAndDecode = async (url, key) => {
        if (!url) return;
        try {
            const resp = await fetch(url);
            const buf = await resp.arrayBuffer();
            const decoded = await ctx.decodeAudioData(buf);
            cachedAudioBuffers[key] = decoded;
            if (currentVisualMode === 'spectrogram' && currentSpecSource === key) {
                renderStereoSpectrogram(key);
            }
        } catch (e) {
            console.debug(`Could not decode audio buffer for ${key}:`, e);
        }
    };

    fetchAndDecode(origUrl, 'orig');
    fetchAndDecode(procUrl, 'proc');
}

function switchSpectrogramSource(source) {
    currentSpecSource = source;
    const btnOrig = document.getElementById('btn-spec-orig');
    const btnProc = document.getElementById('btn-spec-proc');
    const tag = document.getElementById('spectrogram-source-tag');

    if (btnOrig && btnProc) {
        if (source === 'orig') {
            btnOrig.classList.replace('bg-slate-800', 'bg-blue-700');
            btnOrig.classList.replace('text-slate-400', 'text-white');
            btnProc.classList.replace('bg-emerald-700', 'bg-slate-800');
            btnProc.classList.replace('text-white', 'text-slate-400');
            if (tag) {
                tag.textContent = 'ORIGINAL';
                tag.className = 'px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30';
            }
        } else {
            btnProc.classList.replace('bg-slate-800', 'bg-emerald-700');
            btnProc.classList.replace('text-slate-400', 'text-white');
            btnOrig.classList.replace('bg-blue-700', 'bg-slate-800');
            btnOrig.classList.replace('text-white', 'text-slate-400');
            if (tag) {
                tag.textContent = 'PROCESSED';
                tag.className = 'px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-500/20 text-green-300 border border-green-500/30';
            }
        }
    }

    renderStereoSpectrogram(source);
    updateCorrelationGauge(source);
}

function updateCorrelationGauge(source) {
    const data = currentMetricsData ? (source === 'orig' ? currentMetricsData.original : currentMetricsData.processed) : null;
    if (!data) return;

    const corr = Number.isFinite(Number(data.stereo_correlation)) ? Number(data.stereo_correlation) : 1.0;
    const sideDb = Number.isFinite(Number(data.rms_side_db)) ? Number(data.rms_side_db) : -100;
    const widthRatio = Number.isFinite(Number(data.stereo_width_ratio)) ? Number(data.stereo_width_ratio) : 1.0;

    const corrBar = document.getElementById('corr-meter-bar');
    const corrVal = document.getElementById('corr-val');
    const sideVal = document.getElementById('side-val');
    const widthVal = document.getElementById('width-val');

    if (corrBar) {
        // Map [-1, 1] to [0%, 100%]
        const pct = Math.max(0, Math.min(100, ((corr + 1) / 2) * 100));
        corrBar.style.width = '12px';
        corrBar.style.marginLeft = `calc(${pct}% - 6px)`;

        if (corr >= 0.4) {
            corrBar.className = 'h-full bg-emerald-400 transition-all duration-300 rounded-full';
        } else if (corr >= 0.0) {
            corrBar.className = 'h-full bg-amber-400 transition-all duration-300 rounded-full';
        } else {
            corrBar.className = 'h-full bg-rose-500 transition-all duration-300 rounded-full';
        }
    }

    if (corrVal) {
        const sign = corr > 0 ? '+' : '';
        corrVal.textContent = `${sign}${corr.toFixed(2)}`;
        corrVal.className = `font-bold ${corr >= 0.4 ? 'text-emerald-300' : (corr >= 0 ? 'text-amber-300' : 'text-rose-400')}`;
    }

    if (sideVal) {
        sideVal.textContent = sideDb > -90 ? `${sideDb.toFixed(1)} dB` : '-∞ dB';
    }

    if (widthVal) {
        widthVal.textContent = `${widthRatio.toFixed(2)}x`;
    }
}

function renderStereoSpectrogram(sourceKey) {
    const canvasL = document.getElementById('spec-canvas-left');
    const canvasR = document.getElementById('spec-canvas-right');
    if (!canvasL || !canvasR) return;

    const buffer = cachedAudioBuffers[sourceKey];
    if (!buffer) {
        // Draw loading placeholder on canvases
        [canvasL, canvasR].forEach(c => {
            const ctx = c.getContext('2d');
            c.width = c.clientWidth || 400;
            c.height = c.clientHeight || 100;
            ctx.fillStyle = '#090d16';
            ctx.fillRect(0, 0, c.width, c.height);
            ctx.fillStyle = '#64748b';
            ctx.font = '11px monospace';
            ctx.textAlign = 'center';
            ctx.fillText('Computing FFT Spectrogram...', c.width / 2, c.height / 2);
        });
        return;
    }

    const chL = buffer.getChannelData(0);
    const chR = buffer.numberOfChannels > 1 ? buffer.getChannelData(1) : chL;
    const sampleRate = buffer.sampleRate;

    drawChannelSpectrogram(canvasL, chL, sampleRate, 'sky');
    drawChannelSpectrogram(canvasR, chR, sampleRate, 'emerald');
    updateCorrelationGauge(sourceKey);
}

// Real-time thermal heatmap spectrogram drawing on Canvas
function drawChannelSpectrogram(canvas, channelData, sampleRate, channelTheme) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width = Math.max(300, canvas.clientWidth || 400);
    const height = canvas.height = Math.max(80, canvas.clientHeight || 100);

    const numSlices = width;
    const sliceLen = 256;
    const totalSamples = channelData.length;
    const step = Math.max(1, Math.floor((totalSamples - sliceLen) / numSlices));

    const imgData = ctx.createImageData(width, height);
    const pixels = imgData.data;

    // Hann window
    const window = new Float32Array(sliceLen);
    for (let i = 0; i < sliceLen; i++) {
        window[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (sliceLen - 1)));
    }

    for (let col = 0; col < width; col++) {
        const offset = col * step;
        if (offset + sliceLen >= totalSamples) break;

        // Apply window
        const windowed = new Float32Array(sliceLen);
        for (let i = 0; i < sliceLen; i++) {
            windowed[i] = channelData[offset + i] * window[i];
        }

        // Discrete real Fourier bins (Nyquist: sliceLen / 2)
        const numBins = Math.floor(sliceLen / 2);
        for (let y = 0; y < height; y++) {
            // Frequency from bottom (0Hz) to top (Nyquist / sampleRate / 2)
            const binIdx = Math.floor(((height - 1 - y) / height) * numBins);
            const k = Math.min(numBins - 1, Math.max(0, binIdx));

            // Compute DFT component for bin k
            let real = 0, imag = 0;
            const angleStep = (2 * Math.PI * k) / sliceLen;
            for (let n = 0; n < sliceLen; n += 2) { // 2x stride for fast render
                const angle = angleStep * n;
                real += windowed[n] * Math.cos(angle);
                imag -= windowed[n] * Math.sin(angle);
            }

            const mag = Math.sqrt(real * real + imag * imag);
            const db = 20 * Math.log10(mag + 1e-5);
            // Normalize [-70 dB, 0 dB] -> [0, 1]
            const norm = Math.max(0, Math.min(1, (db + 70) / 70));

            // Studio thermal colormap: Deep Navy -> Magenta -> Amber -> White
            let r = 0, g = 0, b = 0;
            if (norm < 0.25) {
                const t = norm / 0.25;
                r = Math.floor(10 + t * 40);
                g = Math.floor(15 + t * 10);
                b = Math.floor(30 + t * 90);
            } else if (norm < 0.55) {
                const t = (norm - 0.25) / 0.3;
                r = Math.floor(50 + t * 150);
                g = Math.floor(25 + t * 10);
                b = Math.floor(120 + t * 80);
            } else if (norm < 0.85) {
                const t = (norm - 0.55) / 0.3;
                r = Math.floor(200 + t * 55);
                g = Math.floor(35 + t * 140);
                b = Math.floor(200 * (1 - t));
            } else {
                const t = (norm - 0.85) / 0.15;
                r = 255;
                g = Math.floor(175 + t * 80);
                b = Math.floor(t * 220);
            }

            const pixelIdx = (y * width + col) * 4;
            pixels[pixelIdx] = r;
            pixels[pixelIdx + 1] = g;
            pixels[pixelIdx + 2] = b;
            pixels[pixelIdx + 3] = 255; // Alpha
        }
    }

    ctx.putImageData(imgData, 0, 0);

    // Subtle frequency grid lines at 1 kHz, 5 kHz, 15 kHz
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 1;
    [0.25, 0.5, 0.75].forEach(ratio => {
        const lineY = Math.floor(height * (1 - ratio));
        ctx.beginPath();
        ctx.moveTo(0, lineY);
        ctx.lineTo(width, lineY);
        ctx.stroke();
    });
}
