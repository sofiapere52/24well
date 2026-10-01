// Run with: node tests/test_revision.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/revision.js'), 'utf8');
vm.runInNewContext(source + `
  const target = {textContent: ''};
  updateRevisionWarning('old-server', target);
  assert.match(target.textContent, /old-server/);
  assert.match(target.textContent, /Ctrl\\+F5/);
  updateRevisionWarning(UI_REVISION, target);
  assert.equal(target.textContent, '');
  updateRevisionWarning(undefined, target);
  assert.match(target.textContent, /older version/);
  target.textContent = 'Unable to stop output';
  updateRevisionWarning(UI_REVISION, target);
  assert.equal(target.textContent, 'Unable to stop output');
`, {assert});
console.log('Revision warning recovery checks passed.');
