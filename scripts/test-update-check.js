const assert = require('node:assert');
const {latestFromResponse} = require('../src/update-check');

const release = {
  tag_name: 'v1.5.0',
  name: 'Otome Translator 1.5.0 (Windows x64)',
  html_url: 'https://github.com/Foxiary/Otome-Translator/releases/tag/v1.5.0',
  draft: false,
  prerelease: false
};

const newer = latestFromResponse(release, '1.4.2');
assert.equal(newer.status, 'available');
assert.equal(newer.latestVersion, '1.5.0');
assert.equal(newer.currentVersion, '1.4.2');
assert.equal(newer.tag, 'v1.5.0');
assert.equal(newer.url, release.html_url);

assert.equal(latestFromResponse(release, '1.5.0').status, 'current');
assert.equal(latestFromResponse(release, 'v1.6.0').status, 'current');
assert.throws(() => latestFromResponse([{sha: 'a'.repeat(40)}], '1.5.0'));
assert.throws(() => latestFromResponse({...release, draft: true}, '1.4.2'));
assert.throws(() => latestFromResponse({...release, prerelease: true}, '1.4.2'));
assert.throws(() => latestFromResponse({...release, tag_name: 'nightly'}, '1.4.2'));

console.log('update-check assertions passed');
