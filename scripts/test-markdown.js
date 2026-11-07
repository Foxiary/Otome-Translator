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

// A numbered step with its commands in an indented fence under it (the rrlib
// README): the code stays in the step, loses the indent, and the list goes on.
const steps = parseMarkdown([
  '1. **Get the JP script**:',
  '',
  '   ```',
  '   python tools/nsp.py romfs "<game>.nsp" jp',
  '     indented more',
  '   ```',
  '',
  '2. Check it.',
  '',
  'After.'
].join('\n'));
assert.equal(steps.length, 2);
assert.equal(steps[0].type, 'list');
assert.equal(steps[0].items.length, 2);
assert.deepEqual(steps[0].items[0].blocks, [{type: 'code', text: 'python tools/nsp.py romfs "<game>.nsp" jp\n  indented more'}]);
assert.equal(steps[1].type, 'paragraph');
// An indented fence outside a list is a code block too, not a paragraph.
assert.equal(parseMarkdown('  ```\n  x\n  ```')[0].type, 'code');
// A numbered list that resumes after a paragraph keeps its own numbering.
assert.equal(parseMarkdown('Intro.\n\n3. Third\n4. Fourth')[1].start, 3);
assert.equal(parseMarkdown('1. First')[0].start, 1);
