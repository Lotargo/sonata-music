(() => {
    const STORAGE_KEY = 'sonata_player_equalizer_v1';
    const MIN_FREQUENCY = 20;
    const MAX_FREQUENCY = 20000;
    const MIN_GAIN = -12;
    const MAX_GAIN = 12;
    const STANDARD_FREQUENCIES = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
    const FILTER_TYPES = new Set(['peaking', 'highpass', 'lowshelf', 'highshelf', 'notch']);

    const PRESETS = {
        flat:       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        rock:       [4, 3, 1, -1.5, -2, 0, 2, 3.5, 4, 3],
        electronic: [5, 4, 1, -1, -2, 0, 1.5, 3, 4.5, 5],
        vocal:      [-2, -1.5, -1, 0, 1.5, 3.5, 4, 2.5, 1, 0],
        bass:       [7, 6, 4, 2, 0, -1, -1.5, -1, 0, 1],
        acoustic:   [2, 2.5, 1.5, 0, 1, 2, 2.5, 2, 1.5, 2],
        air:        [-1, -1, -.5, 0, 0, .5, 1.5, 3, 5, 6],
    };

    const defaultBands = () => STANDARD_FREQUENCIES.map((frequency, index) => ({
        frequency,
        gain: 0,
        q: 1,
        type: index === 0 ? 'lowshelf' : (index === STANDARD_FREQUENCIES.length - 1 ? 'highshelf' : 'peaking'),
    }));

    const defaultState = () => ({
        enabled: false,
        preset: 'flat',
        bands: defaultBands(),
        bass: { enabled: false, amount: 0 },
        clarity: { enabled: false, amount: 0 },
        compressor: { enabled: false, amount: 35 },
    });

    const clamp = (value, min, max) => Math.min(max, Math.max(min, Number(value) || 0));

    function sanitizeState(raw) {
        const fallback = defaultState();
        if (!raw || typeof raw !== 'object') return fallback;

        const incomingBands = Array.isArray(raw.bands) ? raw.bands : [];
        fallback.enabled = Boolean(raw.enabled);
        fallback.preset = typeof raw.preset === 'string' ? raw.preset : 'custom';
        fallback.bands = fallback.bands.map((band, index) => {
            const incoming = incomingBands[index] || {};
            return {
                frequency: clamp(incoming.frequency ?? band.frequency, MIN_FREQUENCY, MAX_FREQUENCY),
                gain: clamp(incoming.gain ?? band.gain, MIN_GAIN, MAX_GAIN),
                q: clamp(incoming.q ?? band.q, .2, 12),
                type: FILTER_TYPES.has(incoming.type) ? incoming.type : band.type,
            };
        });
        fallback.bass = {
            enabled: Boolean(raw.bass?.enabled),
            amount: clamp(raw.bass?.amount, 0, 12),
        };
        fallback.clarity = {
            enabled: Boolean(raw.clarity?.enabled),
            amount: clamp(raw.clarity?.amount, 0, 8),
        };
        fallback.compressor = {
            enabled: Boolean(raw.compressor?.enabled),
            amount: clamp(raw.compressor?.amount ?? 35, 0, 100),
        };
        return fallback;
    }

    function loadState() {
        try {
            return sanitizeState(JSON.parse(localStorage.getItem(STORAGE_KEY)));
        } catch (_) {
            return defaultState();
        }
    }

    let state = loadState();
    let context = null;
    let connectedSource = null;
    let outputAnalyser = null;
    let dryGain = null;
    let wetGain = null;
    let filters = [];
    let bassFilter = null;
    let clarityFilter = null;
    let compressor = null;
    let selectedBand = 0;
    let draggedBand = null;
    let animationFrame = null;
    let lastFocused = null;

    function persistState() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (_) {}
    }

    function setAudioParam(param, value, smoothing = .018) {
        if (!param || !context) return;
        const time = context.currentTime;
        param.cancelScheduledValues(time);
        param.setTargetAtTime(value, time, smoothing);
    }

    function applyAudioState() {
        if (!context) return;

        setAudioParam(dryGain?.gain, state.enabled ? 0 : 1, .01);
        setAudioParam(wetGain?.gain, state.enabled ? 1 : 0, .01);

        filters.forEach((filter, index) => {
            const band = state.bands[index];
            filter.type = band.type;
            setAudioParam(filter.frequency, band.frequency);
            setAudioParam(filter.gain, band.gain);
            setAudioParam(filter.Q, band.q);
        });

        setAudioParam(bassFilter?.gain, state.bass.enabled ? state.bass.amount : 0);
        setAudioParam(clarityFilter?.gain, state.clarity.enabled ? state.clarity.amount : 0);

        if (compressor) {
            const amount = state.compressor.amount / 100;
            setAudioParam(compressor.threshold, state.compressor.enabled ? (-8 - amount * 30) : 0);
            setAudioParam(compressor.knee, state.compressor.enabled ? 18 : 0);
            setAudioParam(compressor.ratio, state.compressor.enabled ? (1 + amount * 7) : 1);
            setAudioParam(compressor.attack, .008 + amount * .012);
            setAudioParam(compressor.release, .16 + amount * .18);
        }
    }

    function connect(audioContext, source, analyserNode) {
        if (!audioContext || !source || !analyserNode) return false;
        if (connectedSource === source && context === audioContext) return true;

        context = audioContext;
        connectedSource = source;
        outputAnalyser = analyserNode;

        dryGain = context.createGain();
        wetGain = context.createGain();
        filters = state.bands.map(band => {
            const filter = context.createBiquadFilter();
            filter.type = band.type;
            filter.frequency.value = band.frequency;
            filter.gain.value = band.gain;
            filter.Q.value = band.q;
            return filter;
        });

        bassFilter = context.createBiquadFilter();
        bassFilter.type = 'lowshelf';
        bassFilter.frequency.value = 70;

        clarityFilter = context.createBiquadFilter();
        clarityFilter.type = 'peaking';
        clarityFilter.frequency.value = 2500;
        clarityFilter.Q.value = .85;

        compressor = context.createDynamicsCompressor();

        source.connect(dryGain);
        dryGain.connect(analyserNode);

        source.connect(filters[0]);
        for (let index = 0; index < filters.length - 1; index += 1) {
            filters[index].connect(filters[index + 1]);
        }
        filters[filters.length - 1].connect(bassFilter);
        bassFilter.connect(clarityFilter);
        clarityFilter.connect(compressor);
        compressor.connect(wetGain);
        wetGain.connect(analyserNode);

        applyAudioState();
        syncUi();
        return true;
    }

    function mutate(callback, options = {}) {
        callback(state);
        if (options.custom !== false) state.preset = 'custom';
        if (options.enable) state.enabled = true;
        persistState();
        applyAudioState();
        syncUi();
    }

    function resetEqualizer() {
        state = defaultState();
        persistState();
        applyAudioState();
        syncUi();
    }

    function applyPreset(name) {
        if (!PRESETS[name]) return;
        const standard = defaultBands();
        state.bands = standard.map((band, index) => ({ ...band, gain: PRESETS[name][index] }));
        state.preset = name;
        state.enabled = true;
        persistState();
        applyAudioState();
        syncUi();
    }

    function formatFrequency(value) {
        const frequency = Math.round(Number(value));
        if (frequency >= 1000) {
            const kilo = frequency / 1000;
            return `${Number.isInteger(kilo) ? kilo : kilo.toFixed(1)}K`;
        }
        return String(frequency);
    }

    function formatGain(value) {
        const gain = Number(value);
        if (Math.abs(gain) < .05) return '0.0 dB';
        return `${gain > 0 ? '+' : ''}${gain.toFixed(1)} dB`;
    }

    function buildBandControls() {
        const grid = document.getElementById('equalizer-band-grid');
        if (!grid || grid.children.length) return;

        grid.innerHTML = state.bands.map((band, index) => `
            <label class="equalizer-band" data-equalizer-band="${index}">
                <output class="equalizer-band-value">${formatGain(band.gain)}</output>
                <span class="equalizer-band-slider">
                    <input type="range" min="${MIN_GAIN}" max="${MAX_GAIN}" step="0.5" value="${band.gain}" aria-label="${formatFrequency(band.frequency)} герц">
                </span>
                <span class="equalizer-band-frequency">${formatFrequency(band.frequency)}</span>
            </label>
        `).join('');

        grid.querySelectorAll('.equalizer-band').forEach((control, index) => {
            const slider = control.querySelector('input');
            slider.addEventListener('input', () => {
                selectedBand = index;
                mutate(next => { next.bands[index].gain = clamp(slider.value, MIN_GAIN, MAX_GAIN); }, { enable: true });
            });
            slider.addEventListener('focus', () => {
                selectedBand = index;
                syncNodeEditor();
            });
        });
    }

    function syncBandControls() {
        document.querySelectorAll('[data-equalizer-band]').forEach((control, index) => {
            const band = state.bands[index];
            if (!band) return;
            const slider = control.querySelector('input');
            const value = control.querySelector('.equalizer-band-value');
            const frequency = control.querySelector('.equalizer-band-frequency');
            slider.value = band.gain;
            slider.setAttribute('aria-label', `${Math.round(band.frequency)} герц: ${formatGain(band.gain)}`);
            value.textContent = formatGain(band.gain);
            value.classList.toggle('is-boosted', band.gain > .05);
            frequency.textContent = formatFrequency(band.frequency);
        });
    }

    function syncNodeEditor() {
        const band = state.bands[selectedBand];
        if (!band) return;
        const number = document.getElementById('equalizer-node-number');
        const type = document.getElementById('equalizer-node-type');
        const frequency = document.getElementById('equalizer-node-frequency');
        const gain = document.getElementById('equalizer-node-gain');
        const q = document.getElementById('equalizer-node-q');
        const qValue = document.getElementById('equalizer-node-q-value');

        if (number) number.textContent = String(selectedBand + 1).padStart(2, '0');
        if (type) type.value = band.type;
        if (frequency) frequency.value = Math.round(band.frequency);
        if (gain) gain.value = band.gain.toFixed(1);
        if (q) q.value = band.q;
        if (qValue) qValue.textContent = band.q.toFixed(2);
    }

    function syncUi() {
        const enabled = document.getElementById('equalizer-enabled');
        const powerLabel = document.getElementById('equalizer-power-label');
        const preset = document.getElementById('equalizer-preset');
        const bassEnabled = document.getElementById('equalizer-bass-enabled');
        const bass = document.getElementById('equalizer-bass');
        const clarityEnabled = document.getElementById('equalizer-clarity-enabled');
        const clarity = document.getElementById('equalizer-clarity');
        const compressorEnabled = document.getElementById('equalizer-compressor-enabled');
        const compressorAmount = document.getElementById('equalizer-compressor');
        const trigger = document.getElementById('equalizer-trigger');
        const status = document.getElementById('equalizer-context-status');

        if (enabled) enabled.checked = state.enabled;
        if (powerLabel) powerLabel.textContent = state.enabled ? 'Включена' : 'Выключена';
        if (preset) preset.value = PRESETS[state.preset] ? state.preset : 'custom';
        if (bassEnabled) bassEnabled.checked = state.bass.enabled;
        if (bass) bass.value = state.bass.amount;
        if (clarityEnabled) clarityEnabled.checked = state.clarity.enabled;
        if (clarity) clarity.value = state.clarity.amount;
        if (compressorEnabled) compressorEnabled.checked = state.compressor.enabled;
        if (compressorAmount) compressorAmount.value = state.compressor.amount;

        const bassValue = document.getElementById('equalizer-bass-value');
        const clarityValue = document.getElementById('equalizer-clarity-value');
        const compressorValue = document.getElementById('equalizer-compressor-value');
        if (bassValue) bassValue.textContent = `${state.bass.amount.toFixed(1)} dB`;
        if (clarityValue) clarityValue.textContent = `${state.clarity.amount.toFixed(1)} dB`;
        if (compressorValue) compressorValue.textContent = `${Math.round(state.compressor.amount)}%`;

        if (trigger) {
            trigger.classList.toggle('is-active', state.enabled);
            trigger.setAttribute('aria-pressed', String(state.enabled));
        }
        if (status) status.textContent = context ? 'DSP подключён' : 'Активируется при воспроизведении';

        syncBandControls();
        syncNodeEditor();
    }

    function selectMode(mode) {
        const isClassic = mode === 'classic';
        const classicButton = document.getElementById('equalizer-tab-classic');
        const spectrumButton = document.getElementById('equalizer-tab-spectrum');
        const classicPanel = document.getElementById('equalizer-classic');
        const spectrumPanel = document.getElementById('equalizer-spectrum');

        classicButton?.classList.toggle('is-active', isClassic);
        spectrumButton?.classList.toggle('is-active', !isClassic);
        classicButton?.setAttribute('aria-selected', String(isClassic));
        spectrumButton?.setAttribute('aria-selected', String(!isClassic));
        classicPanel?.classList.toggle('hidden', !isClassic);
        spectrumPanel?.classList.toggle('hidden', isClassic);

        if (!isClassic) startSpectrum();
    }

    function frequencyToX(frequency, width) {
        const ratio = Math.log(frequency / MIN_FREQUENCY) / Math.log(MAX_FREQUENCY / MIN_FREQUENCY);
        return ratio * width;
    }

    function xToFrequency(x, width) {
        const ratio = clamp(x / width, 0, 1);
        return MIN_FREQUENCY * Math.pow(MAX_FREQUENCY / MIN_FREQUENCY, ratio);
    }

    function gainToY(gain, height) {
        return ((MAX_GAIN - gain) / (MAX_GAIN - MIN_GAIN)) * height;
    }

    function yToGain(y, height) {
        return MAX_GAIN - clamp(y / height, 0, 1) * (MAX_GAIN - MIN_GAIN);
    }

    function getFrequencyCurve(frequencies) {
        const curve = new Float32Array(frequencies.length);
        const activeFilters = [...filters];
        if (state.bass.enabled && bassFilter) activeFilters.push(bassFilter);
        if (state.clarity.enabled && clarityFilter) activeFilters.push(clarityFilter);

        if (activeFilters.length) {
            const magnitude = new Float32Array(frequencies.length);
            const phase = new Float32Array(frequencies.length);
            activeFilters.forEach(filter => {
                filter.getFrequencyResponse(frequencies, magnitude, phase);
                for (let index = 0; index < curve.length; index += 1) {
                    curve[index] += 20 * Math.log10(Math.max(magnitude[index], .00001));
                }
            });
            return curve;
        }

        state.bands.forEach(band => {
            for (let index = 0; index < curve.length; index += 1) {
                const distance = Math.log2(frequencies[index] / band.frequency);
                const width = Math.max(.12, 1 / band.q);
                curve[index] += band.gain * Math.exp(-(distance * distance) / (2 * width * width));
            }
        });
        return curve;
    }

    function drawSpectrum() {
        const modal = document.getElementById('equalizer-modal');
        const panel = document.getElementById('equalizer-spectrum');
        const canvas = document.getElementById('equalizer-spectrum-canvas');
        if (!canvas || modal?.classList.contains('hidden') || panel?.classList.contains('hidden')) {
            animationFrame = null;
            return;
        }

        const rect = canvas.getBoundingClientRect();
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        const width = Math.max(1, Math.round(rect.width));
        const height = Math.max(1, Math.round(rect.height));
        if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
            canvas.width = Math.round(width * dpr);
            canvas.height = Math.round(height * dpr);
        }

        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);

        const frequencyGuides = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
        ctx.lineWidth = 1;
        ctx.font = '9px Inter, Arial, sans-serif';
        ctx.textAlign = 'center';
        frequencyGuides.forEach(frequency => {
            const x = frequencyToX(frequency, width);
            ctx.strokeStyle = 'rgba(255,255,255,.055)';
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
            ctx.fillStyle = 'rgba(255,255,255,.28)';
            ctx.fillText(formatFrequency(frequency), x, height - 8);
        });

        [-12, -6, 0, 6, 12].forEach(gain => {
            const y = gainToY(gain, height);
            ctx.strokeStyle = gain === 0 ? 'rgba(255,255,255,.16)' : 'rgba(255,255,255,.05)';
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        });

        if (outputAnalyser && context) {
            const spectrum = new Uint8Array(outputAnalyser.frequencyBinCount);
            outputAnalyser.getByteFrequencyData(spectrum);
            ctx.beginPath();
            ctx.moveTo(0, height);
            for (let x = 0; x <= width; x += 2) {
                const frequency = xToFrequency(x, width);
                const bin = Math.min(spectrum.length - 1, Math.round((frequency / (context.sampleRate / 2)) * spectrum.length));
                const level = spectrum[bin] / 255;
                const y = height - 18 - level * (height - 38);
                ctx.lineTo(x, y);
            }
            ctx.lineTo(width, height);
            ctx.closePath();
            const fill = ctx.createLinearGradient(0, 0, 0, height);
            fill.addColorStop(0, 'rgba(255,210,30,.20)');
            fill.addColorStop(1, 'rgba(255,210,30,0)');
            ctx.fillStyle = fill;
            ctx.fill();
        }

        const sampleCount = Math.max(160, Math.round(width / 3));
        const frequencies = new Float32Array(sampleCount);
        for (let index = 0; index < sampleCount; index += 1) {
            frequencies[index] = xToFrequency((index / (sampleCount - 1)) * width, width);
        }
        const curve = getFrequencyCurve(frequencies);
        ctx.beginPath();
        curve.forEach((gain, index) => {
            const x = (index / (curve.length - 1)) * width;
            const y = gainToY(clamp(gain, MIN_GAIN, MAX_GAIN), height);
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = state.enabled ? '#ffd21e' : 'rgba(255,255,255,.45)';
        ctx.lineWidth = 2;
        ctx.stroke();

        state.bands.forEach((band, index) => {
            const x = frequencyToX(band.frequency, width);
            const y = gainToY(band.gain, height);
            ctx.beginPath();
            ctx.arc(x, y, index === selectedBand ? 7 : 5, 0, Math.PI * 2);
            ctx.fillStyle = index === selectedBand ? '#ffd21e' : '#f2f2f2';
            ctx.fill();
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#090a0b';
            ctx.stroke();
        });

        animationFrame = requestAnimationFrame(drawSpectrum);
    }

    function startSpectrum() {
        if (animationFrame) cancelAnimationFrame(animationFrame);
        animationFrame = requestAnimationFrame(drawSpectrum);
    }

    function canvasPosition(event) {
        const canvas = event.currentTarget;
        const rect = canvas.getBoundingClientRect();
        return {
            x: clamp(event.clientX - rect.left, 0, rect.width),
            y: clamp(event.clientY - rect.top, 0, rect.height),
            width: rect.width,
            height: rect.height,
        };
    }

    function nearestBand(point) {
        let nearest = 0;
        let distance = Infinity;
        state.bands.forEach((band, index) => {
            const x = frequencyToX(band.frequency, point.width);
            const y = gainToY(band.gain, point.height);
            const nextDistance = Math.hypot(point.x - x, point.y - y);
            if (nextDistance < distance) {
                distance = nextDistance;
                nearest = index;
            }
        });
        return nearest;
    }

    function moveSelectedBand(point) {
        mutate(next => {
            next.bands[selectedBand].frequency = Math.round(xToFrequency(point.x, point.width));
            next.bands[selectedBand].gain = Math.round(yToGain(point.y, point.height) * 10) / 10;
        }, { enable: true });
    }

    function bindEvents() {
        document.getElementById('equalizer-enabled')?.addEventListener('change', event => {
            mutate(next => { next.enabled = event.target.checked; }, { custom: false });
        });
        document.getElementById('equalizer-preset')?.addEventListener('change', event => {
            if (event.target.value !== 'custom') applyPreset(event.target.value);
        });
        document.getElementById('equalizer-reset')?.addEventListener('click', resetEqualizer);
        document.getElementById('equalizer-tab-classic')?.addEventListener('click', () => selectMode('classic'));
        document.getElementById('equalizer-tab-spectrum')?.addEventListener('click', () => selectMode('spectrum'));

        const bindEffect = (prefix, key, max) => {
            document.getElementById(`equalizer-${prefix}-enabled`)?.addEventListener('change', event => {
                mutate(next => { next[key].enabled = event.target.checked; }, { enable: event.target.checked });
            });
            document.getElementById(`equalizer-${prefix}`)?.addEventListener('input', event => {
                mutate(next => { next[key].amount = clamp(event.target.value, 0, max); }, { enable: true });
            });
        };
        bindEffect('bass', 'bass', 12);
        bindEffect('clarity', 'clarity', 8);
        bindEffect('compressor', 'compressor', 100);

        document.getElementById('equalizer-node-type')?.addEventListener('change', event => {
            mutate(next => { next.bands[selectedBand].type = event.target.value; }, { enable: true });
        });
        document.getElementById('equalizer-node-frequency')?.addEventListener('change', event => {
            mutate(next => { next.bands[selectedBand].frequency = clamp(event.target.value, MIN_FREQUENCY, MAX_FREQUENCY); }, { enable: true });
        });
        document.getElementById('equalizer-node-gain')?.addEventListener('change', event => {
            mutate(next => { next.bands[selectedBand].gain = clamp(event.target.value, MIN_GAIN, MAX_GAIN); }, { enable: true });
        });
        document.getElementById('equalizer-node-q')?.addEventListener('input', event => {
            mutate(next => { next.bands[selectedBand].q = clamp(event.target.value, .2, 12); }, { enable: true });
        });

        const canvas = document.getElementById('equalizer-spectrum-canvas');
        canvas?.addEventListener('pointerdown', event => {
            const point = canvasPosition(event);
            selectedBand = nearestBand(point);
            draggedBand = selectedBand;
            canvas.setPointerCapture(event.pointerId);
            moveSelectedBand(point);
        });
        canvas?.addEventListener('pointermove', event => {
            if (draggedBand === null) return;
            moveSelectedBand(canvasPosition(event));
        });
        const stopDragging = event => {
            draggedBand = null;
            if (event.pointerId !== undefined && canvas?.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
        };
        canvas?.addEventListener('pointerup', stopDragging);
        canvas?.addEventListener('pointercancel', stopDragging);
        canvas?.addEventListener('wheel', event => {
            event.preventDefault();
            const direction = event.deltaY > 0 ? -.15 : .15;
            mutate(next => {
                const band = next.bands[selectedBand];
                band.q = clamp(band.q + direction, .2, 12);
            }, { enable: true });
        }, { passive: false });
    }

    window.openEqualizer = () => {
        const modal = document.getElementById('equalizer-modal');
        if (!modal) return;
        lastFocused = document.activeElement;
        modal.classList.remove('hidden');
        modal.setAttribute('aria-hidden', 'false');
        syncUi();
        modal.querySelector('.equalizer-dialog')?.focus();
        if (!document.getElementById('equalizer-spectrum')?.classList.contains('hidden')) startSpectrum();
    };

    window.closeEqualizer = () => {
        const modal = document.getElementById('equalizer-modal');
        if (!modal) return;
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
        if (animationFrame) cancelAnimationFrame(animationFrame);
        animationFrame = null;
        if (lastFocused instanceof HTMLElement) lastFocused.focus();
        lastFocused = null;
    };

    window.handleEqualizerBackdrop = event => {
        if (event.target === event.currentTarget) closeEqualizer();
    };

    window.playerEqualizer = {
        connect,
        getState: () => JSON.parse(JSON.stringify(state)),
        reset: resetEqualizer,
    };

    document.addEventListener('keydown', event => {
        const modal = document.getElementById('equalizer-modal');
        if (event.key === 'Escape' && modal && !modal.classList.contains('hidden')) closeEqualizer();
    });

    document.addEventListener('DOMContentLoaded', () => {
        buildBandControls();
        bindEvents();
        syncUi();
        if (window.lucide) lucide.createIcons();
    });
})();
