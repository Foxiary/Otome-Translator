// Works out which engine a dropped game file or folder belongs to, from file
// names and the first bytes of a few files. Nothing is unpacked: an NSP or XCI is
// read through its NCA header and RomFS index only, which takes well under a second even
// for a 5.7 GB game.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');

// Games the app has been used on. The engine comes from the files; this only
// names the game, and answers when an NSP cannot be opened without keys.
const KNOWN_TITLES = {
  '01009CF01BAC4000': {game: 'Virche Evermore -ErroR:salvation-', engine: 'otomate'},
  '01002B400E9DA000': {game: 'Collar×Malice (JP)', engine: 'otomate'},
  '010083E00F40E000': {game: 'Collar×Malice (USA)', engine: 'otomate'},
  '0100E3B00F412000': {game: 'Collar×Malice -Unlimited- (USA)', engine: 'otomate'},
  '010021D00F404000': {game: 'Code: Realize ~Guardian of Rebirth~ (USA)', engine: 'otomate'},
  '010024A014DE2000': {game: 'Code: Realize ~Guardian of Rebirth~ (CHT)', engine: 'otomate'},
  '010068501FF9A000': {game: 'UNLOGICAL', engine: 'unity'},
  '0100EA001A626000': {game: 'Matsurika no Kei -kEi- Tenmei Iniden', engine: 'rrlib'}
};

const TITLE_RX = /0100[0-9a-f]{12}/i;
const TITLE_RX_ALL = /0100[0-9a-f]{12}/gi;
const hex16 = value => value.toString(16).toUpperCase().padStart(16, '0');
// An update is the base title id + 0x800; DLC n is base + 0x1000 + n.
function baseTitle(id) {
  if (!id) return null;
  const value = BigInt(`0x${id}`);
  const low = value & 0xfffn;
  if (low === 0n || low === 0x800n) return hex16(value & ~0xfffn);
  return hex16((value & ~0xfffn) - 0x1000n);
}
function isUpdateTitle(id) { return !!id && (BigInt(`0x${id}`) & 0xfffn) === 0x800n; }
// Of several ids found in names, prefer one the app knows, then a base game.
function pickTitle(ids) {
  const unique = [...new Set(ids.filter(Boolean).map(id => id.toUpperCase()))];
  return unique.find(id => KNOWN_TITLES[id]) || unique.map(baseTitle).find(id => KNOWN_TITLES[id])
    || unique.find(id => id.endsWith('000')) || unique[0] || null;
}

// ---------------------------------------------------------------- evidence

// Each rule adds weight to an engine when a path matches; a magic number read
// from the file itself counts for more than a name.
const PATH_RULES = [
  {engine: 'rrlib', weight: 4, test: p => /(^|\/)script\.memfs$/.test(p), says: 'script.memfs'},
  {engine: 'rrlib', weight: 2, test: p => p.endsWith('.membody'), says: '.membody'},
  {engine: 'rrlib', weight: 1, test: p => /(^|\/)spec_win\//.test(p), says: 'spec_win/'},
  {engine: 'otomate', weight: 3, test: p => p.endsWith('.cpk'), says: '.cpk'},
  {engine: 'otomate', weight: 2, test: p => /(^|\/)(system|story(_0\d)?|game(_0\d)?)\.cpk$/.test(p), says: 'SYSTEM/STORY/GAME.cpk'},
  {engine: 'otomate', weight: 2, test: p => /\.(ffu|tid|gbin|gstr)$/.test(p), says: '.ffu/.tid/.gbin/.gstr'},
  {engine: 'unity', weight: 4, test: p => /(^|\/)(globalgamemanagers|data\.unity3d|unity default resources)$/.test(p), says: 'globalgamemanagers / data.unity3d'},
  // il2cpp_data/Metadata on PC builds, Data/Managed/Metadata on Switch.
  {engine: 'unity', weight: 4, test: p => /(^|\/)metadata\/global-metadata\.dat$/.test(p), says: 'global-metadata.dat'},
  {engine: 'unity', weight: 2, test: p => p.endsWith('.assets') || p.endsWith('.bundle'), says: '.assets / .bundle'}
];

// First bytes that settle a file on their own.
function magicOf(head, name = '') {
  if (!head || head.length < 4) return null;
  const ascii = head.subarray(0, 8).toString('latin1');
  if (ascii.startsWith('RSON')) {
    // The index names its own format in UTF-16 near the end; read by the caller.
    return {engine: 'rrlib', says: 'RSON'};
  }
  if (ascii.startsWith('RZ') && /\.membody$/i.test(name)) return {engine: 'rrlib', says: 'RZ'};
  if (head.length >= 8 && head.readUInt32LE(0) === 0xc0deabc1 && head.subarray(4, 8).toString('latin1') === 'KUV ') return {engine: 'rrlib', says: 'KUV'};
  if (ascii.startsWith('CPK ')) return {engine: 'otomate', says: 'CPK'};
  if (ascii.startsWith('STCM2L')) return {engine: 'otomate', says: 'STCM2L'};
  if (ascii.startsWith('TID') && /\.tid$/i.test(name)) return {engine: 'otomate', says: 'TID'};
  if (head.readUInt16LE(0) === 0x4655 && /\.ffu$/i.test(name)) return {engine: 'otomate', says: 'UF'};
  if (ascii.startsWith('GSTL') && /\.gstr$/i.test(name)) return {engine: 'otomate', says: 'GSTL'};
  if (ascii.startsWith('UnityFS')) return {engine: 'unity', says: 'UnityFS'};
  if (head.readUInt32LE(0) === 0xfab11baf) return {engine: 'unity', says: 'global-metadata'};
  return null;
}
const RRLIB_TAG = Buffer.from('rrlib/memfs', 'utf16le');

class Evidence {
  constructor() { this.score = {}; this.notes = {}; }
  add(engine, weight, note) {
    this.score[engine] = (this.score[engine] || 0) + weight;
    (this.notes[engine] ||= new Set()).add(note);
  }
  addPaths(paths) {
    for (const rule of PATH_RULES) {
      const hits = paths.filter(p => rule.test(p));
      // Many hits of one rule are one piece of evidence, not many.
      if (hits.length) this.add(rule.engine, rule.weight, `${rule.says} (${hits.length})`);
    }
  }
  addMagic(head, name) {
    const found = magicOf(head, name);
    if (!found) return;
    if (found.says === 'RSON') {
      if (head.includes(RRLIB_TAG)) this.add('rrlib', 8, `${name}: RSON rrlib/memfs`);
      else this.add('rrlib', 3, `${name}: RSON`);
      return;
    }
    this.add(found.engine, 6, `${name}: ${found.says}`);
  }
  candidates() {
    return Object.entries(this.score).sort((a, b) => b[1] - a[1])
      .map(([engine, score]) => ({engine, score, evidence: [...this.notes[engine]]}));
  }
}

function readHead(file, length = 64) {
  const fd = fs.openSync(file, 'r');
  try {
    const buffer = Buffer.alloc(length);
    const read = fs.readSync(fd, buffer, 0, length, 0);
    return buffer.subarray(0, read);
  } finally { fs.closeSync(fd); }
}

// ---------------------------------------------------------------- folders

const SKIP_DIRS = new Set(['.git', 'node_modules', '__pycache__', '.DS_Store']);
function listFolder(root, {maxDepth = 7, maxEntries = 60000} = {}) {
  const out = [];
  const walk = (dir, rel, depth) => {
    if (depth > maxDepth || out.length >= maxEntries) return;
    let entries;
    try { entries = fs.readdirSync(dir, {withFileTypes: true}); } catch { return; }
    for (const entry of entries) {
      if (out.length >= maxEntries) return;
      if (SKIP_DIRS.has(entry.name)) continue;
      const relative = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) walk(path.join(dir, entry.name), relative, depth + 1);
      else if (entry.isFile()) out.push(relative);
    }
  };
  walk(root, '', 0);
  return out;
}

// The files whose first bytes are worth reading: one of each kind is enough.
function probes(paths) {
  const picks = [];
  const take = test => { const hit = paths.find(test); if (hit && !picks.includes(hit)) picks.push(hit); };
  take(p => /(^|\/)script\.memfs$/i.test(p));
  take(p => /\.memfs$/i.test(p));
  take(p => /\.cpk$/i.test(p));
  take(p => /\.(ffu|tid|gstr)$/i.test(p));
  take(p => /global-metadata\.dat$/i.test(p));
  take(p => /(^|\/)(data\.unity3d|globalgamemanagers)$/i.test(p));
  take(p => /\.(assets|bundle)$/i.test(p));
  return picks;
}

// ---------------------------------------------------------------- NSP

function keyCandidates() {
  const home = os.homedir();
  const appData = process.env.APPDATA || path.join(home, 'AppData', 'Roaming');
  return [
    path.join(home, '.switch', 'prod.keys'),
    path.join(home, 'Library', 'Application Support', 'Ryujinx', 'system', 'prod.keys'),
    path.join(home, '.config', 'Ryujinx', 'system', 'prod.keys'),
    path.join(appData, 'Ryujinx', 'system', 'prod.keys')
  ];
}
function findKeys(preferred, searchDefaults = true) {
  for (const file of [preferred, ...(searchDefaults ? keyCandidates() : [])].filter(Boolean)) {
    try { if (fs.statSync(file).isFile()) return file; } catch {}
  }
  return null;
}
function loadKeys(file) {
  const keys = {};
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([a-z0-9_]+)\s*=\s*([0-9a-f]+)\s*$/i);
    if (match) keys[match[1].toLowerCase()] = Buffer.from(match[2], 'hex');
  }
  return keys;
}

function readAt(fd, offset, length) {
  const buffer = Buffer.alloc(length);
  const read = fs.readSync(fd, buffer, 0, length, offset);
  return buffer.subarray(0, read);
}
function pfs0(fd, base = 0) {
  const head = readAt(fd, base, 16);
  if (head.subarray(0, 4).toString('latin1') !== 'PFS0') throw new Error('not an NSP (no PFS0 header)');
  const count = head.readUInt32LE(4);
  const stringSize = head.readUInt32LE(8);
  const table = readAt(fd, base + 16, 0x18 * count + stringSize);
  const strings = table.subarray(0x18 * count);
  const data = base + 16 + 0x18 * count + stringSize;
  const files = [];
  for (let i = 0; i < count; i++) {
    const offset = Number(table.readBigUInt64LE(0x18 * i));
    const size = Number(table.readBigUInt64LE(0x18 * i + 8));
    const nameOffset = table.readUInt32LE(0x18 * i + 16);
    const name = strings.subarray(nameOffset, strings.indexOf(0, nameOffset)).toString('utf8');
    files.push({name, offset: data + offset, size});
  }
  return files;
}
function aes(mode, key, iv, data) {
  const decipher = crypto.createDecipheriv(mode, key, iv);
  decipher.setAutoPadding(false);
  return Buffer.concat([decipher.update(data), decipher.final()]);
}
// The NCA header is AES-XTS in 0x200 sectors with a BIG-endian sector number as
// the tweak. Electron's BoringSSL has no XTS cipher, so it is built here from
// AES-ECB: T = E(key2, tweak); each block is D(key1, C ^ T) ^ T, then T *= x
// in GF(2^128), little-endian.
function xtsDecryptSector(key, sector, data) {
  const tweak = Buffer.alloc(16);
  tweak.writeBigUInt64BE(BigInt(sector), 8);
  const encrypt = crypto.createCipheriv('aes-128-ecb', key.subarray(16, 32), null);
  encrypt.setAutoPadding(false);
  let t = Buffer.concat([encrypt.update(tweak), encrypt.final()]);
  const tweaks = Buffer.alloc(data.length);
  for (let block = 0; block < data.length / 16; block++) {
    t.copy(tweaks, block * 16);
    const next = Buffer.alloc(16);
    let carry = 0;
    for (let i = 0; i < 16; i++) {
      next[i] = ((t[i] << 1) | carry) & 0xff;
      carry = t[i] >> 7;
    }
    if (carry) next[0] ^= 0x87;
    t = next;
  }
  const masked = Buffer.alloc(data.length);
  for (let i = 0; i < data.length; i++) masked[i] = data[i] ^ tweaks[i];
  const plain = aes('aes-128-ecb', key.subarray(0, 16), null, masked);
  for (let i = 0; i < plain.length; i++) plain[i] ^= tweaks[i];
  return plain;
}
function decryptHeader(encrypted, headerKey) {
  const parts = [];
  for (let sector = 0; sector < 6; sector++) parts.push(xtsDecryptSector(headerKey, sector, encrypted.subarray(sector * 0x200, (sector + 1) * 0x200)));
  return Buffer.concat(parts);
}

class Nca {
  constructor(fd, offset, keys, ticket) {
    this.fd = fd; this.offset = offset;
    if (!keys.header_key) throw new Error('prod.keys has no header_key');
    const header = decryptHeader(readAt(fd, offset, 0xc00), keys.header_key);
    const magic = header.subarray(0x200, 0x204).toString('latin1');
    if (magic !== 'NCA3' && magic !== 'NCA2') throw new Error('NCA header did not decrypt (wrong keys?)');
    this.header = header;
    this.contentType = header[0x205];
    this.titleId = header.readBigUInt64LE(0x210).toString(16).toUpperCase().padStart(16, '0');
    const generation = Math.max(header[0x206], header[0x220]);
    const revision = (Math.max(generation - 1, 0)).toString(16).padStart(2, '0');
    const rights = header.subarray(0x230, 0x240);
    if (rights.some(byte => byte)) {
      if (!ticket) throw new Error('the NSP has no ticket for its title key');
      const kek = keys[`titlekek_${revision}`];
      if (!kek) throw new Error(`prod.keys has no titlekek_${revision}`);
      this.key = aes('aes-128-ecb', kek, null, ticket.subarray(0x180, 0x190));
    } else {
      const index = ['application', 'ocean', 'system'][header[0x207]] || 'application';
      const kak = keys[`key_area_key_${index}_${revision}`];
      if (!kak) throw new Error(`prod.keys has no key_area_key_${index}_${revision}`);
      this.key = aes('aes-128-ecb', kak, null, header.subarray(0x300, 0x340)).subarray(0x20, 0x30);
    }
    this.sections = [];
    for (let i = 0; i < 4; i++) {
      const start = header.readUInt32LE(0x240 + 0x10 * i);
      const end = header.readUInt32LE(0x244 + 0x10 * i);
      if (!end) continue;
      const fs_ = header.subarray(0x400 + 0x200 * i, 0x600 + 0x200 * i);
      this.sections.push({index: i, start: start * 0x200, end: end * 0x200, fsHeader: fs_, fsType: fs_[2], cryptType: fs_[4]});
    }
  }
  // CTR counter: the section's 8 counter bytes reversed, then the offset inside
  // the NCA (not the NSP) in 16-byte units.
  read(section, relative, length) {
    const absolute = section.start + relative;
    const aligned = absolute - (absolute % 16);
    const pad = absolute - aligned;
    const size = Math.ceil((pad + length) / 16) * 16;
    const data = readAt(this.fd, this.offset + aligned, size);
    const counter = Buffer.alloc(16);
    Buffer.from(section.fsHeader.subarray(0x140, 0x148)).reverse().copy(counter, 0);
    counter.writeBigUInt64BE(BigInt(aligned / 16), 8);
    return aes('aes-128-ctr', this.key, counter, data).subarray(pad, pad + length);
  }
}

function romfsFiles(nca, section) {
  const fh = section.fsHeader;
  if (fh.subarray(8, 12).toString('latin1') !== 'IVFC') throw new Error('RomFS section has no IVFC header');
  const base = Number(fh.readBigUInt64LE(0x18 + 0x18 * 5));
  const header = nca.read(section, base, 0x50);
  const v = i => Number(header.readBigUInt64LE(i * 8));
  const dirMeta = nca.read(section, base + v(3), v(4));
  const fileMeta = nca.read(section, base + v(7), v(8));
  const dataBase = base + v(9);
  const dirName = offset => {
    const parent = dirMeta.readUInt32LE(offset);
    const length = dirMeta.readUInt32LE(offset + 20);
    return {parent, name: dirMeta.subarray(offset + 24, offset + 24 + length).toString('utf8')};
  };
  const dirPath = offset => {
    const parts = [];
    for (let guard = 0; offset !== 0 && guard < 64; guard++) { const d = dirName(offset); parts.push(d.name); offset = d.parent; }
    return parts.reverse().join('/');
  };
  const files = [];
  for (let offset = 0; offset + 32 <= fileMeta.length;) {
    const parent = fileMeta.readUInt32LE(offset);
    const dataOffset = Number(fileMeta.readBigUInt64LE(offset + 8));
    const size = Number(fileMeta.readBigUInt64LE(offset + 16));
    const length = fileMeta.readUInt32LE(offset + 28);
    const name = fileMeta.subarray(offset + 32, offset + 32 + length).toString('utf8');
    const dir = dirPath(parent);
    files.push({path: dir ? `${dir}/${name}` : name, offset: dataBase + dataOffset, size});
    offset += 32 + Math.ceil(length / 4) * 4;
  }
  return files;
}

// HFS0, the partition format of a game card: like PFS0 with 0x40-byte entries
// that carry a hash of each file's start.
function hfs0(fd, base) {
  const head = readAt(fd, base, 16);
  if (head.subarray(0, 4).toString('latin1') !== 'HFS0') throw new Error('not an HFS0 partition');
  const count = head.readUInt32LE(4);
  const stringSize = head.readUInt32LE(8);
  const table = readAt(fd, base + 16, 0x40 * count + stringSize);
  const strings = table.subarray(0x40 * count);
  const data = base + 16 + 0x40 * count + stringSize;
  const files = [];
  for (let i = 0; i < count; i++) {
    const nameOffset = table.readUInt32LE(0x40 * i + 16);
    files.push({name: strings.subarray(nameOffset, strings.indexOf(0, nameOffset)).toString('utf8'),
      offset: data + Number(table.readBigUInt64LE(0x40 * i)), size: Number(table.readBigUInt64LE(0x40 * i + 8))});
  }
  return files;
}
// An XCI (game card dump): 'HEAD' at 0x100, the root HFS0 at the offset in 0x130,
// and the game's NCAs in its "secure" partition, itself an HFS0.
function xciEntries(fd) {
  const head = readAt(fd, 0x100, 0x40);
  const rootOffset = Number(head.readBigUInt64LE(0x30));
  const secure = hfs0(fd, rootOffset).find(entry => entry.name === 'secure');
  if (!secure) throw new Error('the XCI has no secure partition');
  return hfs0(fd, secure.offset);
}
// The files of an NSP (PFS0 at 0) or an XCI ('HEAD' at 0x100).
function packageEntries(fd) {
  const head = readAt(fd, 0, 0x104);
  if (head.subarray(0, 4).toString('latin1') === 'PFS0') return pfs0(fd);
  if (head.subarray(0x100, 0x104).toString('latin1') === 'HEAD') return xciEntries(fd);
  throw new Error('not an NSP or XCI');
}

// The game's program NCA. A card can carry an update next to the base game; both
// are programs, and the base game is the one whose RomFS reads on its own.
function baseProgram(fd, entries, keys, ticket) {
  const ncas = entries.filter(entry => entry.name.endsWith('.nca') && !entry.name.endsWith('.cnmt.nca'))
    .sort((a, b) => b.size - a.size);
  const programs = [];
  for (const entry of ncas) {
    const nca = new Nca(fd, entry.offset, keys, ticket);
    if (nca.contentType === 0) programs.push(nca);
  }
  if (!programs.length) return null;
  const romfsOf = nca => nca.sections.find(section => section.fsType === 0);
  const isBase = nca => !!romfsOf(nca) && romfsOf(nca).cryptType !== 4 && !isUpdateTitle(nca.titleId);
  const program = programs.find(isBase) || programs[0];
  return {program, romfs: romfsOf(program), exefs: program.sections.find(section => section.fsType === 1), base: isBase(program)};
}

function inspectPackage(file, options = {}) {
  const fd = fs.openSync(file, 'r');
  try {
    const entries = packageEntries(fd);
    const ticketEntry = entries.find(entry => entry.name.endsWith('.tik'));
    // The ticket is named after the rights id: title id + key generation.
    const titleFromName = (ticketEntry?.name.match(TITLE_RX) || entries.map(e => e.name.match(TITLE_RX)).find(Boolean) || [])[0];
    const result = {titleId: titleFromName ? titleFromName.toUpperCase() : null, paths: null, heads: {}, problem: null, update: false};
    const keysFile = findKeys(options.keys, options.defaultKeys !== false);
    if (!keysFile) { result.problem = 'keys'; return result; }
    const keys = loadKeys(keysFile);
    result.keys = keysFile;
    const ticket = ticketEntry ? readAt(fd, ticketEntry.offset, ticketEntry.size) : null;
    const picked = baseProgram(fd, entries, keys, ticket);
    if (!picked) { result.problem = 'no-program'; return result; }
    const {program, romfs, base} = picked;
    result.titleId = program.titleId;
    if (!romfs) { result.problem = 'no-romfs'; return result; }
    // An update carries a patch RomFS (BKTR) that only reads against the base game.
    if (!base) { result.update = true; result.problem = 'update'; return result; }
    const files = romfsFiles(program, romfs);
    result.paths = files.map(f => f.path);
    for (const rel of probes(result.paths.map(p => p.toLowerCase()))) {
      const entry = files.find(f => f.path.toLowerCase() === rel);
      // The whole index for RSON (it is small and names itself at the end), 64 bytes otherwise.
      const length = /\.memfs$/i.test(rel) ? Math.min(entry.size, 1 << 20) : Math.min(entry.size, 64);
      result.heads[entry.path] = program.read(romfs, entry.offset, length);
    }
    return result;
  } finally { fs.closeSync(fd); }
}

// ---------------------------------------------------------------- entry point

function describeTitle(titleId) {
  if (!titleId) return {titleId: null, game: null, knownEngine: null};
  const known = KNOWN_TITLES[titleId] || KNOWN_TITLES[baseTitle(titleId)];
  return {titleId, game: known?.game || null, knownEngine: known?.engine || null};
}

function finish(kind, input, evidence, extra = {}) {
  const candidates = evidence.candidates();
  const title = describeTitle(extra.titleId);
  // A title the app knows decides only when the files said nothing.
  if (!candidates.length && title.knownEngine) {
    candidates.push({engine: title.knownEngine, score: 1, evidence: [`title ${title.titleId}`]});
  }
  const top = candidates[0];
  const confident = !!top && top.score >= 4 && (!candidates[1] || top.score >= candidates[1].score * 2);
  return {input, kind, engine: top?.engine || null, confident, candidates, ...title,
    problem: extra.problem || null, update: !!extra.update, fileCount: extra.fileCount ?? null};
}

function detect(input, options = {}) {
  let stat;
  try { stat = fs.statSync(input); } catch { return finish('missing', input, new Evidence(), {problem: 'missing'}); }
  const evidence = new Evidence();
  const titleInPath = pickTitle(input.match(TITLE_RX_ALL) || []);

  if (stat.isDirectory()) {
    const paths = listFolder(input, options).map(p => p.replace(/\\/g, '/'));
    const lower = paths.map(p => p.toLowerCase());
    evidence.addPaths(lower);
    for (const rel of probes(lower)) {
      const original = paths[lower.indexOf(rel)];
      const full = path.join(input, original);
      const length = /\.memfs$/i.test(rel) ? Math.min(fs.statSync(full).size, 1 << 20) : 64;
      try { evidence.addMagic(readHead(full, length), original); } catch {}
    }
    const titleInside = pickTitle(lower.flatMap(p => p.match(TITLE_RX_ALL) || []));
    return finish('folder', input, evidence, {titleId: titleInPath || titleInside, fileCount: paths.length});
  }

  const container = (input.match(/\.(nsp|xci)$/i) || [])[1]?.toLowerCase();
  if (container) {
    let nsp;
    try { nsp = inspectPackage(input, options); }
    catch (error) { return finish(container, input, evidence, {titleId: titleInPath, problem: `${container}: ${error.message}`}); }
    if (nsp.paths) {
      const lower = nsp.paths.map(p => p.toLowerCase());
      evidence.addPaths(lower);
      for (const [name, head] of Object.entries(nsp.heads)) evidence.addMagic(head, name);
    }
    return finish(container, input, evidence, {titleId: nsp.titleId || titleInPath, problem: nsp.problem,
      update: nsp.update, fileCount: nsp.paths ? nsp.paths.length : null});
  }
  if (/\.(nsz|xcz)$/i.test(input)) {
    return finish('file', input, evidence, {titleId: titleInPath, problem: 'unsupported-container'});
  }

  const name = path.basename(input);
  const length = /\.memfs$/i.test(name) ? Math.min(stat.size, 1 << 20) : 64;
  try { evidence.addMagic(readHead(input, length), name); } catch {}
  evidence.addPaths([name.toLowerCase()]);
  return finish('file', input, evidence, {titleId: titleInPath});
}

module.exports = {detect, magicOf, listFolder, baseTitle, isUpdateTitle, KNOWN_TITLES, findKeys, inspectPackage,
  // For game-extract.js, which reads the same containers.
  internals: {packageEntries, baseProgram, romfsFiles, loadKeys, readAt, TITLE_RX}};
