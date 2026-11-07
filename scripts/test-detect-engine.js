// Engine detection on synthetic folders, files and an NSP built here with random
// keys, so the decryption path is covered without game data or real keys.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {detect, magicOf, baseTitle, isUpdateTitle} = require('../src/detect-engine');
const {extractGame} = require('../src/game-extract');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'otm-detect-'));
function put(relative, data) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, data);
  return file;
}
// A minimal index: the magic, then the format name in UTF-16 as the engine writes it.
const MEMFS = Buffer.concat([Buffer.from('RSON'), Buffer.alloc(12), Buffer.from('rrlib/memfs', 'utf16le')]);

(async () => {
try {
  // Magic numbers.
  assert.equal(magicOf(Buffer.from('CPK \0\0\0\0'), 'SYSTEM.cpk').engine, 'otomate');
  assert.equal(magicOf(Buffer.from('UnityFS\0'), 'a.bundle').engine, 'unity');
  assert.equal(magicOf(MEMFS, 'script.memfs').engine, 'rrlib');
  const kuv = Buffer.alloc(16); kuv.writeUInt32LE(0xc0deabc1, 0); kuv.write('KUV ', 4, 'latin1');
  assert.equal(magicOf(kuv, 'x.tat').engine, 'rrlib');
  const meta = Buffer.alloc(8); meta.writeUInt32LE(0xfab11baf, 0);
  assert.equal(magicOf(meta, 'global-metadata.dat').engine, 'unity');
  assert.equal(magicOf(Buffer.from('hello world'), 'readme.txt'), null);

  // Title ids: updates and DLC lead back to the base game.
  assert.equal(baseTitle('0100EA001A626800'), '0100EA001A626000');
  assert.equal(baseTitle('010068501FF9B001'), '010068501FF9A000');
  assert.ok(isUpdateTitle('010083E00F40E800'));
  assert.ok(!isUpdateTitle('010083E00F40E000'));

  // Folders laid out like each engine's game files or mods.
  put('rr/matsurika0100ea001a626000/romfs/common/script.memfs', MEMFS);
  put('rr/matsurika0100ea001a626000/romfs/common/script.membody', Buffer.from('RZ\0\0\0\x10'));
  let r = detect(path.join(root, 'rr'));
  assert.equal(r.engine, 'rrlib'); assert.ok(r.confident);
  assert.equal(r.titleId, '0100EA001A626000'); assert.match(r.game, /Matsurika/);
  assert.ok(r.candidates[0].evidence.some(note => note.includes('rrlib/memfs')));

  put('oto/romfs/SYSTEM.cpk', Buffer.concat([Buffer.from('CPK '), Buffer.alloc(60)]));
  put('oto/romfs/STORY.cpk', Buffer.concat([Buffer.from('CPK '), Buffer.alloc(60)]));
  r = detect(path.join(root, 'oto'));
  assert.equal(r.engine, 'otomate'); assert.ok(r.confident); assert.equal(r.titleId, null);

  put('uni/romfs/Data/data.unity3d', Buffer.concat([Buffer.from('UnityFS'), Buffer.alloc(57)]));
  put('uni/romfs/Data/Managed/Metadata/global-metadata.dat', meta);
  r = detect(path.join(root, 'uni'));
  assert.equal(r.engine, 'unity'); assert.ok(r.confident);

  put('none/readme.txt', 'nothing here');
  r = detect(path.join(root, 'none'));
  assert.equal(r.engine, null); assert.equal(r.candidates.length, 0);

  // A single file, and a name the app knows without any file evidence.
  r = detect(path.join(root, 'rr/matsurika0100ea001a626000/romfs/common/script.memfs'));
  assert.equal(r.kind, 'file'); assert.equal(r.engine, 'rrlib');
  r = detect(path.join(root, 'missing.nsp'));
  assert.equal(r.problem, 'missing'); assert.equal(r.engine, null);
  assert.equal(detect(put('game.nsz', 'x')).problem, 'unsupported-container');

  // ---------------------------------------------------------------- NSP
  const titleId = '0100EA001A626000';
  const headerKey = crypto.randomBytes(32);
  const keyAreaKey = crypto.randomBytes(16);
  const sectionKey = crypto.randomBytes(16);
  const counterSeed = crypto.randomBytes(8);
  const keysFile = put('prod.keys', `header_key = ${headerKey.toString('hex')}\nkey_area_key_application_00 = ${keyAreaKey.toString('hex')}\n`);

  // RomFS: a root dir, dir "common", file "common/script.memfs".
  const align4 = n => Math.ceil(n / 4) * 4;
  const dirMeta = Buffer.alloc(24 + 24 + align4(6));
  dirMeta.writeUInt32LE(0, 0); dirMeta.writeUInt32LE(0xffffffff, 4); dirMeta.writeUInt32LE(24, 8);
  dirMeta.writeUInt32LE(0xffffffff, 12); dirMeta.writeUInt32LE(0xffffffff, 16); dirMeta.writeUInt32LE(0, 20);
  dirMeta.writeUInt32LE(0, 24); dirMeta.writeUInt32LE(0xffffffff, 28); dirMeta.writeUInt32LE(0xffffffff, 32);
  dirMeta.writeUInt32LE(0, 36); dirMeta.writeUInt32LE(0xffffffff, 40); dirMeta.writeUInt32LE(6, 44);
  dirMeta.write('common', 48, 'utf8');
  const fileName = 'script.memfs';
  const fileMeta = Buffer.alloc(32 + align4(fileName.length));
  fileMeta.writeUInt32LE(24, 0); fileMeta.writeUInt32LE(0xffffffff, 4);
  fileMeta.writeBigUInt64LE(0n, 8); fileMeta.writeBigUInt64LE(BigInt(MEMFS.length), 16);
  fileMeta.writeUInt32LE(0xffffffff, 24); fileMeta.writeUInt32LE(fileName.length, 28);
  fileMeta.write(fileName, 32, 'utf8');
  const romfsHeader = Buffer.alloc(0x50);
  const dirMetaAt = 0x50, fileMetaAt = dirMetaAt + dirMeta.length, dataAt = align4(fileMetaAt + fileMeta.length);
  romfsHeader.writeBigUInt64LE(0x50n, 0);
  romfsHeader.writeBigUInt64LE(BigInt(dirMetaAt), 24); romfsHeader.writeBigUInt64LE(BigInt(dirMeta.length), 32);
  romfsHeader.writeBigUInt64LE(BigInt(fileMetaAt), 56); romfsHeader.writeBigUInt64LE(BigInt(fileMeta.length), 64);
  romfsHeader.writeBigUInt64LE(BigInt(dataAt), 72);
  let romfs = Buffer.concat([romfsHeader, dirMeta, fileMeta]);
  romfs = Buffer.concat([romfs, Buffer.alloc(dataAt - romfs.length), MEMFS]);
  romfs = Buffer.concat([romfs, Buffer.alloc(Math.ceil(romfs.length / 0x200) * 0x200 - romfs.length)]);

  // NCA header in plain text, then encrypted.
  const header = Buffer.alloc(0xc00);
  header.write('NCA3', 0x200, 'latin1');
  header[0x205] = 0;                                   // program
  header.writeBigUInt64LE(BigInt(`0x${titleId}`), 0x210);
  header.writeUInt32LE(6, 0x240);                      // section 0 starts right after the header
  header.writeUInt32LE(6 + romfs.length / 0x200, 0x244);
  const keyArea = Buffer.alloc(0x40); sectionKey.copy(keyArea, 0x20);
  const ecb = crypto.createCipheriv('aes-128-ecb', keyAreaKey, null); ecb.setAutoPadding(false);
  Buffer.concat([ecb.update(keyArea), ecb.final()]).copy(header, 0x300);
  const fsHeader = header.subarray(0x400, 0x600);
  fsHeader[2] = 0; fsHeader[4] = 3; fsHeader.write('IVFC', 8, 'latin1');
  fsHeader.writeBigUInt64LE(0n, 0x18 + 0x18 * 5);      // level 6 (the RomFS) at the start of the section
  counterSeed.copy(fsHeader, 0x140);
  const encHeader = [];
  for (let sector = 0; sector < 6; sector++) {
    const tweak = Buffer.alloc(16); tweak.writeBigUInt64BE(BigInt(sector), 8);
    const xts = crypto.createCipheriv('aes-128-xts', headerKey, tweak); xts.setAutoPadding(false);
    encHeader.push(xts.update(header.subarray(sector * 0x200, (sector + 1) * 0x200)), xts.final());
  }
  const counter = Buffer.alloc(16); Buffer.from(counterSeed).reverse().copy(counter, 0);
  counter.writeBigUInt64BE(BigInt(0xc00 / 16), 8);
  const ctr = crypto.createCipheriv('aes-128-ctr', sectionKey, counter);
  const nca = Buffer.concat([...encHeader, ctr.update(romfs), ctr.final()]);

  // PFS0 holding the NCA and a ticket named after the rights id.
  const names = ['0123456789abcdef0123456789abcdef.nca', `${titleId.toLowerCase()}0000000000000000.tik`];
  const blobs = [nca, Buffer.alloc(0x2c0)];
  const strings = Buffer.from(names.join('\0') + '\0', 'utf8');
  const table = Buffer.alloc(0x18 * names.length);
  let offset = 0, nameOffset = 0;
  names.forEach((name, i) => {
    table.writeBigUInt64LE(BigInt(offset), 0x18 * i); table.writeBigUInt64LE(BigInt(blobs[i].length), 0x18 * i + 8);
    table.writeUInt32LE(nameOffset, 0x18 * i + 16);
    offset += blobs[i].length; nameOffset += Buffer.byteLength(name) + 1;
  });
  const pfsHeader = Buffer.alloc(16); pfsHeader.write('PFS0', 0, 'latin1');
  pfsHeader.writeUInt32LE(names.length, 4); pfsHeader.writeUInt32LE(strings.length, 8);
  const nsp = put('game.nsp', Buffer.concat([pfsHeader, table, strings, ...blobs]));

  r = detect(nsp, {keys: keysFile, defaultKeys: false});
  assert.equal(r.kind, 'nsp'); assert.equal(r.problem, null);
  assert.equal(r.engine, 'rrlib'); assert.ok(r.confident);
  assert.equal(r.titleId, titleId); assert.equal(r.fileCount, 1);
  assert.ok(r.candidates[0].evidence.some(note => note.includes('rrlib/memfs')), 'the index was decrypted and read');

  // Without keys the ticket name still names the game, but nothing is confident.
  r = detect(nsp, {keys: path.join(root, 'nope.keys'), defaultKeys: false});
  assert.equal(r.problem, 'keys'); assert.equal(r.titleId, titleId);
  assert.equal(r.engine, 'rrlib'); assert.ok(!r.confident);

  // Wrong keys are reported, not mistaken for a game.
  const wrong = put('wrong.keys', `header_key = ${crypto.randomBytes(32).toString('hex')}\n`);
  r = detect(nsp, {keys: wrong, defaultKeys: false});
  assert.match(r.problem, /decrypt/);

  // ---------------------------------------------------------------- XCI
  // The same NCA on a game card: 'HEAD' at 0x100, a root HFS0 holding update,
  // normal and secure, and the NCA inside secure. No ticket, as on a real card.
  function hfs0Image(entryNames, entryBlobs) {
    const hfsStrings = Buffer.from(entryNames.map(name => `${name}\0`).join(''), 'utf8');
    const hfsTable = Buffer.alloc(0x40 * entryNames.length);
    let at = 0, nameAt = 0;
    entryNames.forEach((name, i) => {
      hfsTable.writeBigUInt64LE(BigInt(at), 0x40 * i); hfsTable.writeBigUInt64LE(BigInt(entryBlobs[i].length), 0x40 * i + 8);
      hfsTable.writeUInt32LE(nameAt, 0x40 * i + 16);
      at += entryBlobs[i].length; nameAt += Buffer.byteLength(name) + 1;
    });
    const hfsHeader = Buffer.alloc(16); hfsHeader.write('HFS0', 0, 'latin1');
    hfsHeader.writeUInt32LE(entryNames.length, 4); hfsHeader.writeUInt32LE(hfsStrings.length, 8);
    return Buffer.concat([hfsHeader, hfsTable, hfsStrings, ...entryBlobs]);
  }
  const secure = hfs0Image([names[0]], [nca]);
  const rootPartition = hfs0Image(['update', 'normal', 'secure'], [hfs0Image([], []), hfs0Image([], []), secure]);
  const cardHeader = Buffer.alloc(0x200);
  cardHeader.write('HEAD', 0x100, 'latin1');
  cardHeader.writeBigUInt64LE(0x200n, 0x130);
  const xci = put('card.xci', Buffer.concat([cardHeader, rootPartition]));
  r = detect(xci, {keys: keysFile, defaultKeys: false});
  assert.equal(r.kind, 'xci'); assert.equal(r.problem, null);
  assert.equal(r.engine, 'rrlib'); assert.ok(r.confident);
  assert.equal(r.titleId, titleId); assert.equal(r.fileCount, 1);
  // A card has no ticket to name the game when there are no keys.
  r = detect(xci, {keys: path.join(root, 'nope.keys'), defaultKeys: false});
  assert.equal(r.problem, 'keys'); assert.equal(r.engine, null);
  // Taking the whole game out: the RomFS file comes back byte for byte, from
  // the NSP and from the card alike.
  for (const container of [nsp, xci]) {
    const out = path.join(root, `out-${path.extname(container).slice(1)}`);
    const seen = [];
    const summary = await extractGame(container, {romfsDir: path.join(out, 'romfs'), exefsDir: path.join(out, 'exefs'),
      keys: keysFile, defaultKeys: false, onProgress: progress => seen.push(progress)});
    assert.equal(summary.files, 1); assert.equal(summary.bytes, MEMFS.length); assert.equal(summary.titleId, titleId);
    assert.deepEqual(fs.readFileSync(path.join(out, 'romfs', 'common', 'script.memfs')), MEMFS);
    assert.equal(seen.at(-1).done, MEMFS.length);
  }
  await assert.rejects(extractGame(nsp, {romfsDir: path.join(root, 'stopped'), keys: keysFile, defaultKeys: false, isCancelled: () => true}),
    error => error.code === 'cancelled');
  await assert.rejects(extractGame(nsp, {romfsDir: path.join(root, 'nokeys'), keys: path.join(root, 'nope.keys'), defaultKeys: false}),
    error => error.code === 'keys');

  // Something that is neither container says so.
  assert.match(detect(put('junk.xci', Buffer.alloc(0x400)), {keys: keysFile, defaultKeys: false}).problem, /not an NSP or XCI/);
} finally {
  fs.rmSync(root, {recursive: true, force: true});
}
console.log('detect-engine assertions passed');
})().catch(error => { console.error(error); process.exit(1); });
