// Copies an engine's files into a project folder and keeps them current. The
// tools run from that copy, so a stale one breaks a tool that is fine in the
// app: a project kept rrlib's old patch.py beside a new sprite.py, which
// imports a function the old file lacks.
//
// A file the project lacks is copied. A file it has is replaced only while it
// is untouched, which is either of
//   - it matches an earlier version the engine shipped (`earlier`, written by
//     scripts/update-engine-hashes.js), or
//   - it is byte for byte what the app wrote there last time (`record`, kept
//     per project folder and engine in the app's data folder). This covers a
//     copy taken from a build no release ever had, such as a working tree.
// A file the user edited matches neither and is left alone.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const SKIP = new Set(['__pycache__', '.git']);

function sha256(data) { return crypto.createHash('sha256').update(data).digest('hex'); }
// Earlier versions are hashed as LF text, so a CRLF checkout of one must match too.
function lfHash(data) { return sha256(Buffer.from(data.toString('latin1').split('\r\n').join('\n'), 'latin1')); }

// entries: [[source path, path relative to the project]]; earlier: {relative: hash or [hashes]};
// record: {relative: hash} from the last run. Returns the new record and what happened.
function syncEngineFiles(folder, entries, earlier = {}, record = {}) {
  const result = {record: {...record}, added: [], updated: [], kept: []};
  const visit = (source, relative) => {
    if (!fs.existsSync(source)) return;
    const target = path.join(folder, relative);
    if (fs.statSync(source).isDirectory()) {
      if (SKIP.has(path.basename(source))) return;
      fs.mkdirSync(target, {recursive: true});
      for (const name of fs.readdirSync(source)) visit(path.join(source, name), `${relative}/${name}`);
      return;
    }
    const data = fs.readFileSync(source);
    const hash = sha256(data);
    if (!fs.existsSync(target)) {
      fs.mkdirSync(path.dirname(target), {recursive: true});
      fs.copyFileSync(source, target);
      result.record[relative] = hash;
      result.added.push(relative);
      return;
    }
    const present = fs.readFileSync(target);
    const presentHash = sha256(present);
    if (presentHash === hash) { result.record[relative] = hash; return; }
    const known = [].concat(earlier[relative] || []);
    if (record[relative] === presentHash || known.includes(presentHash) || known.includes(lfHash(present))) {
      fs.copyFileSync(source, target);
      result.record[relative] = hash;
      result.updated.push(relative);
    } else {
      result.kept.push(relative);
    }
  };
  fs.mkdirSync(folder, {recursive: true});
  for (const [source, relative] of entries) visit(source, relative);
  return result;
}

module.exports = {syncEngineFiles, sha256, lfHash};
