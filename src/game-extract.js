// Takes a whole game out of an .nsp or .xci: every RomFS file and the ExeFS
// (main, sdk, ...), decrypted in 8 MB pieces so the window stays responsive,
// with progress and a way to stop. Reads the same containers as detect-engine.js.
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const {findKeys, internals} = require('./detect-engine');
const {packageEntries, baseProgram, romfsFiles, loadKeys, readAt} = internals;

const CHUNK = 8 << 20;

class ExtractError extends Error {
  constructor(code, message, extra = {}) { super(message); this.code = code; Object.assign(this, extra); }
}

// The ExeFS is a PFS0 inside its section, behind a SHA-256 hash layer: the
// superblock's region 1 (at 0x40 of the section header) is where it starts.
function exefsFiles(program, section) {
  const base = Number(section.fsHeader.readBigUInt64LE(0x40));
  const head = program.read(section, base, 16);
  if (head.subarray(0, 4).toString('latin1') !== 'PFS0') throw new ExtractError('format', 'the ExeFS section has no PFS0 header');
  const count = head.readUInt32LE(4);
  const stringSize = head.readUInt32LE(8);
  const table = program.read(section, base + 16, 0x18 * count + stringSize);
  const strings = table.subarray(0x18 * count);
  const data = base + 16 + 0x18 * count + stringSize;
  const files = [];
  for (let i = 0; i < count; i++) {
    const nameOffset = table.readUInt32LE(0x18 * i + 16);
    files.push({path: strings.subarray(nameOffset, strings.indexOf(0, nameOffset)).toString('utf8'),
      offset: data + Number(table.readBigUInt64LE(0x18 * i)), size: Number(table.readBigUInt64LE(0x18 * i + 8))});
  }
  return files;
}

// Where a game file lands, refusing any name that would leave the folder.
function inside(folder, relative) {
  const target = path.resolve(folder, ...relative.split('/'));
  if (target !== folder && !target.startsWith(path.resolve(folder) + path.sep)) {
    throw new ExtractError('format', `refused a file outside the target folder: ${relative}`);
  }
  return target;
}

function freeSpace(folder) {
  let probe = path.resolve(folder);
  while (!fs.existsSync(probe) && path.dirname(probe) !== probe) probe = path.dirname(probe);
  try { const stats = fs.statfsSync(probe); return stats.bavail * stats.bsize; } catch { return Infinity; }
}

async function copyOut(program, section, file, target, onBytes, isCancelled) {
  await fsp.mkdir(path.dirname(target), {recursive: true});
  const handle = await fsp.open(target, 'w');
  try {
    for (let done = 0; done < file.size;) {
      if (isCancelled()) throw new ExtractError('cancelled', 'stopped');
      const length = Math.min(CHUNK, file.size - done);
      const data = program.read(section, file.offset + done, length);
      await handle.write(data, 0, data.length);
      done += length;
      onBytes(length);
    }
  } finally { await handle.close(); }
}

// options: romfsDir (required), exefsDir, keys, defaultKeys, onProgress({done,
// total, files, count, current}), isCancelled(). Resolves with a summary;
// rejects with an ExtractError whose code is keys | no-program | no-romfs |
// update | space | cancelled | format.
async function extractGame(file, options) {
  const {romfsDir, exefsDir, onProgress = () => {}, isCancelled = () => false} = options;
  const keysFile = findKeys(options.keys, options.defaultKeys !== false);
  if (!keysFile) throw new ExtractError('keys', 'prod.keys was not found');
  const fd = fs.openSync(file, 'r');
  try {
    const entries = packageEntries(fd);
    const ticketEntry = entries.find(entry => entry.name.endsWith('.tik'));
    const ticket = ticketEntry ? readAt(fd, ticketEntry.offset, ticketEntry.size) : null;
    const picked = baseProgram(fd, entries, loadKeys(keysFile), ticket);
    if (!picked) throw new ExtractError('no-program', 'the file holds no game program');
    if (!picked.romfs) throw new ExtractError('no-romfs', 'the game program has no RomFS');
    if (!picked.base) throw new ExtractError('update', 'this is an update; use the base game');
    const {program} = picked;
    const jobs = romfsFiles(program, picked.romfs)
      .map(entry => ({section: picked.romfs, entry, target: inside(romfsDir, entry.path)}));
    if (exefsDir && picked.exefs) {
      for (const entry of exefsFiles(program, picked.exefs)) jobs.push({section: picked.exefs, entry, target: inside(exefsDir, entry.path)});
    }
    const total = jobs.reduce((sum, job) => sum + job.entry.size, 0);
    const available = freeSpace(romfsDir);
    if (available < total * 1.02) {
      const gb = bytes => (bytes / 1e9).toFixed(1);
      throw new ExtractError('space', `${gb(total)} GB needed, ${gb(available)} GB free`, {needed: total, available});
    }

    let done = 0, last = 0;
    const report = (index, force = false) => {
      const now = Date.now();
      if (!force && now - last < 150) return;
      last = now;
      onProgress({done, total, files: index, count: jobs.length, current: jobs[Math.min(index, jobs.length - 1)]?.entry.path || ''});
    };
    for (let index = 0; index < jobs.length; index++) {
      const job = jobs[index];
      await copyOut(program, job.section, job.entry, job.target, bytes => { done += bytes; report(index); }, isCancelled);
      report(index + 1);
      // Let the window and its messages through between files, small ones too.
      if (index % 64 === 63) await new Promise(resolve => setImmediate(resolve));
    }
    report(jobs.length, true);
    return {titleId: program.titleId, files: jobs.length, bytes: total, romfsDir, exefsDir: picked.exefs ? exefsDir : null};
  } finally { fs.closeSync(fd); }
}

module.exports = {extractGame, ExtractError};
