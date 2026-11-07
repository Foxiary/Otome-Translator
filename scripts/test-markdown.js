const assert = require('node:assert/strict');
const {parseMarkdown, resolveDocLink} = require('../src/markdown');

const blocks = parseMarkdown([
  '# Title',
  '',
  'See **DICH** and [the tools](tools/README.md).',
  '',
  '- one',
  '  - nested',
  '',
  '| A | B |',
  '|---|---|',
  '| c | d |',
  '',
  '```',
  'python tools/mksheet.py',
  '```'
].join('\n'));

assert.equal(blocks[0].type, 'heading');
assert.equal(blocks[1].type, 'paragraph');
assert.equal(blocks[1].inlines.some(node => node.type === 'strong'), true);
assert.equal(blocks[1].inlines.find(node => node.type === 'link').href, 'tools/README.md');
assert.equal(blocks[2].type, 'list');
assert.equal(blocks[2].items[0].children.type, 'list');
assert.equal(blocks[3].type, 'table');
assert.deepEqual(blocks[3].rows.length, 1);
assert.equal(blocks[4].type, 'code');
assert.match(blocks[4].text, /mksheet/);

assert.deepEqual(resolveDocLink('README.md', 'tools/README.md'), {file: 'tools/README.md', hash: ''});
assert.deepEqual(resolveDocLink('docs/01-data-layout.md', '../README.md'), {file: 'README.md', hash: ''});
assert.deepEqual(resolveDocLink('DICH.md', '#nhanh'), {hash: '#nhanh'});
assert.deepEqual(resolveDocLink('README.md', 'https://github.com/Foxiary/ul-vi-patch'), {external: 'https://github.com/Foxiary/ul-vi-patch'});
assert.equal(resolveDocLink('README.md', '../secrets.txt'), null);
assert.equal(resolveDocLink('README.md', 'javascript:alert(1)'), null);
