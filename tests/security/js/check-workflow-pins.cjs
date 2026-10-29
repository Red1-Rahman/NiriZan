#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');

const root = path.resolve(__dirname, '../../..');
const dir = path.join(root, '.github', 'workflows');
const failures = [];

const WORKFLOW_EXT = /\.ya?ml$/;
const INSTALL_RE = /\b(pip install|npm install|npm ci)\b/;
const PRIVILEGED_KEYS = ['contents', 'pull-requests', 'id-token'];

for (const file of fs.readdirSync(dir).filter(f => WORKFLOW_EXT.test(f)).sort()) {
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
    const privileged = PRIVILEGED_KEYS.some(k => perms[k] === 'write');

    // Flag ANY install anywhere in a privileged job: in the same run: block as
    // other commands, or before any later step. Do not require a later step
    // to exist; the install itself runs with the job's elevated token the
    // moment it executes, regardless of what (if anything) follows it.
    const installSteps = steps
      .map((s, i) => ({ i, run: `${s.run || ''}` }))
      .filter(s => INSTALL_RE.test(s.run));

    const checkoutUnsafe = steps.some(s => `${s.uses || ''}`.startsWith('actions/checkout@') && s.with?.['persist-credentials'] !== false);

    console.log(`${file} | ${job.name || id} | ${JSON.stringify(perms)} | installs=${installSteps.length}, unsafe-checkout=${checkoutUnsafe}`);

    if (privileged && installSteps.length > 0) {
      for (const { i, run } of installSteps) {
        const sameStepHasMoreCommands = run.split(/\n|&&|;/).filter(c => c.trim()).length > 1;
        const laterStepExists = i < steps.length - 1;
        if (sameStepHasMoreCommands || laterStepExists) {
          failures.push(`${file}:${id}: unpinned package install at step ${i} runs with privileged permissions (same-step or later commands present)`);
        } else {
          failures.push(`${file}:${id}: unpinned package install at step ${i} runs with privileged permissions`);
        }
      }
    }
  }

  const trigger = doc.on?.workflow_run;
  if (trigger) {
    const hasBranches = Boolean(trigger.branches);
    const annotation = /# security-reviewed:\s*\d{4}-\d{2}-\d{2}\s*\n\s*workflow_run:/.test(source);

    // Evaluate EVERY job in this workflow, not just whether at least one job
    // is guarded. A workflow_run trigger exposes the triggering ref's commits
    // to every job in the file, and GitHub grants workflow_run jobs secrets
    // and write-scoped tokens by default -- an unguarded sibling job is a
    // real exposure even when another job in the same file is guarded.
    const jobEntries = Object.entries(doc.jobs || {});
    const unguardedJobs = jobEntries
      .filter(([, j]) => !/head_repository\.full_name/.test(j.if || ''))
      .map(([id]) => id);

    console.log(`${file} | workflow_run branches=${hasBranches} unguarded_jobs=${unguardedJobs.join(',') || 'none'}`);

    if (hasBranches && unguardedJobs.length > 0 && !annotation) {
      for (const id of unguardedJobs) {
        failures.push(`${file}:${id}: workflow_run branch filter lacks head_repository.full_name guard on this job`);
      }
    }
  }
}

if (failures.length) { console.error(failures.join('\n')); process.exitCode = 1; }