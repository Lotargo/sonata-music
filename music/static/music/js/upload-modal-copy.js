function getLibraryFileActionLabel() {
    const enhanceQuality = document.getElementById('library-enhance-quality')?.checked;
    return enhanceQuality ? 'Запустить обработку' : 'Добавить файл';
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
    } else {
        aiSettings?.classList.add('hidden');
        dspSettings?.classList.add('hidden');
    }

    if (startBtn) {
        startBtn.innerHTML = isLibraryFlow ? getLibraryFileActionLabel() : 'Запустить обработку';
    }

    lucide.createIcons();
};

const originalResetUpload = resetUpload;
resetUpload = function() {
    originalResetUpload();
    const startBtn = document.getElementById('start-process-btn');
    if (startBtn && currentUploadFlow === 'library') {
        startBtn.innerHTML = 'Добавить файл';
    }
};

const originalStartProcessing = startProcessing;
startProcessing = async function() {
    if (!currentUploadTrackId) return;

    const btn = document.getElementById('start-process-btn');
    const isLibraryFlow = currentUploadFlow === 'library';
    const enhanceQuality = document.getElementById('library-enhance-quality')?.checked;
    const shouldProcess = !isLibraryFlow || enhanceQuality;

    btn.disabled = true;
    btn.innerHTML = isLibraryFlow && !shouldProcess
        ? '<i data-lucide="loader-2" class="animate-spin w-5 h-5"></i> Добавляю файл...'
        : '<i data-lucide="loader-2" class="animate-spin w-5 h-5"></i> Обработка...';
    lucide.createIcons();

    const title = document.getElementById('input-title').value;
    const artist = document.getElementById('input-artist').value;

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
            alert('Не удалось добавить файл: ' + e.message);
            btn.disabled = false;
            btn.innerHTML = 'Добавить файл';
        }
        return;
    }

    originalStartProcessing();
};

configureUploadFlow();
