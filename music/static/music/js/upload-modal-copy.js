function getLibraryFileActionLabel() {
    const enhanceQuality = document.getElementById('library-enhance-quality')?.checked;
    return enhanceQuality ? 'Запустить обработку' : 'Добавить файл';
}

const UPLOAD_FORMAT_OPTIONS = {
    mp3: {
        label: 'Bitrate',
        defaultValue: '320k',
        options: [
            { value: '128k', text: '128 kbps' },
            { value: '192k', text: '192 kbps' },
            { value: '256k', text: '256 kbps' },
            { value: '320k', text: '320 kbps (High)' }
        ]
    },
    ogg: {
        label: 'Bitrate',
        defaultValue: '320k',
        options: [
            { value: '128k', text: '128 kbps' },
            { value: '192k', text: '192 kbps' },
            { value: '256k', text: '256 kbps' },
            { value: '320k', text: '320 kbps (High)' },
            { value: '500k', text: '500 kbps (Max)' }
        ]
    },
    wav: {
        label: 'Bit Depth',
        defaultValue: '24-bit',
        options: [
            { value: '16-bit', text: '16-bit (CD)' },
            { value: '24-bit', text: '24-bit (Studio)' },
            { value: '32-bit', text: '32-bit Float' }
        ]
    },
    flac: {
        label: 'Bit Depth',
        defaultValue: '24-bit',
        options: [
            { value: '16-bit', text: '16-bit (CD)' },
            { value: '24-bit', text: '24-bit (Studio)' },
            { value: '32-bit', text: '32-bit Float' }
        ]
    }
};

function getUploadFormatConfig(format) {
    return UPLOAD_FORMAT_OPTIONS[(format || 'mp3').toLowerCase()] || UPLOAD_FORMAT_OPTIONS.mp3;
}

function isBitrateValueAllowedForFormat(format, value) {
    if (!value) return false;
    return getUploadFormatConfig(format).options.some(option => option.value === value);
}

function ensureUploadBitrateOptions(preferredValue = null) {
    const formatSelect = document.getElementById('target-format');
    const bitrateSelect = document.getElementById('target-bitrate');
    const bitrateLabel = document.getElementById('bitrate-label');
    if (!formatSelect || !bitrateSelect) return null;

    const format = (formatSelect.value || 'mp3').toLowerCase();
    const config = getUploadFormatConfig(format);
    const previousValue = preferredValue || bitrateSelect.value;
    const selectedValue = isBitrateValueAllowedForFormat(format, previousValue)
        ? previousValue
        : config.defaultValue;

    if (bitrateLabel) bitrateLabel.innerText = config.label;

    const currentSignature = Array.from(bitrateSelect.options).map(option => `${option.value}:${option.text}`).join('|');
    const nextSignature = config.options.map(option => `${option.value}:${option.text}`).join('|');

    if (currentSignature !== nextSignature) {
        bitrateSelect.innerHTML = '';
        config.options.forEach(({ value, text }) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = text;
            bitrateSelect.appendChild(option);
        });
    }

    bitrateSelect.value = selectedValue;
    if (!isBitrateValueAllowedForFormat(format, bitrateSelect.value)) {
        bitrateSelect.value = config.defaultValue;
    }

    return bitrateSelect.value;
}

updateBitrateOptions = function(preferredValue = null) {
    return ensureUploadBitrateOptions(preferredValue);
};

function bindUploadFormatControls() {
    const formatSelect = document.getElementById('target-format');
    if (formatSelect && formatSelect.dataset.bitrateBound !== 'true') {
        formatSelect.addEventListener('change', () => ensureUploadBitrateOptions());
        formatSelect.dataset.bitrateBound = 'true';
    }
    ensureUploadBitrateOptions();
}

function resetUploadProcessingControls() {
    const formatSelect = document.getElementById('target-format');
    if (formatSelect) formatSelect.value = 'mp3';

    const sampleRateSelect = document.getElementById('target-sr');
    if (sampleRateSelect) sampleRateSelect.value = '48000';

    ensureUploadBitrateOptions('320k');
}

configureUploadFlow = function() {
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
            ? '<i data-lucide="upload-cloud" class="text-[var(--yellow)]"></i> Добавить файл'
            : '<i data-lucide="wand-sparkles" class="text-[var(--yellow)]"></i> Реставрация аудио';
    }

    libraryOptions?.classList.toggle('hidden', !isLibraryFlow);
    processingModeSection?.classList.toggle('hidden', !enhanceQuality);
    formatSettings?.classList.toggle('hidden', !enhanceQuality);

    if (enhanceQuality) {
        aiSettings?.classList.toggle('hidden', selectedMode !== 'ai');
        dspSettings?.classList.toggle('hidden', selectedMode === 'restoration');
        bindUploadFormatControls();
    } else {
        aiSettings?.classList.add('hidden');
        dspSettings?.classList.add('hidden');
    }

    if (startBtn) {
        startBtn.innerHTML = isLibraryFlow ? getLibraryFileActionLabel() : 'Запустить обработку';
    }

    if (window.lucide) lucide.createIcons();
};

const originalOpenUploadModal = openUploadModal;
openUploadModal = function(flow = 'library') {
    originalOpenUploadModal(flow);
    bindUploadFormatControls();
};

const originalShowConfigUI = showConfigUI;
showConfigUI = function(track) {
    const result = originalShowConfigUI(track);
    bindUploadFormatControls();
    return result;
};

const originalResetUpload = resetUpload;
resetUpload = function() {
    originalResetUpload();
    resetUploadProcessingControls();

    const startBtn = document.getElementById('start-process-btn');
    if (startBtn && currentUploadFlow === 'library') {
        startBtn.innerHTML = 'Добавить файл';
    }
};

const originalStartProcessing = startProcessing;
startProcessing = async function() {
    if (!currentUploadTrackId) return;
    ensureUploadBitrateOptions();
    return originalStartProcessing();
};

bindUploadFormatControls();
configureUploadFlow();
