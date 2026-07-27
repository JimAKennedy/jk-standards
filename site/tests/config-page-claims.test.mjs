// Cross-check: every field in config-schema.json is mentioned on
// /reference/configuration/. Adding a Config dataclass field must land
// on the page (via the emitter regeneration + iteration), not disappear.

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { loadFixture, loadPage } from './helpers.mjs';

test('reference/configuration: every schema field appears on the page', () => {
  const fixture = loadFixture('config-schema');
  const html = loadPage('reference/configuration/index.html');

  const missing = [];
  for (const field of fixture.fields) {
    if (!html.includes(field.name)) missing.push(field.name);
  }
  assert.equal(
    missing.length,
    0,
    `configuration page missing field(s): ${missing.join(', ')}`,
  );
});

test('reference/configuration: intro count matches fixture length', () => {
  const fixture = loadFixture('config-schema');
  const html = loadPage('reference/configuration/index.html');
  const match = html.match(/<strong>(\d+)<\/strong>/);
  assert.ok(match, 'expected a <strong>N</strong> count in the intro');
  assert.equal(
    Number(match[1]),
    fixture.fields.length,
    `intro count ${match[1]} does not match config-schema.json length ${fixture.fields.length}`,
  );
});
