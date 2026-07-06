let comparisonGuardReplayingClick = false;

document.addEventListener('click', async (event) => {
    const compareButton = event.target.closest?.('#compare-play');
    if (!compareButton || comparisonGuardReplayingClick) return;
    if (typeof window.pauseMainPlayerForComparison !== 'function') return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    await window.pauseMainPlayerForComparison();

    comparisonGuardReplayingClick = true;
    compareButton.click();
    comparisonGuardReplayingClick = false;
}, true);
