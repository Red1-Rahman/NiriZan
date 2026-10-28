#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');

const root = path.resolve(__dirname, '../../..');
const dir = path.join(root, '.github', 'workflows');
const failures = [];
const reviewed = new Set();

for (const file of fs.readdirSync(dir).filter(f => f.endsWith('.yml')).sort()) {
  const source = fs.readFileSync(path.join(dir, file), 'utf8');
  const doc = yaml.load(source) || {};
  const uses = [...source.matchAll(/\buses:\s*([^\s#]+)/g)];
  for (const [, ref] of uses) {
    if (!/@[0-9a-fA-F]{40}$/.test(ref)) failures.push(`${file}: unpinned action ${ref}`);
    else if (!/#\s*v\d+\.\d+\.\d+/.test(source.slice(source.indexOf(ref) + ref.length, source.indexOf('\n', source.indexOf(ref)))))
      console.warn(`${file}: SHA pin ${ref} has no # vX.Y.Z comment`);
  }
  const workflowPerms = doc.permissions || {};
  for (const [id, job] of Object.entries(doc.jobs || {})) {
    const perms = job.permissions || workflowPerms;
    const steps = job.steps || [];
    const installs = steps.map((s, i) => /\b(pip install|npm install|npm ci)\b/.test(`${s.run || ''}`) ? i : -1).filter(i => i >= 0);
    const checkoutUnsafe = steps.some(s => `${s.uses || ''}`.startsWith('actions/checkout@') && s.with?.['persist-credentials'] !== false);
    console.log(`${file} | ${job.name || id} | ${JSON.stringify(perms)} | installs=${installs.length}, unsafe-checkout=${checkoutUnsafe}`);
    const privileged = ['contents', 'pull-requests', 'id-token'].some(k => perms[k] === 'write');
    if (privileged && installs.some(i => steps.slice(i + 1).some(s => s.uses || s.run)))
      failures.push(`${file}:${id}: unpinned package install before subsequent workflow step`);
  }
  if (doc.on?.workflow_run || doc['on']?.workflow_run) {
    const trigger = doc.on?.workflow_run || doc['on'].workflow_run;
    const hasBranches = Boolean(trigger.branches);
    const guarded = Object.values(doc.jobs || {}).some(j => /head_repository\.full_name/.test(j.if || ''));
    const annotation = /# security-reviewed:\s*\d{4}-\d{2}-\d{2}\s*\n\s*workflow_run:/.test(source);
    console.log(`${file} | workflow_run branches=${hasBranches} head_repository_guard=${guarded}`);
    if (hasBranches && !guarded && !annotation) failures.push(`${file}: workflow_run branch filter lacks head_repository.full_name guard`);
  }
}
if (failures.length) { console.error(failures.join('\n')); process.exitCode = 1; }
