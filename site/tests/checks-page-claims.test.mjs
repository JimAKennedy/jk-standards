// Cross-check: every check in checks.json has a matching section on
// /reference/checks/, and the page has no orphan sections for checks that
// no longer exist. Divergence means the fixture was regenerated but the
// prose fell out of sync (or vice versa).

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { loadFixture, loadPage, extractIds, diffSets } from './helpers.mjs';

test('reference/checks: page sections match checks.json', () => {
  const fixture = loadFixture('checks');
  const expected = new Set(fixture.checks.map((c) => c.name));

  const html = loadPage('reference/checks/index.html');
  const actual = extractIds(html, (id) => expected.has(id));

  assert.equal(
    diffSets(expected, actual),
    '',
    `checks page diverges from checks.json — ${diffSets(expected, actual)}`,
  );
});

test('reference/checks: intro count matches fixture length', () => {
  const fixture = loadFixture('checks');
  const html = loadPage('reference/checks/index.html');
  // The intro sentence renders `<strong>{checksData.checks.length}</strong>`.
  const match = html.match(/<strong>(\d+)<\/strong>/);
  assert.ok(match, 'expected a <strong>N</strong> count in the intro');
  assert.equal(
    Number(match[1]),
    fixture.checks.length,
    `intro count ${match[1]} does not match checks.json length ${fixture.checks.length}`,
  );
});
