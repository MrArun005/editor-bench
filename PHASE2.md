# Phase 2: AI-agent task benchmark (design only, not run)

Goal: measure how well each editor's built-in agent finishes realistic coding work on the same repo, under matched conditions.

## Tools and setup

| Tool | Agent surface | Setup | Model parity note |
|---|---|---|---|
| FriedLiver | Agent tabs (Claude Code inside) | Owner's Anthropic account / API key | Pin the same Claude model as the other tools where possible |
| Cursor | Agent mode (Composer) | Cursor Pro account | Pick the same Claude model in the model menu. Disable "Auto" model routing |
| Antigravity IDE | Agent manager + editor | Google account | Default is Gemini. Run once with Gemini (the native setup) and, if offered, once with the same Claude model |
| VS Code | Copilot agent mode | GitHub Copilot subscription | Choose the same Claude model in Copilot's picker |
| OpenCode Desktop | OpenCode agent | Anthropic API key | Configure the same model ID explicitly |

Parity rules: same model (or a declared exception), same repo commit, fresh profile with no extra extensions or MCP servers, auto-approve tool calls where the tool allows it, and the same single prompt text per task. If a tool must ask permission, each click counts as one intervention.

## Fixture

Use the phase-1 fixture (`microsoft/vscode-extension-samples` @ pinned commit), with one small sample extension chosen as the target (for example `helloworld-sample`, extended with a vitest suite). Prepare a `phase2` branch that adds the failing test and seeded bug for task 1. Each task starts from a clean `git worktree` of that branch.

## The 6 tasks

| # | Task | Prompt (abridged) | Success check |
|---|---|---|---|
| 1 | Bug fix with failing test | "`npm test` fails in X; fix the bug, not the test." | Seeded test passes, no test files changed (`git diff --stat -- '*.test.*'` empty), full suite green |
| 2 | Small feature | "Add a `wordCount` command that shows the active editor's word count." | Hidden acceptance test passes, command is contributed in `package.json` |
| 3 | Cross-file refactor | "Rename `Foo` to `Bar` everywhere and extract helper Y into its own module." | `tsc --noEmit` clean, suite green, no remaining `Foo` identifiers |
| 4 | Explain code | "Explain how the LSP sample's server and client talk to each other." | Rubric: 5 required facts, graded blind by a second model plus spot-checks by the owner. No partial credit for wrong facts |
| 5 | UI change verified in browser | "Make the webview sample's button primary-coloured and add a hover state; verify it in the browser." | Playwright screenshot diff against reference plus a computed-style assertion. Did the agent itself open a browser to check? (yes/no) |
| 6 | Multi-step with tests | "Add input validation to the settings parser, write tests first, then implement, and keep the suite green." | New tests exist and fail on the old code (mutation check), suite green, change compiles |

## Metrics per task × tool (3 attempts each; report median and success rate)

- **Success**: the automated check above passes (binary). Task 4 uses its rubric score.
- **Wall time**: from prompt submission until the agent declares itself done (screen recording timestamps).
- **Turns**: user messages needed, including the first.
- **Human interventions**: approvals, corrections and "continue" nudges. Lower is better.
- **Tokens and cost**: wherever the tool shows them (FriedLiver/Claude Code, OpenCode, Copilot usage view). Cursor and Antigravity show only partial data, so record "not visible" rather than estimating.
- **Diff hygiene**: files touched outside the task scope, and leftover debug code.

## Harness

- A `phase2/` folder holds the prompts, the reference solutions, `check_N.sh` per task, and a results sheet (`phase2.csv`).
- The owner (or a helper) runs each attempt by hand in the GUI and screen-records it. The checks run automatically afterwards with `make check TASK=n DIR=worktree`.
- Order: Latin square across tools, so no tool always goes first on a task.

## What it needs from the owner

| Need | Detail |
|---|---|
| Accounts | Cursor Pro, a Google account for Antigravity, GitHub Copilot, and an Anthropic API key (for OpenCode, and FriedLiver if it isn't already signed in) |
| Cost estimate | About 6 tasks × 5 tools × 3 attempts = 90 agent runs. API-billed runs (FriedLiver, OpenCode) cost roughly $0.30–1.50 each with a Claude Sonnet-class model, so about $20–60 in total. Subscription tools (Cursor, Copilot, Antigravity) cost $0 extra within plan limits |
| His time | About 15 min of active time per attempt (prompting, approvals, recording), so about 20 hours for the full 90 runs. A reduced version (1 attempt, 4 tools) is about 6 hours |
| Hardware | Runs on the laptop one tool at a time, the same safety rules as phase 1. No Docker. The AI work happens server-side, so local load is light |
| Decisions | Which model to pin for parity, and whether Antigravity is tested with Gemini, Claude, or both |
