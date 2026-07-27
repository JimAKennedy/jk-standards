// Tiny helpers for site claim-tests. Reads rendered HTML under site/dist/
// and JSON fixtures under site/src/generated/. The tests assume the site
// has been built (npm run build); the npm `test` script chains build → test.
//
// No jsdom dep — the pages are static and the shapes we cross-check
// (id="name" sections, name mentions) are straightforward to extract
// with regex.

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const SITE_ROOT = resolve(HERE, '..');
export const DIST = resolve(SITE_ROOT, 'dist');
export const GENERATED = resolve(SITE_ROOT, 'src', 'generated');

export function loadFixture(name) {
  const raw = readFileSync(resolve(GENERATED, `${name}.json`), 'utf-8');
  return JSON.parse(raw);
}

export function loadPage(relPath) {
  return readFileSync(resolve(DIST, relPath), 'utf-8');
}

// Extract the set of id="…" values that appear on the page. The theme
// contributes a fixed set of framework ids (search widget, sidebar, etc.);
// callers pass a `keep` predicate to filter down to their entries.
export function extractIds(html, keep = () => true) {
  const ids = new Set();
  const re = /\bid="([a-z][a-z0-9_-]*)"/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (keep(m[1])) ids.add(m[1]);
  }
  return ids;
}

// Symmetric difference between two sets, formatted for assertion messages.
export function diffSets(expected, actual) {
  const missing = [...expected].filter((x) => !actual.has(x)).sort();
  const extra = [...actual].filter((x) => !expected.has(x)).sort();
  const parts = [];
  if (missing.length) parts.push(`missing on page: ${missing.join(', ')}`);
  if (extra.length) parts.push(`extra on page (not in fixture): ${extra.join(', ')}`);
  return parts.join('; ');
}
