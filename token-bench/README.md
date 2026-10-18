# token-bench

How many tokens (and dollars) do FriedLiver's agents spend for the same coding task as Claude Code,
Codex CLI, Gemini CLI, Cursor (`cursor-agent`) and Antigravity, on a large repository?

Python stdlib only, no Docker. Every part runs without API keys in **replay mode** (recorded raw
outputs through the same parsers). The live runs cost money and need keys; see the estimate below.

```sh
python3 -m unittest discover -s token-bench/tests -v           # parsers, guards, replay end to end
python3 bench.py estimate --config repos/public.json           # list-price estimate before spending
python3 bench.py run --config repos/public.json --out results-local/replay --replay fixtures --reps 3
python3 report.py results-local/replay                          # full-width dark HTML report
python3 bench.py run --config repos/public.json --out results-local/live --skip-missing-keys   # PAID
FRIEDLIVER_SRC=~/code/FriedLiver-Code python3 bench.py context-replay --config repos/public.json \
  --repo-dir results-local/live/work/typescript --out results-local/live                       # free, no LLM
```

The fixtures in `fixtures/` are **synthetic** (`fixtures/make_fixtures.py`): they test the plumbing
and say nothing about any tool. A report built from them carries a red banner saying so.

## How each tool reports usage headlessly

| Tool | Headless command | Where the tokens are | Cache tokens | Resume (S2, S5) | Source |
|---|---|---|---|---|---|
| Claude Code | `claude --bare -p … --output-format stream-json --verbose` | `usage` on every `assistant` message (one per API call; dedupe by `message.id`), final `result` has `total_cost_usd`, `usage`, `session_id` | `cache_read_input_tokens`, `cache_creation_input_tokens`; `input_tokens` is uncached | `--resume <session_id>`; after a resume `total_cost_usd` includes earlier runs, so cost is recomputed from tokens | [Headless docs](https://code.claude.com/docs/en/headless) |
| Codex CLI | `codex exec --json` | `turn.completed.usage` | `cached_input_tokens` is inside `input_tokens`; `reasoning_output_tokens` | `codex exec resume <thread_id>` (`thread.started.thread_id`) | [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) |
| Gemini CLI | `gemini -p … --output-format stream-json --approval-mode auto_edit` | final `result.stats`: `input_tokens` (= promptTokenCount, cached part included), `cached`, `output_tokens` (candidates only), `total_tokens`, `tool_calls`; thinking = total − input − output | `cached` (implicit caching) | `--resume latest` (takes `latest` or an index, not an id) | [Headless docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/headless.md); field mapping read from the CLI's `convertToStreamStats` (v0.64.0) |
| Cursor | `cursor-agent -p … --output-format stream-json` | Documented `result` has no usage. Newer CLIs add `usage {inputTokens, outputTokens, cacheReadTokens, cacheWriteTokens}`, where `inputTokens` is uncached and billing = the three input fields summed. No usage -> row flagged "tokens not reported" | `cacheReadTokens`, `cacheWriteTokens` | `--resume <session_id>` | [Output format](https://cursor.com/docs/cli/reference/output-format), [Cursor staff on the usage fields](https://forum.cursor.com/t/discrepancies-between-cursor-cli-usage-and-billing/164471) |
| Antigravity CLI | `agy -p … --output-format stream-json --dangerously-skip-permissions --sandbox` (local only) | `result.usage {input_tokens, output_tokens, thinking_tokens, cache_read_tokens, total_tokens}`; tool steps are `step_update` with `step_type: tool` | in the docs' examples total = input + output, so cache reads are inside `input_tokens` and thinking inside `output_tokens` (inferred, not stated) | `--conversation <conversation_id>` | [Headless docs](https://antigravity.google/docs/cli/headless) |
| Antigravity IDE | none | manual protocol (below); `agy` is the automated stand-in for its agent | | | |
| FriedLiver agents | ACP, as FriedLiver starts them: `claude-agent-acp`, `codex-acp`, `gemini --acp` (`agent-core/main/agents/registry.ts`) | `session/prompt` result `usage {inputTokens, outputTokens, cachedReadTokens, cachedWriteTokens, thoughtTokens, totalTokens}` (UNSTABLE in ACP SDK 1.9, cumulative over the session, so a turn = the difference); `session/update` `usage_update {used, size, cost?}` = context window and cumulative cost | `cachedReadTokens`, `cachedWriteTokens` | the same ACP session | `@agentclientprotocol/sdk` 1.9.0 `schema/types.gen.d.ts` (`Usage`, `UsageUpdate`); FriedLiver folds `usage_update` in `extensions/friedliver-agents/src/shared/session.ts` |

`acp.py` is a small headless ACP client (stdio JSON-RPC, answers `fs/*` and permission requests,
logs every message) so the FriedLiver arms run in CI exactly through the adapters FriedLiver uses.

## Scenarios

Each is a fixed prompt plus a success check (`repos/public.json`). S2 continues S1's session and S5
continues S4's; every other scenario starts a fresh session on a fresh `git reset --hard` checkout.

| | Prompt (public repos) | Success check | Measures |
|---|---|---|---|
| S1 | "Give me an overview of this project's architecture." (TypeScript v6.0.3) | answer names compiler, services, server | how much each tool reads into context cold |
| S2 | "List the modules again." (same session) | answer names compiler, services | re-read waste vs. caching |
| S3 | "Where is `isTypeAssignableTo` defined and what calls it?" | answer names `checker.ts` | search efficiency |
| S4 | change `stripEndSlash` (nestjs/nest v11.2.7) to drop every trailing slash, update its test | spec file changed **and** the repo's spec plus a hidden spec pass (mocha) | edit + test loop |
| S5 | "Now also handle a path made only of slashes …" (same session) | hidden S5 spec passes | diff-awareness |
| S6 | explain the compile pipeline from .ts to emitted JS | answer names scanner, parser, binder, checker, emit | module explanation |
| S7 | read RFC 9110 with the tool's web fetch, name the "Misdirected Request" code | answer contains 421 | fetch: cleaned text vs raw HTML. **Local runs only** (`"network": true`): CI skips it and gives agents no web tools |

Why two repos: TypeScript v6.0.3 (about 70k files, the last TypeScript-written release, the tag
FriedLiver's own index bench uses) is the large one; its tests need a full build, so the edit
scenarios use nestjs/nest, a large NestJS framework monorepo, whose spec runs in seconds.
`checks/selfcheck.py` proves the S4/S5 checks fail on the untouched repo and pass after a correct
hand-written edit (CI job `free-checks`).

**Metrics per run:** uncached input, cache read, cache write, output (reasoning included), list-price
cost (`prices.json`), tool-reported cost when there is one, tool calls, bytes of tool output fed
back, files read, wall time, success, human interventions (manual rows). **3 repetitions**,
round-robin arm order, medians with min–max.

**Model parity.** Arms are compared only inside a group: `anthropic` (Claude Code, FriedLiver+Claude,
Cursor on its Sonnet model) all on Claude Sonnet 5.5; `openai` (Codex, FriedLiver+Codex) on gpt-5.5;
`google` (Gemini CLI, FriedLiver+Gemini, Antigravity CLI, Antigravity IDE) on Gemini 3.1 Pro.
Override per arm with `--model arm=model`.

**Vanilla setup.** `claude --bare`, `codex --ignore-user-config`, and a fresh `CLAUDE_CONFIG_DIR` /
`CODEX_HOME` for the FriedLiver arms, so nobody's plugins, hooks, MCP servers or memory get counted.
Gemini CLI and `agy` still read `~/.gemini`: run with no Gemini extensions installed.

**Approvals.** The narrowest mode that still edits: Claude `acceptEdits` with an explicit tool list,
Codex `workspace-write` (network off), Gemini `auto_edit`, Cursor without `--force`; web tools only
for network scenarios. FriedLiver arms auto-approve ACP permission requests except `fetch` (denied in
CI and in non-network scenarios). `agy` has no per-tool approval flag headless, so it runs with
`--sandbox` and is local only.

## Secrets and public CI

- Each agent process gets an allowlisted environment (`PATH`, `HOME`, `TMPDIR`, locale, shell) plus
  only its own tool's key (`bench.arm_env`); setup commands and success checks get no key at all.
- Agents run in a throwaway `git worktree` of the pinned commit, deleted after each session.
- Every transcript is redacted before it is written (exact key values, then `sk-ant-…`, `sk-…`,
  `AIza…`, `key_…` shapes). CI uploads parsed results and the report only; raw transcripts only
  with the `upload_raw` input.
- The workflow is `workflow_dispatch` only with `contents: read`; keys appear only in the live job's
  `Run` step. The Cursor CLI is installed from a pinned version's tarball checked against a SHA-256;
  on a mismatch the Cursor arm is skipped.

## IDE-side measures (no LLM, free)

- **Index build.** `ide_side.mjs` bundles FriedLiver's real `projectIndex.ts` with the esbuild FriedLiver
  already ships and times a full build, a re-open from the saved index, and the saved size (and the
  Merkle root when run against `feat/index-merkle`). Claude Code, Codex and Gemini CLI keep no index
  (0 B, they search on demand). Cursor indexes in its cloud, which is not observable headlessly:
  read it off Cursor Settings > Indexing by hand if you want it.
- **S3 context cost.** `context_replay.py` sends one fixed trace (find definition, find callers, read
  the file) through each tool's output format and caps: Claude Code's Grep/Read (`cat -n`, 2000 lines),
  Codex's shell output (head+tail cut to 10 KiB / 256 lines), Gemini CLI's search/read_file. Those three
  are emulations, with the constants at the top of the file to correct per version. FriedLiver's row is
  its real `index_symbols` / `index_search` answers. Tokens = bytes/4 (estimate).

## Cost of a full run (3 reps x 7 scenarios, list prices 2026-10-18)

`python3 bench.py estimate` computes this from each scenario's `estimate` block (input incl. cache,
output incl. reasoning; 85 % of input assumed cached, 8 % cache writes on Anthropic). The range is
x0.5 to x2: reasoning-heavy models (gpt-5.5, Gemini Pro) and long Gemini prompts over 200k tokens
(priced at the <=200k tier here) push towards the top.

| Arm | Billed to | Public repos | Large private repo (template estimates) |
|---|---|---|---|
| claude | Anthropic API | $4.03 ($2–8) | $5.75 ($3–11) |
| friedliver-claude | Anthropic API | $4.03 ($2–8) | $5.75 ($3–11) |
| codex | OpenAI API | $11.36 ($6–23) | $16.12 ($8–32) |
| friedliver-codex | OpenAI API | $11.36 ($6–23) | $16.12 ($8–32) |
| gemini | Gemini API | $4.54 ($2–9) | $6.45 ($3–13) |
| friedliver-gemini | Gemini API | $4.54 ($2–9) | $6.45 ($3–13) |
| **API cash, all six** | | **~$40 ($20–80)** | **~$57 ($28–113)** |
| cursor | Cursor plan | ~$4 list-equivalent | ~$6 |
| antigravity, antigravity-ide | Google AI plan quota | ~$4.5 each, equivalent | ~$6.5 each |
| friedliver-ui (manual) | your Claude login | ~$4 equivalent | ~$6 |

Halve the OpenAI line by running Codex on `gpt-5.3-codex` (`--model codex=gpt-5.3-codex --model friedliver-codex=gpt-5.3-codex`).
`claude` runs are also capped per turn with `--max-budget-usd` (default $3).

## Private repos: local only

The public repo never sees a private repo's name, paths, symbols or outputs.

1. `cp repos/private.example.json repos/private.local.json` and fill in the `<...>` values: the repo path,
   a pinned commit, an install command, the S3 symbol (e.g. a service function), the S4/S5
   edit and the command that runs its spec. `*.local.json` is gitignored (a unit test checks).
2. `./run-private-local.sh` prints the estimate, asks, then runs. The checkout is a detached
   `git worktree` of your clone (your working tree is never touched), and everything goes to
   `~/token-bench-private/<timestamp>/`.
3. `bench.py` refuses a `"private": true` config when `CI`/`GITHUB_ACTIONS` is set, and refuses to
   write its results anywhere inside this repo.

## Manual protocol (Antigravity IDE, FriedLiver's own chat UI)

For each scenario and repetition: reset the checkout (`git reset --hard <sha> && git clean -fd`),
open a new conversation on the group's model (S2/S5: same conversation as S1/S4), paste the prompt
exactly, start a stopwatch, approve whatever the agent asks (count each approval as an intervention),
stop when it says it is done. Run the scenario's check (`check.cmd` from the config for S4/S5).
Copy the conversation's token usage if the UI shows it; leave the token columns empty if it does
not (the row is then marked "tokens not reported" and the `agy` arm is the token number for
Antigravity). Fill `fixtures/manual-antigravity-ide.sample.csv`'s columns, then:
`python3 bench.py import-manual --config C --arm antigravity-ide --csv yours.csv --out RESULTS && python3 report.py RESULTS`.
Budget about 3–5 minutes per prompt: 21 prompts per repo, so roughly 1.5–2 hours per repo per GUI.

## Known gaps

- **FriedLiver does not log token usage yet.** Its UI keeps only `usage_update` (context used/size,
  cost). `session/prompt`'s `usage` (input/output/cache per session) is returned by
  `AgentHub.prompt` but not stored, so a FriedLiver UI run has no token numbers to copy. Appending each
  turn's `PromptResponse.usage` to a JSONL (or showing it in the chat) closes the friedliver-ui arm.
- **The index tools need the editor.** `index_*` answers come from the editor host through the MCP
  bridge; there is no headless index server. The `friedliver-*` arms therefore run FriedLiver's
  adapters without the index unless `FRIEDLIVER_INDEX_MCP` (a JSON list of ACP `mcpServers`) points
  at one. The index's effect shows in the IDE-side S3 replay and in manual friedliver-ui runs.
- This client offers ACP `fs` but not `terminal`, so agents run shell commands themselves; FriedLiver
  offers both. Command output reaches the model either way.
- Cursor's usage field is undocumented; Antigravity's cache split is inferred from the docs' numbers.
