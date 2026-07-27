// Structural contract for the reusable deploy-site.yml workflow and its
// consumers. This is the executable proof (no live Pages deploy) that the
// reusable shape holds: the producer exposes the parameterized `prebuild` +
// toolchain + `deploy` gate surface, this repo's real caller (publish-site.yml)
// and the ci.yml smoke callers consume it correctly, and the Node-only fixture
// keeps the python-less prebuild seam intact. If any of these drift, every
// downstream consumer breaks — this test fails before a tag ships.
//
// String/regex assertions (not a YAML parse) deliberately mirror the repo's
// grep-based workflow verifies (jk-standards action-pinning etc.): no YAML
// dependency, and the assertions read like the grep contracts they enforce.

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const read = (rel) => readFileSync(resolve(repoRoot, rel), 'utf8');

const deploySite = read('.github/workflows/deploy-site.yml');
const publishSite = read('.github/workflows/publish-site.yml');
const ci = read('.github/workflows/ci.yml');

test('deploy-site.yml is a reusable workflow_call producer, not self-triggered', () => {
  assert.match(deploySite, /^on:\s*\n\s+workflow_call:/m, 'expected `on: workflow_call:`');
  // The header carries a commented consumer-usage example (`on: push` / `branches:
  // [ main ]`); strip comment lines so the anti-self-trigger assertions test only
  // real YAML, not the documentation.
  const active = deploySite
    .split('\n')
    .filter((line) => !/^\s*#/.test(line))
    .join('\n');
  assert.doesNotMatch(
    active,
    /^\s*push:/m,
    'reusable producer must not self-trigger on push',
  );
  assert.doesNotMatch(
    active,
    /branches:\s*\[\s*main\s*\]/,
    'reusable producer must not carry a branches: [main] trigger',
  );
});

test('deploy-site.yml exposes the full parameterized input surface', () => {
  for (const input of [
    'prebuild',
    'working-directory',
    'node-version',
    'python-version',
    'python-install',
    'verify',
    'deploy',
    'version-json',
    'version-key',
  ]) {
    assert.match(
      deploySite,
      new RegExp(`^\\s{6}${input}:`, 'm'),
      `deploy-site.yml missing input \`${input}\``,
    );
  }
});

test('deploy-site.yml gates deploy + verify-live on the deploy input', () => {
  // Both the deploy and verify-live jobs (and the version/artifact steps) must
  // be gated on `inputs.deploy` so a build-only caller (deploy: false) skips
  // every Pages-requiring leg cleanly.
  const gateCount = (deploySite.match(/if:\s*\$\{\{\s*inputs\.deploy\s*\}\}/g) || []).length;
  assert.ok(
    gateCount >= 3,
    `expected >=3 \`if: \${{ inputs.deploy }}\` gates (deploy job, verify-live job, artifact/version steps); found ${gateCount}`,
  );
  // The prebuild step is itself gated so an empty prebuild is a clean no-op.
  assert.match(
    deploySite,
    /if:\s*\$\{\{\s*inputs\.prebuild\s*!=\s*''\s*\}\}/,
    'prebuild step must be gated on a non-empty prebuild input',
  );
});

test('publish-site.yml is a thin caller of the reusable producer (real deploy path)', () => {
  assert.match(publishSite, /uses:\s*\.\/\.github\/workflows\/deploy-site\.yml/);
  assert.match(publishSite, /prebuild:\s*jk-standards emit all/, 'expected the Python prebuild');
  assert.match(publishSite, /python-version:\s*"3\.12"/);
  assert.match(publishSite, /id-token:\s*write/, 'real deploy needs the id-token grant');
  assert.match(publishSite, /deploy:\s*true/, 'the real caller deploys');
});

test('ci.yml wires both build-only smoke callers of the reusable producer', () => {
  // Python-prebuild smoke: this repo's own site, build-only.
  assert.match(ci, /^\s{2}deploy-site-smoke:/m, 'missing deploy-site-smoke job');
  // Node-only fixture smoke: python-less prebuild seam, build-only.
  assert.match(ci, /^\s{2}deploy-site-fixture-smoke:/m, 'missing deploy-site-fixture-smoke job');

  // Both must consume the reusable producer and run build-only (deploy: false)
  // so CI needs no live Pages grant.
  const smokeUses = (ci.match(/uses:\s*\.\/\.github\/workflows\/deploy-site\.yml/g) || []).length;
  assert.ok(smokeUses >= 2, `expected both smoke jobs to consume deploy-site.yml; found ${smokeUses}`);
  const buildOnly = (ci.match(/deploy:\s*false/g) || []).length;
  assert.ok(buildOnly >= 2, `expected both smoke jobs to set deploy: false; found ${buildOnly}`);

  // The fixture smoke targets the Node-only fixture with no Python leg.
  assert.match(ci, /working-directory:\s*tests\/fixtures\/deploy-site/, 'fixture smoke must point at the fixture dir');
});

test('ci-complete aggregates both smoke jobs (needs + result check)', () => {
  const needs = ci.match(/ci-complete:\s*\n\s*needs:\s*\[([^\]]*)\]/);
  assert.ok(needs, 'could not find ci-complete needs list');
  assert.match(needs[1], /deploy-site-smoke/, 'ci-complete needs must include deploy-site-smoke');
  assert.match(needs[1], /deploy-site-fixture-smoke/, 'ci-complete needs must include deploy-site-fixture-smoke');

  assert.match(
    ci,
    /needs\.deploy-site-smoke\.result.*!=.*"success"/,
    'ci-complete result check must gate on deploy-site-smoke',
  );
  assert.match(
    ci,
    /needs\.deploy-site-fixture-smoke\.result.*!=.*"success"/,
    'ci-complete result check must gate on deploy-site-fixture-smoke',
  );
});

test('Node-only fixture keeps the python-less prebuild seam intact', () => {
  const pkg = JSON.parse(read('tests/fixtures/deploy-site/package.json'));
  assert.equal(pkg.type, 'module', 'fixture must be ESM so the .mjs prebuild runs');
  assert.match(pkg.scripts.prebuild, /gen-rules\.mjs/, 'prebuild must run the Node-only generator');
  assert.match(pkg.scripts.build, /astro build/, 'build must be an astro build');

  const genRules = read('tests/fixtures/deploy-site/scripts/gen-rules.mjs');
  assert.match(genRules, /src\/generated\/rules\.json/, 'generator must emit src/generated/rules.json');

  const indexMdx = read('tests/fixtures/deploy-site/src/content/docs/index.mdx');
  assert.match(
    indexMdx,
    /import\s+rules\s+from\s+['"][^'"]*generated\/rules\.json['"]/,
    'the page must import the generated rules.json so a skipped prebuild fails the build loudly',
  );
});
