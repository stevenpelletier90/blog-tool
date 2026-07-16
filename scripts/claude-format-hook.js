// PostToolUse formatter for Claude Code edits.
//
// Files Claude edits land on disk without passing through an editor, so
// format-on-save never sees them and they drift out of style. This hook closes
// that gap: it auto-fixes whatever Claude just touched, using the same fixer
// `ruff check .` checks with — and nothing more. Hook and gate must agree; a
// hook that applies a standard the gate does not check is how a one-line edit
// turns into a thousand-line diff.
//
// Claude Code passes the edited file's path on stdin as JSON
// (`tool_input.file_path`) — there is no CLAUDE_FILE_PATH env var; an earlier
// inline version relied on one and silently no-op'd.
//
// Formatting must never block a tool call, so every branch exits 0 and all
// fixer output is discarded. Real violations still surface at `ruff check .`,
// which is the actual gate.

import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { extname, join } from 'node:path';

let input;
try {
  input = JSON.parse(readFileSync(0, 'utf8') || '{}');
} catch {
  process.exit(0);
}

const filePath = input?.tool_input?.file_path ?? '';
if (filePath === '' || !existsSync(filePath)) process.exit(0);

const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd();
const isWin = process.platform === 'win32';

// spawnSync({ shell: true }) runs via cmd.exe on Windows, /bin/sh elsewhere.
// Quote the path for that shell: cmd treats backslashes literally inside double
// quotes (paths can't contain `"`); POSIX shells need single-quote escaping.
const quote = (p) => (isWin ? `"${p}"` : `'${p.replace(/'/g, `'\\''`)}'`);
const run = (cmdline) => spawnSync(cmdline, { cwd: projectDir, shell: true, stdio: 'ignore' });

// Prefer the venv's ruff over a bare `ruff` on PATH. requirements-dev.txt pins
// ruff==0.15.21, and only the venv binary honors that pin — a PATH ruff is
// whatever version happens to be installed globally, which can format to a
// different style than the repo's gate. Same class of bug as bare `npx <tool>`
// silently fetching an unpinned tool from the registry. There is currently NO
// ruff on this machine's PATH, so the venv binary is also the only one that
// works at all; the PATH fallback exists for contributors who install ruff
// globally instead of running setup.bat/setup.sh.
const venvRuff = join(projectDir, 'blog-extractor-env', isWin ? 'Scripts/ruff.exe' : 'bin/ruff');
const ruff = existsSync(venvRuff) ? quote(venvRuff) : 'ruff';

const file = quote(filePath);

switch (extname(filePath).toLowerCase()) {
  case '.py':
    // `ruff check --fix` ONLY — deliberately not `ruff format`.
    //
    // This repo has never adopted ruff's formatter: `ruff check .` passes clean
    // while `ruff format --check .` would reformat 5 files, and blog_extractor.py
    // alone is a ~1995-line rewrite (68% of the file). Running the formatter here
    // would mean the first edit to any module buries a one-line change under a
    // mass reformat nobody asked for, applying a standard the gate never checks.
    //
    // `check --fix` matches `ruff check .` exactly, so hook and gate agree.
    // If the formatter is ever wanted, adopt it as its own deliberate commit
    // (`ruff format .` repo-wide) and add it here afterwards — not before.
    //
    // If ruff is missing entirely, spawnSync reports a nonzero status rather
    // than throwing; exit codes are ignored here, so it degrades to a no-op
    // instead of blocking the edit.
    run(`${ruff} check --fix ${file}`);
    break;
  // No .md/.json/.yml branch on purpose: this repo has no formatter for them.
  // requirements-dev.txt pins ruff/mypy/pytest and there is no package.json, so
  // adding prettier here would mean bolting a node toolchain onto a Python repo
  // purely for symmetry with the other repos' hooks. Nothing to run, no branch.
  default:
    break;
}

process.exit(0);
