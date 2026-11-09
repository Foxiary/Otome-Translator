const assert = require('node:assert/strict');
const {outputTarget, previewOf} = require('../src/reveal');

const tool = args => ({args});
const dir = (name) => ({name, kind: 'dir'});
const save = (name) => ({name, kind: 'save'});
const file = (name) => ({name, kind: 'file'});
const flag = (name) => ({name, kind: 'bool'});

const screen = file('screen');
assert.equal(outputTarget(tool([screen, dir('output folder')]), {screen: '/ssdata/ttlm_nam.memfs', 'output folder': '/anh'}), '/anh');
assert.equal(outputTarget(tool([screen, dir('output folder')]), {screen: '/ssdata/ttlm_nam.memfs', 'output folder': '  '}), '');
assert.equal(outputTarget(tool([screen]), {screen: '/ssdata/ttlm_nam.memfs'}), '');

const importing = tool([screen, dir('image folder'), dir('--out'), flag('--apply')]);
assert.equal(outputTarget(importing, {screen: '/a.memfs', 'image folder': '/anh', '--out': '/mod/ssdata'}), '');
assert.equal(outputTarget(importing, {screen: '/a.memfs', 'image folder': '/anh', '--out': '/mod/ssdata', '--apply': true}), '/mod/ssdata');

const patch = tool([dir('--jp'), dir('--out'), save('--report'), flag('--apply')]);
assert.equal(outputTarget(patch, {'--jp': '/jp', '--out': '/out', '--report': '/out/rows.csv', '--apply': true}), '/out');
assert.equal(outputTarget(tool([dir('--jp'), save('--csv')]), {'--jp': '/jp', '--csv': '/findings.csv'}), '/findings.csv');

assert.equal(outputTarget(tool([file('NSP'), dir('output folder'), flag('--list')]), {NSP: '/g.nsp', 'output folder': '/out', '--list': true}), '');
assert.equal(outputTarget(tool([file('workbook'), dir('output folder'), flag('--dry-run')]), {workbook: '/s.xlsx', 'output folder': '/out', '--dry-run': true}), '');
assert.equal(outputTarget(tool([dir('--out-dir'), flag('--build')]), {'--out-dir': '/zips'}), '');
assert.equal(outputTarget(tool([dir('--out-dir'), flag('--build')]), {'--out-dir': '/zips', '--build': true}), '/zips');
assert.equal(outputTarget(tool([save('output XLSX')]), {'output XLSX': '/sheet.xlsx'}), '/sheet.xlsx');

// The preview image a dry run of font.py gen drew, for the write dialog.
assert.equal(previewOf('ui.font.memfs: ...\nanh xem truoc -> /tmp/xem thu.png  (tu tren xuong: standard 一, extra 二)\nchay thu - them --apply de ghi vao /mod/font\n'), '/tmp/xem thu.png');
assert.equal(previewOf('anh xem truoc -> C:\\Users\\me\\p.png\r\n'), 'C:\\Users\\me\\p.png');
assert.equal(previewOf('10 font san sang.\nchay thu - them --apply de ghi vao /mod/font'), '');
assert.equal(previewOf(undefined), '');
