// IDE-side measure, no LLM: builds FriedLiver's real project index (extensions/friedliver-agents/
// src/host/projectIndex.ts, bundled on the fly with the esbuild FriedLiver already installs) over a
// repo, times a full build and a re-open from the saved index, and returns the real index_* answers
// for one symbol. Read-only on the repo (unlike FriedLiver's indexBench.test.ts, which edits files).
//
//   node ide_side.mjs --repo DIR --src FRIEDLIVER_CODE_CHECKOUT --symbol NAME [--file DEF_FILE]
//
// Prints JSON to stdout. Works with and without the Merkle tree (feat/index-merkle): when the index
// has `tree`, its root is reported.
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith('--') ? [...acc, [a.slice(2), all[i + 1]]] : acc), []));
const ext = path.join(args.src, 'extensions/friedliver-agents');
const esbuild = createRequire(path.join(ext, 'package.json'))('esbuild');
const dir = mkdtempSync(path.join(tmpdir(), 'fl-index-'));
const out = path.join(dir, 'projectIndex.mjs');
await esbuild.build({ entryPoints: [path.join(ext, 'src/host/projectIndex.ts')], bundle: true, platform: 'node', format: 'esm', outfile: out, logLevel: 'silent' });
const { ProjectIndex, answerIndex, STAT_BATCH } = await import(pathToFileURL(out).href);
rmSync(dir, { recursive: true, force: true });

// FriedLiver's defaults: friedliver.index.maxFiles 50000, maxMemoryMB 150.
const options = { maxFiles: 50_000, maxBytes: 150 * 1024 * 1024 };

async function open(saved) {
  const t = performance.now();
  const ix = new ProjectIndex(args.repo, options);
  if (saved) await ix.load(saved);
  const files = await ix.list();
  if (ix.prune) ix.prune(new Set(files));
  if (ix.updateBatch) for (let i = 0; i < files.length; i += STAT_BATCH) await ix.updateBatch(files.slice(i, i + STAT_BATCH));
  else for (const f of files) await ix.update(f);
  return { ix, ms: performance.now() - t, listed: files.length };
}

const full = await open(undefined);
full.ix.tree?.snapshot?.();
const json = JSON.stringify(full.ix);
const reopen = await open(JSON.parse(json));
const ask = (call) => answerIndex([full.ix], call, false);
const result = {
  index: {
    files_listed: full.listed,
    files_indexed: full.ix.size,
    capped: full.ix.capped,
    build_ms: Math.round(full.ms),
    reopen_ms: Math.round(reopen.ms),
    saved_bytes: Buffer.byteLength(json),
    merkle_root: full.ix.tree?.root?.() ?? null,
  },
  answers: {
    index_symbols: await ask({ tool: 'index_symbols', name: args.symbol }),
    index_search: await ask({ tool: 'index_search', query: args.symbol }),
    index_related: args.file ? await ask({ tool: 'index_related', path: args.file }) : '',
  },
};
process.stdout.write(JSON.stringify(result));
