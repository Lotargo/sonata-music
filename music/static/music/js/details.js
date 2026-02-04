// State
let wsOrig = null;
let wsProc = null;
let detailsTrackId = null;
let activeCompareAudio = 'proc'; // 'orig' or 'proc'
let isComparePlaying = false;

// DOM Elements
const detailsModal = document.getElementById('details-modal');
const metricsBody = document.getElementById('metrics-body');
const comparePlayBtn = document.getElementById('compare-play');
const viewSplitBtn = document.getElementById('view-split');
const viewOverlayBtn = document.getElementById('view-overlay');
const btnListenOrig = document.getElementById('btn-listen-orig');
const btnListenProc = document.getElementById('btn-listen-proc');

// Controls
function closeDetailsModal() {
    if (detailsModal) detailsModal.classList.add('hidden');
    if (wsOrig) wsOrig.destroy();
    if (wsProc) wsProc.destroy();
    wsOrig = null;
    wsProc = null;
    isComparePlaying = false;
}

window.openDetails = async (id) => {
    // Ensure we have track data
    let track = null;
    if (window.tracks) {
        track = window.tracks.find(t => t.id === id);
    }

    if (!track) {
        // Fallback: fetch library
        try {
            const res = await fetch('/library');
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

    // Reset UI
    const modal = document.getElementById('details-modal');
    modal.classList.remove('hidden');
    document.getElementById('details-title').textContent = track.title;
    metricsBody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-slate-500">Loading metrics...</td></tr>';

    // Reset Play Button
    isComparePlaying = false;
    updateComparePlayIcon();

    // Fetch Metrics
    try {
        const res = await fetch(`/metrics/${id}`);
        if (res.ok) {
            const data = await res.json();
            renderMetricsTable(data);
            initComparisonWaveforms(track, data);
        } else {
            metricsBody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-red-400">Metrics not available.</td></tr>';
        }
    } catch (e) {
        console.error(e);
        metricsBody.innerHTML = `<tr><td colspan="3" class="px-4 py-4 text-center text-red-400">Error loading metrics: ${e.message}</td></tr>`;
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
        { label: 'Dynamic Range (dB)', key: 'dynamic_range_db', diff: true },
        { label: 'Crest Factor', key: 'crest_factor', diff: true }
    ];

    metricsBody.innerHTML = metrics.map(m => {
        const v1 = parseFloat(orig[m.key]).toFixed(2);
        const v2 = parseFloat(proc[m.key]).toFixed(2);
        const diff = (v2 - v1).toFixed(2);

        let diffColor = 'text-slate-500';
        if (m.key === 'dynamic_range_db' || m.key === 'crest_factor') {
             // Higher is usually better or stylistic
             diffColor = diff > 0 ? 'text-green-400' : 'text-slate-500';
        } else {
             // Loudness changes
             diffColor = diff > 0 ? 'text-green-400' : (diff < 0 ? 'text-red-400' : 'text-slate-500');
        }

        const diffSign = diff > 0 ? '+' : '';

        return `
            <tr class="hover:bg-white/5 transition border-b border-white/5 last:border-0">
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
        height: 256, // Matches h-64
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
        progressColor: 'rgba(96, 165, 250, 0.8)',
        cursorColor: '#60a5fa',
    });

    wsProc = WaveSurfer.create({
        ...commonOptions,
        container: '#wave-proc',
        waveColor: 'rgba(34, 197, 94, 0.5)', // Green
        progressColor: 'rgba(74, 222, 128, 0.8)',
        cursorColor: '#4ade80',
    });

    // Load Audio
    // Original: via uploads serving
    // Processed: via library_files serving
    const origUrl = `/uploads/${track.filename}`;
    const procFilename = track.processed_path.split('/').pop();
    const procUrl = `/library_files/${procFilename}`;

    wsOrig.load(origUrl);
    wsProc.load(procUrl);

    // Sync Logic
    let isSeeking = false;

    const syncSeek = (p, source) => {
        if(!isSeeking) {
            isSeeking = true;
            if (source === 'orig' && wsProc) wsProc.seekTo(p);
            if (source === 'proc' && wsOrig) wsOrig.seekTo(p);
            isSeeking = false;
        }
    };

    wsOrig.on('seek', (p) => syncSeek(p, 'orig'));
    wsProc.on('seek', (p) => syncSeek(p, 'proc'));

    wsOrig.on('finish', () => { isComparePlaying = false; updateComparePlayIcon(); });
    wsProc.on('finish', () => { isComparePlaying = false; updateComparePlayIcon(); });

    // Play Button Logic
    if (comparePlayBtn) {
        comparePlayBtn.onclick = () => {
            if (isComparePlaying) {
                wsOrig.pause();
                wsProc.pause();
                isComparePlaying = false;
            } else {
                wsOrig.play();
                wsProc.play();
                isComparePlaying = true;
            }
            updateComparePlayIcon();
        };
    }

    // Default: Listen Processed, Split View
    setCompareAudio('proc');
    setVisualMode('split');
}

function updateComparePlayIcon() {
    if (comparePlayBtn) {
        comparePlayBtn.innerHTML = isComparePlaying
            ? '<i data-lucide="pause" class="fill-current w-6 h-6"></i>'
            : '<i data-lucide="play" class="fill-current w-6 h-6 ml-1"></i>';
        lucide.createIcons();
    }
}

function setCompareAudio(source) {
    activeCompareAudio = source;
    if(source === 'orig') {
        if(wsOrig) wsOrig.setMuted(false);
        if(wsProc) wsProc.setMuted(true);

        btnListenOrig.classList.remove('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
        btnListenOrig.classList.add('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/20');

        btnListenProc.classList.add('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
        btnListenProc.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
    } else {
        if(wsOrig) wsOrig.setMuted(true);
        if(wsProc) wsProc.setMuted(false);

        btnListenProc.classList.remove('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
        btnListenProc.classList.add('bg-indigo-600', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');

        btnListenOrig.classList.add('bg-slate-700', 'hover:bg-slate-600', 'border-white/5');
        btnListenOrig.classList.remove('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/20');
    }
}

function setVisualMode(mode) {
    const waveOrigWrapper = document.getElementById('wave-orig-wrapper');
    const waveProcWrapper = document.getElementById('wave-proc-wrapper');
    const viewSplit = document.getElementById('view-split');
    const viewOverlay = document.getElementById('view-overlay');

    if (mode === 'overlay') {
        viewOverlay.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewOverlay.classList.remove('text-slate-400');
        viewSplit.classList.remove('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewSplit.classList.add('text-slate-400');

        // Overlay Mode
        waveOrigWrapper.style.top = '0';
        waveOrigWrapper.style.height = '100%';
        waveOrigWrapper.classList.remove('border-b');

        waveProcWrapper.style.top = '0';
        waveProcWrapper.style.height = '100%';
        waveProcWrapper.style.opacity = '0.7'; // Blend

    } else {
        // Split Mode
        viewSplit.classList.add('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewSplit.classList.remove('text-slate-400');
        viewOverlay.classList.remove('bg-slate-700', 'text-white', 'shadow', 'font-medium');
        viewOverlay.classList.add('text-slate-400');

        // Top half / Bottom half
        waveOrigWrapper.style.top = '0';
        waveOrigWrapper.style.height = '50%';
        waveOrigWrapper.classList.add('border-b');

        waveProcWrapper.style.top = '50%';
        waveProcWrapper.style.height = '50%';
        waveProcWrapper.style.opacity = '1';
    }

    // Trigger redraw
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 100);
}
