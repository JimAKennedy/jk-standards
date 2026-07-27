#!/usr/bin/env node
// Node-only prebuild: emulates nfr-review's `rules.json` generation. Emits a
// generated artifact that the Astro build then consumes, proving the reusable
// deploy-site.yml `prebuild` input works with `python-version: ""` (no Python
// leg). This is the counterpart to this repo's own `jk-standards emit all`
// Python prebuild -- one parameterized workflow covers both.
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const outPath = resolve(root, 'src/generated/rules.json');

// A small, deterministic rules table standing in for a real nfr-review policy
// set. Deterministic (no timestamps/randomness) so the fixture build is
// reproducible and the structural contract test can assert exact shape.
const rules = [
	{
		id: 'no-console',
		severity: 'warn',
		description: 'Disallow console.* calls in shipped code',
	},
	{
		id: 'require-alt-text',
		severity: 'error',
		description: 'Images must carry descriptive alt text',
	},
	{
		id: 'max-bundle-kb',
		severity: 'error',
		threshold: 250,
		description: 'Client JavaScript bundle must stay under budget',
	},
];

const payload = {
	generatedBy: 'gen-rules.mjs (Node-only prebuild)',
	ruleCount: rules.length,
	rules,
};

await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
console.log(`gen-rules: wrote ${rules.length} rules to ${outPath}`);
