const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const rowTable = { innerHTML: '' };
const element = { addEventListener() {} };
const context = vm.createContext({
    window: {},
    document: {
        addEventListener() {},
        getElementById: () => element,
        querySelector: selector => selector.includes('track-table') ? rowTable : null,
    },
    lucide: { createIcons() {} },
    console,
});
vm.runInContext(fs.readFileSync('music/static/music/js/player.js', 'utf8'), context);
vm.runInContext(`
    window.tracks = [{ id: 1, title: 'Track', artist: 'Artist', status: 'completed', bpm: 120, musical_key: 'C Minor' }];
    renderLibraryFromTracks();
`, context);
assert.match(rowTable.innerHTML, /120 BPM/);
assert.match(rowTable.innerHTML, /C Minor/);
vm.runInContext('window.tracks[0].play_count = 1; renderLibraryFromTracks();', context);
assert.match(rowTable.innerHTML, /120 BPM/);
assert.match(rowTable.innerHTML, /C Minor/);
vm.runInContext("window.tracks[0].bpm = 99; window.tracks[0].musical_key = 'D Major'; renderLibraryFromTracks();", context);
assert.match(rowTable.innerHTML, /99 BPM/);
assert.match(rowTable.innerHTML, /D Major/);
vm.runInContext("window.tracks[0].bpm = null; window.tracks[0].musical_key = null; renderLibraryFromTracks();", context);
assert.doesNotMatch(rowTable.innerHTML, /track-badge-bpm|track-badge-key/);
assert.match(vm.runInContext("trackMetadataMarkup({ musical_key: '<img>' })", context), /&lt;img&gt;/);
console.log('Track metadata regression checks passed');
