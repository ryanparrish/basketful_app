/**
 * Runs `manage.py seed_e2e_participant`, which (re)creates the e2e
 * participant and products and cancels the participant's open orders.
 *
 * Uses the repo's .venv Python unless E2E_PYTHON names another one.
 */
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');

function pythonExecutable(): string {
  if (process.env.E2E_PYTHON) return process.env.E2E_PYTHON;
  const venvPython = path.join(REPO_ROOT, '.venv/bin/python');
  return existsSync(venvPython) ? venvPython : 'python3';
}

export function seedE2eParticipant() {
  execFileSync(pythonExecutable(), ['manage.py', 'seed_e2e_participant'], {
    cwd: REPO_ROOT,
    stdio: 'inherit',
  });
}
