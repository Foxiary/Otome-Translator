const https = require('node:https');

const API_URL = 'https://api.github.com/repos/Foxiary/Otome-Translator/releases/latest';

function parseVersion(value) {
  const match = String(value || '').match(/(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return match.slice(1, 4).map(Number);
}

function compareVersions(left, right) {
  for (let index = 0; index < 3; index++) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return 0;
}

function latestFromResponse(release, currentVersion) {
  const current = parseVersion(currentVersion);
  const latest = parseVersion(release?.tag_name);
  if (!current || !latest || release.draft || release.prerelease) {
    throw new Error('GitHub returned an invalid release.');
  }
  const tag = String(release.tag_name);
  const newer = compareVersions(latest, current) > 0;
  return {
    status: newer ? 'available' : 'current',
    currentVersion: current.join('.'),
    latestVersion: latest.join('.'),
    tag,
    title: String(release.name || tag).slice(0, 160),
    url: typeof release.html_url === 'string' && release.html_url.startsWith('https://github.com/')
      ? release.html_url
      : `https://github.com/Foxiary/Otome-Translator/releases/tag/${encodeURIComponent(tag)}`,
    checkedAt: new Date().toISOString()
  };
}

function fetchLatest() {
  return new Promise((resolve, reject) => {
    const request = https.get(API_URL, {
      headers: {'Accept': 'application/vnd.github+json', 'User-Agent': 'Otome-Translator-Update-Check'}
    }, response => {
      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`GitHub returned HTTP ${response.statusCode}.`));
        return;
      }
      let body = '';
      response.setEncoding('utf8');
      response.on('data', chunk => {
        body += chunk;
        if (body.length > 256_000) request.destroy(new Error('Update response is too large.'));
      });
      response.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch { reject(new Error('GitHub returned unreadable update data.')); }
      });
      response.on('error', reject);
    });
    request.setTimeout(10_000, () => request.destroy(new Error('Update check timed out.')));
    request.on('error', reject);
  });
}

async function checkForUpdate(currentVersion, requestLatest = fetchLatest) {
  return latestFromResponse(await requestLatest(), currentVersion);
}

module.exports = {checkForUpdate, latestFromResponse};
