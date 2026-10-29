#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const target = process.argv[2];
if (!target) { console.error('Usage: node validate-findings-schema.cjs path/to/findings.json'); process.exit(2); }
// Plain readFileSync is intentional: the input is repo-local, trusted generated JSON; Windows lacks O_NOFOLLOW/O_NONBLOCK.
let entries;
try { entries = JSON.parse(fs.readFileSync(path.resolve(target), 'utf8')); }
catch (e) { console.error(`1: invalid JSON: ${e.message}`); process.exit(1); }
if (!Array.isArray(entries)) entries = entries?.findings;
const required = ['fingerprint_id','title','severity','confidence','preconditions','source_refs','sink','data_flow','security_impact','reproduction_steps','expected_finding_if_exploited','affected_scope','recommended_mitigation','false_positive_considerations','unresolved','status'];
const errors = [];
if (!Array.isArray(entries)) errors.push('1: expected an array of findings');
for (const [i, f] of (entries || []).entries()) {
  const line = i + 1;
  if (!f || typeof f !== 'object' || Array.isArray(f)) { errors.push(`${line}: expected object`); continue; }
  for (const k of required) if (!(k in f)) errors.push(`${line}: missing ${k}`);
  if (!['confirmed','needs_validation','hardening','rejected'].includes(f.status)) errors.push(`${line}: invalid status`);
  if (f.status === 'needs_validation' ? f.severity !== null : typeof f.severity !== 'string') errors.push(`${line}: severity must be null only for needs_validation`);
  if (typeof f.confidence !== 'number' || f.confidence < 0 || f.confidence > 1) errors.push(`${line}: confidence must be in [0,1]`);
  for (const k of required.filter(k => !['severity','confidence','source_refs','unresolved'].includes(k))) if (typeof f[k] !== 'string' || !f[k].trim()) errors.push(`${line}: ${k} must be a non-empty string`);
  if (!Array.isArray(f.source_refs) || !f.source_refs.length) {
    errors.push(`${line}: source_refs must be a non-empty array`);
  } else {
    f.source_refs.forEach((r, n) => {
      if (!r || typeof r !== 'object' || Array.isArray(r)) { errors.push(`${line}: source_refs[${n}] must be an object`); return; }
      // Presence alone is not enough: {file:null, function:false, line:"?", statement:""}
      // satisfies `k in r` for every key while carrying no usable attribution.
      // Require file/function/statement to be populated strings and line to be
      // a positive integer (or a string that parses as one, for "12-34" ranges).
      for (const k of ['file', 'function', 'statement']) {
        if (!(k in r)) errors.push(`${line}: source_refs[${n}] missing ${k}`);
        else if (typeof r[k] !== 'string' || !r[k].trim()) errors.push(`${line}: source_refs[${n}].${k} must be a non-empty string`);
      }
      if (!('line' in r)) {
        errors.push(`${line}: source_refs[${n}] missing line`);
      } else {
        const lineVal = r.line;
        const isPositiveInt = typeof lineVal === 'number' && Number.isInteger(lineVal) && lineVal > 0;
        const isValidRangeString = typeof lineVal === 'string' && /^\d+(-\d+)?$/.test(lineVal.trim());
        if (!isPositiveInt && !isValidRangeString) errors.push(`${line}: source_refs[${n}].line must be a positive integer or a "N" / "N-M" string`);
      }
    });
  }
  if (typeof f.unresolved !== 'boolean') errors.push(`${line}: unresolved must be boolean`);
}
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }