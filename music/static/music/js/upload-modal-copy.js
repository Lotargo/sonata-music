function getLibraryFileActionLabel() {
    const enhanceQuality = document.getElementById('library-enhance-quality')?.checked;
    return enhanceQuality ? 'Запустить обработку' : 'Добавить файл';
}

function isBitrateValueAllowedForFormat(format, value) {
    if (!value) return false;
    if (format === 'mp3') return ['128k', '192k', '256k', '320k'].includes(value);
    if (format === 'ogg') return ['128k', '192k', '256k', '320k', '500k'].includes(value);
    return ['16-bit', '24-bit', '32-bit'].includes(value);
}

function getDefaultBitrateValueForFormat(format) {
    return (format === 'mp3' || format === 'ogg') ? '320k' : '24-bit';
}

function ensureUploadBitrateOptions(force = false) {
    const formatSelect = document.getElementById('target-format');
    const bitrateSelect = document.getElementById('target-bitrate');
    if (!formatSelect || !bitrateSelect) return;

    const format = formatSelect.value || 'mp3';
    const previousValue = bitrateSelect.value;
    const hasOptions = bitrateSelect.options.length > 0;
    const hasValidValue = isBitrateValueAllowedForFormat(format, previousValue);

    if (force || !hasOptions || !hasValidValue) {
        updateBitrateOptions();
    }

    if (!isBitrateValueAllowedForFormat(format, bitrateSelect.value)) {
        const fallback = getDefaultBitrateValueForFormat(format);
        const fallbackExists = Array.from(bitrateSelect.options).some(option => option.value === fallback);
        if (fallbackExists) bitrateSelect.value = fallback;
    }
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
        ensureUploadBitrateOptions();
    } else {
        aiSettings?.classList.add('hidden');
        dspSettings?.classList.add('hidden');
    }

    if (startBtn) {
        startBtn.innerHTML = isLibraryFlow ? getLibraryFileActionLabel() : 'Запустить обработку';
    }

    lucide.createIcons();
};

const originalOpenUploadModal = openUploadModal;
openUploadModal = function(flow = 'library') {
    originalOpenUploadModal(flow);
    ensureUploadBitrateOptions(true);
};

const originalShowConfigUI = showConfigUI;
showConfigUI = function(track) {
    const result = originalShowConfigUI(track);
    ensureUploadBitrateOptions();
    return result;
};

const originalResetUpload = resetUpload;
resetUpload = function() {
    originalResetUpload();

    const formatSelect = document.getElementById('target-format');
    if (formatSelect) formatSelect.value = 'mp3';

    const sampleRateSelect = document.getElementById('target-sr');
    if (sampleRateSelect) sampleRateSelect.value = '48000';

    ensureUploadBitrateOptions(true);

    const startBtn = document.getElementById('start-process-btn');
    if (startBtn && currentUploadFlow === 'library') {
        startBtn.innerHTML = 'Добавить файл';
    }
};

const originalStartProcessing = startProcessing;
startProcessing = async function() {
    if (!currentUploadTrackId) return;

    ensureUploadBitrateOptions();

    const btn = document.getElementById('start-process-btn');
    const isLibraryFlow = currentUploadFlow === 'library';
    const enhanceQuality = document.getElementById('library-enhance-quality')?.checked;
    const shouldProcess = !isLibraryFlow || enhanceQuality;

    if (shouldProcess) {
        const result = originalStartProcessing();
        if (isLibraryFlow && btn) {
            btn.innerHTML = '<i data-lucide="loader-2" class="animate-spin w-5 h-5"></i> Обработка...';
            lucide.createIcons();
        }
        return result;
    }

    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" class="animate-spin w-5 h-5"></i> Добавляю файл...';
    lucide.createIcons();

    const title = document.getElementById('input-title').value;
    const artist = document.getElementById('input-artist').value;

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
        alert('Не удалось добавить файл: ' + e.message);
        btn.disabled = false;
        btn.innerHTML = 'Добавить файл';
    }
};

ensureUploadBitrateOptions(true);
configureUploadFlow();
