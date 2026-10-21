const assert = require('node:assert/strict');
const {engines} = require('../src/engines');

// Every tool, group and document shows in Vietnamese when that language is chosen.
for (const engine of engines) {
  assert.ok(engine.vi.flow, `${engine.id} flow`);
  for (const group of engine.groups) {
    assert.ok(engine.vi.groups[group]?.name && engine.vi.groups[group]?.summary, `${engine.id} group ${group}`);
  }
  for (const [, file] of engine.docs) assert.ok(engine.vi.docs[file], `${engine.id} document ${file}`);
  for (const tool of engine.tools) {
    assert.ok(tool.vi?.title && tool.vi?.description, `${tool.id} Vietnamese title and description`);
    assert.equal(!!tool.vi.note, !!tool.note, `${tool.id} has a note in both languages or neither`);
  }
}
console.log('catalog-vi assertions passed');
