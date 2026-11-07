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
    // Field labels and help in Vietnamese, where a tool has them, name real fields.
    for (const [name, text] of Object.entries(tool.vi.args || {})) {
      const arg = tool.args.find(item => item.name === name);
      assert.ok(arg, `${tool.id}: Vietnamese text for a field it does not have: ${name}`);
      assert.ok(text.label && (text.help || !arg.help), `${tool.id} ${name}: Vietnamese label and help`);
    }
  }
}
console.log('catalog-vi assertions passed');
