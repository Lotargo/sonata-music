// State
let wsOrig = null;
let wsProc = null;
let detailsTrackId = null;
let activeCompareAudio = 'proc'; // 'orig' or 'proc'
let isComparePlaying = false;
let compareSyncTimer = null;
let waveformReadyState = { orig: false, proc: false };

// DOM Elements
const detailsModal = document.getElementById('details-modal');
const metricsBody = document.getElementById('metrics-body');
const comparePlayBtn = document.getElementById('compare-play');
const btnListenOrig = document.getElementById('btn-listen-orig');
const btnListenProc = document.getElementById('btn-listen-proc');

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
        { label: 'RMS (dB)', original: orig.rms_db, processed: proc.rms_db },
        { label: 'Dynamic Range (dB)', original: orig.dynamic_range_db, processed: proc.dynamic_range_db },
        { label: 'Crest Factor', original: derivedOrigCrest, processed: derivedProcCrest },
    ];

    metricsBody.innerHTML = metricRows.map(row => {
        const originalNumber = Number(row.original);
        const processedNumber = Number(row.processed);
        const diffNumber = processedNumber - originalNumber;
        const diff = formatDiff(diffNumber);

        return `
            <tr class="hover:bg-white/5 transition border-b border-white/5 last:border-0">
                <td class="px-4 py-3 font-medium text-slate-300">${row.label}</td>
                <td class="px-4 py-3 font-mono text-slate-400">${formatMetricValue(row.original)}</td>
                <td class="px-4 py-3 font-mono text-white font-bold">
                    <span class="inline-flex items-center gap-2">
                        ${formatMetricValue(row.processed)}
                        ${diff.text ? `<span class="text-xs ${diff.className} font-normal">${diff.text}</span>` : ''}
                    </span>
                </td>
            </tr>
        `;
    }).join('');
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
}

function updateComparePlayIcon() {
    if (comparePlayBtn) {
        comparePlayBtn.innerHTML = isComparePlaying
            ? '<i data-lucide="pause" class="fill-current w-6 h-6"></i>'
            : '<i data-lucide="play" class="fill-current w-6 h-6 ml-1"></i>';
        safeLucideRefresh();
    }
}

function setCompareAudio(source, markActive = true) {
    activeCompareAudio = source;
    if (wsOrig) wsOrig.setMuted(source !== 'orig');
    if (wsProc) wsProc.setMuted(source !== 'proc');

    btnListenOrig?.classList.toggle('is-active', markActive && source === 'orig');
    btnListenProc?.classList.toggle('is-active', markActive && source === 'proc');

    if (isComparePlaying && wsOrig && wsProc) {
        const anchor = source === 'orig' ? wsOrig : wsProc;
        const t = anchor.getCurrentTime() || 0;
        wsOrig.setTime(t);
        wsProc.setTime(t);
    }
}

function setVisualMode(mode) {
    const waveOrigWrapper = document.getElementById('wave-orig-wrapper');
    const waveProcWrapper = document.getElementById('wave-proc-wrapper');
    const viewSplit = document.getElementById('view-split');
    const viewOverlay = document.getElementById('view-overlay');
    if (!waveOrigWrapper || !waveProcWrapper || !viewSplit || !viewOverlay) return;

    if (mode === 'overlay') {
        viewOverlay.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewOverlay.classList.remove('text-slate-400');
        viewSplit.classList.remove('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewSplit.classList.add('text-slate-400');

        waveOrigWrapper.style.top = '0';
        waveOrigWrapper.style.height = '100%';
        waveOrigWrapper.classList.remove('border-b');

        waveProcWrapper.style.top = '0';
        waveProcWrapper.style.height = '100%';
        waveProcWrapper.style.opacity = '0.7';
    } else {
        viewSplit.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewSplit.classList.remove('text-slate-400');
        viewOverlay.classList.remove('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewOverlay.classList.add('text-slate-400');

        waveOrigWrapper.style.top = '0';
        waveOrigWrapper.style.height = '50%';
        waveOrigWrapper.classList.add('border-b');

        waveProcWrapper.style.top = '50%';
        waveProcWrapper.style.height = '50%';
        waveProcWrapper.style.opacity = '1';
    }

    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 100);
}
