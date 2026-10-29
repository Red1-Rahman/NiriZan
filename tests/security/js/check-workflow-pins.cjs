#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');

const root = path.resolve(__dirname, '../../..');
const dir = path.join(root, '.github', 'workflows');
const failures = [];

const WORKFLOW_EXT = /\.ya?ml$/;

// Package-manager install detection, covering common executable forms.
// pip3/pip, npm (install/ci), pnpm (add/install), yarn add -- not an
// exhaustive list of every package manager, but covers the ones realistic
// in a GitHub Actions Python/Node workflow.
const INSTALL_RE = /\b(pip3?\s+install|npm\s+(install|ci)|pnpm\s+(add|install)|yarn\s+add)\b/;

// GitHub recognizes a scalar `permissions: write-all` (grants every scope
// write) in addition to the per-scope object form. Treating only the three
// hardcoded keys as "privileged" missed write-all entirely, and missed any
// other write-scoped key (packages, actions, checks, etc.) beyond the three
// originally checked.
const WRITE_ALL = 'write-all';
function isPrivileged(perms) {
  if (perms === WRITE_ALL) return true;
  if (!perms || typeof perms !== 'object') return false;
  return Object.values(perms).some(v => v === 'write' || v === WRITE_ALL);
}

for (const file of fs.readdirSync(dir).filter(f => WORKFLOW_EXT.test(f)).sort()) {
  const source = fs.readFileSync(path.join(dir, file), 'utf8');
  const doc = yaml.load(source) || {};
  const uses = [...source.matchAll(/\buses:\s*([^\s#]+)/g)];
  for (const [, ref] of uses) {
    if (!/@[0-9a-fA-F]{40}$/.test(ref)) failures.push(`${file}: unpinned action ${ref}`);
    else if (!/#\s*v\d+\.\d+\.\d+/.test(source.slice(source.indexOf(ref) + ref.length, source.indexOf('\n', source.indexOf(ref)))))
      console.warn(`${file}: SHA pin ${ref} has no # vX.Y.Z comment`);
  }

  const workflowPerms = doc.permissions;
  for (const [id, job] of Object.entries(doc.jobs || {})) {
    const perms = job.permissions !== undefined ? job.permissions : workflowPerms;
    const steps = job.steps || [];
    // When both the workflow and the job omit `permissions`, the effective
    // GITHUB_TOKEN scope comes from the repository/organization default,
    // which this static check cannot see (it may be read-write). Treat that
    // as unresolved rather than as unprivileged.
    const permissionsOmitted = perms === undefined;
    const privileged = isPrivileged(perms);

    const installSteps = steps
      .map((s, i) => ({ i, run: `${s.run || ''}` }))
      .filter(s => INSTALL_RE.test(s.run));

    const checkoutUnsafe = steps.some(s => `${s.uses || ''}`.startsWith('actions/checkout@') && s.with?.['persist-credentials'] !== false);

    console.log(`${file} | ${job.name || id} | ${permissionsOmitted ? '<omitted>' : JSON.stringify(perms)} | installs=${installSteps.length}, unsafe-checkout=${checkoutUnsafe}`);

    if (permissionsOmitted && installSteps.length > 0) {
      failures.push(`${file}:${id}: package install has unresolved token permissions; declare permissions explicitly`);
    }

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
    const annotation = /# security-reviewed:\s*\d{4}-\d{2}-\d{2}\s*\n\s*workflow_run:/.test(source);

    // A workflow_run job gets secrets and write-scoped tokens regardless of
    // whether `branches` is set -- `branches` only narrows WHICH triggering
    // runs fire the workflow, it is not a trust boundary. Every job in a
    // workflow_run-triggered workflow needs its own evaluation.
    //
    // "Guarded" requires the job's `if:` to actually RESTRICT execution to
    // the trusted repository, not merely mention head_repository.full_name
    // anywhere in the condition -- a condition like
    // `head_repository.full_name != github.repository` mentions the field
    // but selects EXTERNAL repos, the opposite of a guard. We require the
    // comparison to be an equality check against github.repository (the
    // one safe, common pattern); anything else is flagged for manual
    // review rather than silently trusted, since condition expressions are
    // too varied to fully parse here.
    const GUARD_RE = /head_repository\.full_name\s*==\s*github\.repository/;

    const jobEntries = Object.entries(doc.jobs || {});
    const unguardedJobs = jobEntries
      .filter(([, j]) => !GUARD_RE.test(j.if || ''))
      .map(([id]) => id);

    console.log(`${file} | workflow_run trigger present | unguarded_jobs=${unguardedJobs.join(',') || 'none'}`);

    if (unguardedJobs.length > 0 && !annotation) {
      for (const id of unguardedJobs) {
        failures.push(`${file}:${id}: workflow_run trigger lacks a head_repository.full_name == github.repository guard on this job`);
      }
    }
  }
}

if (failures.length) { console.error(failures.join('\n')); process.exitCode = 1; }