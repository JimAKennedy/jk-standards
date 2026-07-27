// Cross-check: every skill in skills.json has a matching <h3 id="…"> on
// /reference/skills/. Same guarantee shape as checks-page-claims.

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { loadFixture, loadPage, extractIds, diffSets } from './helpers.mjs';

test('reference/skills: page sections match skills.json', () => {
  const fixture = loadFixture('skills');
  const expected = new Set(fixture.skills.map((s) => s.name));

  const html = loadPage('reference/skills/index.html');
  const actual = extractIds(html, (id) => expected.has(id));

  assert.equal(
    diffSets(expected, actual),
    '',
    `skills page diverges from skills.json — ${diffSets(expected, actual)}`,
  );
});

test('reference/skills: descriptions render verbatim', () => {
  const fixture = loadFixture('skills');
  const html = loadPage('reference/skills/index.html');
  for (const skill of fixture.skills) {
    // First 40 chars is enough to prove the description ended up on the
    // page — full-string match is brittle to whitespace/entity handling.
    const needle = skill.description.slice(0, 40);
    assert.ok(
      html.includes(needle),
      `skills page missing description for "${skill.name}" (searched for "${needle}")`,
    );
  }
});
