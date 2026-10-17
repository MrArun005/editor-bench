# Editor benchmark — phases + A/B (2026-10-17, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39055777241

Scenarios: slow-shell, large-repo.

## Arms

| Arm | Version | VS Code base | Install size (MB) | Source / verification |
|---|---|---|---:|---|
| FriedLiver | 1.142.0 | 1.142.0 | 563 | sha256 verified; codesign valid |
| VS Code (stock) | 1.142.0 | 1.142.0 | 865 | vendor publishes no hash; codesign valid |
| FriedLiver + settings-perf | 1.142.0 | 1.142.0 | 563 | same binary as FriedLiver + settings below |

Settings added for **FriedLiver + settings-perf** (on top of `update.mode: none`):

```json
{
 "editor.cursorBlinking": "blink",
 "workbench.startupEditor": "none",
 "typescript.tsserver.useSyntaxServer": "never",
 "files.watcherExclude": {
  "**/.git/objects/**": true,
  "**/.git/subtree-cache/**": true,
  "**/.hg/store/**": true,
  "**/.venv/**": true,
  "**/__pycache__/**": true,
  "**/.next/**": true,
  "**/.turbo/**": true,
  "**/.gradle/**": true,
  "**/target/**": true,
  "**/dist/**": true,
  "**/build/**": true,
  "**/node_modules/**": true
 },
 "extensions.experimental.deferredStartupFinishedActivation": true
}
```

## Cold start (1 warm-up discarded, then 5 runs, round-robin across arms)

| Arm | Launch → workbench ready, median (p90) ms | Launch → extension host ready, median (p90) ms | Launch → first window, median (p90) ms |
|---|---:|---:|---:|
| FriedLiver | 1,318 (2,722) | 1,546 (3,071) | 924 (1,427) |
| VS Code (stock) | 1,596 (2,219) | 2,840 (4,109) | 1,112 (1,621) |
| FriedLiver + settings-perf | 2,020 (2,910) | 2,252 (3,194) | 1,300 (1,747) |

## Startup phases (cold runs, median ms, from the product's own perf marks)

The first seven rows are consecutive and add up to process start → workbench ready (each is a median, so the sum is close to the workbench median, not equal). The rows after the divider break that down or cover the extension host.

| Phase | Marks | FriedLiver | VS Code (stock) | FriedLiver + settings-perf |
|---|---|---:|---:|---:|
| Process start → main started | `willLoadMainBundle` → `didStartMain` | 146 | 378 | 442 |
| Main: switches, locale, app ready | `didStartMain` → `mainAppReady` | 93 | 108 | 151 |
| Main services → window opened | `mainAppReady` → `willOpenNewWindow` | 287 | 320 | 400 |
| Renderer start → workbench JS load | `willOpenNewWindow` → `willLoadWorkbenchMain` | 152 | 212 | 237 |
| Workbench JS load + evaluate | `willLoadWorkbenchMain` → `didLoadWorkbenchMain` | 216 | 228 | 262 |
| Workbench main → services start | `didLoadWorkbenchMain` → `willStartWorkbench` | 29 | 38 | 42 |
| Workbench services, contributions, restore | `willStartWorkbench` → `didStartWorkbench` | 382 | 298 | 471 |
| — | |  |  |  |
| · BlockStartup contributions | `willCreateWorkbenchContributions/1` → `didCreateWorkbenchContributions/1` | 10 | 11 | 13 |
| · BlockRestore contributions | `willCreateWorkbenchContributions/2` → `didCreateWorkbenchContributions/2` | 14 | 29 | 17 |
| · Editor restore | `willRestoreEditors` → `didRestoreEditors` | 30 | 145 | 29 |
| Extension scan + registration (renderer) | `willLoadExtensions` → `didLoadExtensions` | 124 | 260 | 173 |
| Extension host: connect to renderer | `extHost/willConnectToRenderer` → `extHost/didConnectToRenderer` | 1 | 2 | 0 |
| Workbench ready → extension host ready | `didStartWorkbench` → `extHost/ready` | 237 | 1,318 | 239 |
| Extension host ready (from process start) | `willLoadMainBundle` → `extHost/ready` | 1,546 | 2,840 | 2,252 |

### Slowest workbench contributions (renderer.log)

VS Code logs a contribution at warn level only when creating it took over 20 ms (BlockStartup/BlockRestore) or 100 ms (later phases). Median ms over the cold runs it appeared in (runs seen / cold runs).

- **FriedLiver**: none above the threshold
- **VS Code (stock)**: none above the threshold
- **FriedLiver + settings-perf**: none above the threshold

## Memory, processes and idle CPU

Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.

| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 12 | 637 [512–641] | 1,751 [1,485–1,821] | 2.61 [2.13–2.65] | 21 [20–24] | 630 / 1,760 |
| VS Code (stock) | 14 | 804 [639–811] | 2,099 [1,720–2,126] | 5.7 [5.45–6.27] | 38 [28–38] | 814 / 2,182 |
| FriedLiver + settings-perf | 11 | 556 [528–593] | 1,594 [1,492–1,605] | 5.51 [5.43–5.91] | 27 [23–34] | 569 / 1,602 |

## Opening a 5 MB file (VS Code family only)

| Arm | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |
|---|---:|---:|---:|
| FriedLiver | 453 | 30 | 423 |
| VS Code (stock) | 646 | 145 | 501 |
| FriedLiver + settings-perf | 629 | 29 | 600 |

## Scenario: slow login shell

`.zshrc` sleeps 1.0 s (as nvm or oh-my-zsh can). Each arm gets its own profile with a probe extension: it activates on `*` and calls `workspace.findFiles`, the extension-host file search that also serves Quick Open. Extension host ready is measured from process start (perf mark). File search is measured from just before `open` (wall clock). Median [min–max] of 3 runs, ms.

| Arm | Ext host ready, fast shell | Ext host ready, slow shell | Δ | First file-search result, fast shell | Slow shell | Δ |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 1,742 [1,695–2,497] | 2,300 [2,251–3,179] | 558 | 2,216 [2,213–3,179] | 2,640 [2,585–3,677] | 424 |
| VS Code (stock) | 3,281 [2,748–4,208] | 2,813 [2,443–3,606] | -468 | 3,909 [3,198–5,255] | 3,475 [2,866–4,282] | -434 |
| FriedLiver + settings-perf | 1,710 [1,617–1,938] | 3,113 [2,450–3,309] | 1,403 | 2,201 [2,070–2,389] | 3,575 [2,866–3,890] | 1,374 |

## Scenario: large repo (microsoft/TypeScript @ d48a5cf89a, 72,631 files)

Median [min–max] of 3 runs.

| Arm | Processes | Footprint (MB) | CPU in the first 60 s after the window (%) | Idle CPU, ready+60→120 s (%) |
|---|---:|---:|---:|---:|
| FriedLiver | 9 | 553 [398–636] | 84 [15–110] | 5.01 [0.48–5.65] |
| VS Code (stock) | 11 | 563 [555–584] | 25 [21–38] | 0.61 [0.46–4.35] |
| FriedLiver + settings-perf | 9 | 548 [388–636] | 74 [14–103] | 2.72 [0.46–4.87] |

## A/B deltas

Δ = arm median − baseline median (negative = the arm is faster or smaller). **better** or **worse** only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point (CPU). Otherwise *noise*. This is one run; the keep rule needs the same verdict in two separate CI runs.

### FriedLiver vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 1,596 | 1,318 | -278 | -17.4 % | 1,487 | 5/5 | noise |
| First window | 1,112 | 924 | -188 | -16.9 % | 716 | 5/5 | noise |
| Extension host ready | 2,840 | 1,546 | -1,294 | -45.6 % | 1,599 | 5/5 | noise |
| Process start → main started | 378 | 146 | -232 | -61.4 % | 342 | 5/5 | noise |
| Main: switches, locale, app ready | 108 | 93 | -15 | -13.9 % | 84 | 5/5 | noise |
| Main services → window opened | 320 | 287 | -33 | -10.3 % | 340 | 5/5 | noise |
| Renderer start → workbench JS load | 212 | 152 | -60 | -28.3 % | 162 | 5/5 | noise |
| Workbench JS load + evaluate | 228 | 216 | -12 | -5.3 % | 280 | 5/5 | noise |
| Workbench main → services start | 38 | 29 | -9 | -23.7 % | 31 | 5/5 | noise |
| Workbench services, contributions, restore | 298 | 382 | +84 | +28.2 % | 506 | 5/5 | noise |
| · BlockStartup contributions | 11 | 10 | -1 | -9.1 % | 18 | 5/5 | noise |
| · BlockRestore contributions | 29 | 14 | -15 | -51.7 % | 30 | 5/5 | noise |
| · Editor restore | 145 | 30 | -115 | -79.3 % | 98 | 5/5 | **better** |
| Idle footprint | 804 | 637 | -168 | -20.8 % | 172 | 3/3 | noise |
| Idle RSS | 2,099 | 1,751 | -348 | -16.6 % | 406 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 5.70 | 2.61 | -3.09 | -54.2 % | 0.82 | 3/3 | **better** |
| CPU, first 60 s after window | 38.33 | 20.58 | -17.75 | -46.3 % | 10.78 | 3/3 | **better** |
| 20 files: footprint | 814 | 630 | -184 | -22.6 % | 30 | 3/3 | **better** |
| Slow shell: extension host ready | 2,813 | 2,300 | -513 | -18.2 % | 1,163 | 3/3 | noise |
| Slow shell: first file-search result | 3,475 | 2,640 | -835 | -24.0 % | 1,416 | 3/3 | noise |
| Fast shell: first file-search result | 3,909 | 2,216 | -1,693 | -43.3 % | 2,057 | 3/3 | noise |
| Large repo: footprint | 563 | 553 | -10 | -1.8 % | 238 | 3/3 | noise |
| Large repo: CPU first 60 s | 24.63 | 84.33 | +59.70 | +242.4 % | 94.95 | 3/3 | noise |
| Large repo: idle CPU | 0.61 | 5.01 | +4.40 | +721.3 % | 5.17 | 3/3 | noise |

### FriedLiver + settings-perf vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 1,596 | 2,020 | +424 | +26.6 % | 1,060 | 5/5 | noise |
| First window | 1,112 | 1,300 | +188 | +16.9 % | 716 | 5/5 | noise |
| Extension host ready | 2,840 | 2,252 | -588 | -20.7 % | 1,565 | 5/5 | noise |
| Process start → main started | 378 | 442 | +64 | +16.9 % | 342 | 5/5 | noise |
| Main: switches, locale, app ready | 108 | 151 | +43 | +39.8 % | 107 | 5/5 | noise |
| Main services → window opened | 320 | 400 | +80 | +25.0 % | 225 | 5/5 | noise |
| Renderer start → workbench JS load | 212 | 237 | +25 | +11.8 % | 185 | 5/5 | noise |
| Workbench JS load + evaluate | 228 | 262 | +34 | +14.9 % | 214 | 5/5 | noise |
| Workbench main → services start | 38 | 42 | +4 | +10.5 % | 24 | 5/5 | noise |
| Workbench services, contributions, restore | 298 | 471 | +173 | +58.1 % | 259 | 5/5 | noise |
| · BlockStartup contributions | 11 | 13 | +2 | +18.2 % | 11 | 5/5 | noise |
| · BlockRestore contributions | 29 | 17 | -12 | -41.4 % | 30 | 5/5 | noise |
| · Editor restore | 145 | 29 | -116 | -80.0 % | 98 | 5/5 | **better** |
| Idle footprint | 804 | 556 | -249 | -30.9 % | 172 | 3/3 | **better** |
| Idle RSS | 2,099 | 1,594 | -505 | -24.1 % | 406 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 5.70 | 5.51 | -0.19 | -3.3 % | 0.82 | 3/3 | noise |
| CPU, first 60 s after window | 38.33 | 26.83 | -11.50 | -30.0 % | 10.99 | 3/3 | **better** |
| 20 files: footprint | 814 | 569 | -245 | -30.1 % | 26 | 3/3 | **better** |
| Slow shell: extension host ready | 2,813 | 3,113 | +300 | +10.7 % | 1,163 | 3/3 | noise |
| Slow shell: first file-search result | 3,475 | 3,575 | +100 | +2.9 % | 1,416 | 3/3 | noise |
| Fast shell: first file-search result | 3,909 | 2,201 | -1,708 | -43.7 % | 2,057 | 3/3 | noise |
| Large repo: footprint | 563 | 548 | -15 | -2.7 % | 248 | 3/3 | noise |
| Large repo: CPU first 60 s | 24.63 | 74.45 | +49.82 | +202.3 % | 88.62 | 3/3 | noise |
| Large repo: idle CPU | 0.61 | 2.72 | +2.11 | +345.9 % | 4.41 | 3/3 | noise |

### FriedLiver + settings-perf vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 1,318 | 2,020 | +702 | +53.3 % | 1,487 | 5/5 | noise |
| First window | 924 | 1,300 | +376 | +40.7 % | 705 | 5/5 | noise |
| Extension host ready | 1,546 | 2,252 | +706 | +45.7 % | 1,599 | 5/5 | noise |
| Process start → main started | 146 | 442 | +296 | +202.7 % | 192 | 5/5 | **worse** |
| Main: switches, locale, app ready | 93 | 151 | +58 | +62.4 % | 107 | 5/5 | noise |
| Main services → window opened | 287 | 400 | +113 | +39.4 % | 340 | 5/5 | noise |
| Renderer start → workbench JS load | 152 | 237 | +85 | +55.9 % | 185 | 5/5 | noise |
| Workbench JS load + evaluate | 216 | 262 | +46 | +21.3 % | 280 | 5/5 | noise |
| Workbench main → services start | 29 | 42 | +13 | +44.8 % | 31 | 5/5 | noise |
| Workbench services, contributions, restore | 382 | 471 | +89 | +23.3 % | 506 | 5/5 | noise |
| · BlockStartup contributions | 10 | 13 | +3 | +30.0 % | 18 | 5/5 | noise |
| · BlockRestore contributions | 14 | 17 | +3 | +21.4 % | 22 | 5/5 | noise |
| · Editor restore | 30 | 29 | -1 | -3.3 % | 31 | 5/5 | noise |
| Idle footprint | 637 | 556 | -81 | -12.7 % | 129 | 3/3 | noise |
| Idle RSS | 1,751 | 1,594 | -157 | -9.0 % | 336 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.61 | 5.51 | +2.90 | +111.1 % | 0.52 | 3/3 | **worse** |
| CPU, first 60 s after window | 20.58 | 26.83 | +6.25 | +30.4 % | 10.99 | 3/3 | noise |
| 20 files: footprint | 630 | 569 | -61 | -9.7 % | 30 | 3/3 | **better** |
| Slow shell: extension host ready | 2,300 | 3,113 | +813 | +35.3 % | 928 | 3/3 | noise |
| Slow shell: first file-search result | 2,640 | 3,575 | +935 | +35.4 % | 1,092 | 3/3 | noise |
| Fast shell: first file-search result | 2,216 | 2,201 | -15 | -0.7 % | 966 | 3/3 | noise |
| Large repo: footprint | 553 | 548 | -5 | -0.9 % | 248 | 3/3 | noise |
| Large repo: CPU first 60 s | 84.33 | 74.45 | -9.88 | -11.7 % | 94.95 | 3/3 | noise |
| Large repo: idle CPU | 5.01 | 2.72 | -2.29 | -45.7 % | 5.17 | 3/3 | noise |


## Method

- **One app at a time.** Every run waits until every process of the previous run is gone, then sleeps 10 s. A run is aborted (app killed) if free memory (`kern.memorystatus_level` × RAM) drops below 2 GB.
- **Throwaway profiles.** Each app gets its own temporary `HOME`, `XDG_*` dirs, `--user-data-dir`, and (VS Code family) `--extensions-dir`, plus `--use-mock-keychain --password-store=basic`. Apps are launched with `open -n -g` from an **empty environment**. Apps launched from an editor's terminal otherwise inherit `ELECTRON_RUN_AS_NODE` and the parent editor's `VSCODE_IPC_HOOK`. The only setting changed from defaults is `update.mode: none` (VS Code family), except in settings-variant arms (below). VS Code family apps also get `--disable-workspace-trust`, so no trust modal appears on a fresh profile.
- **Process attribution.** The process tree is every process whose argv or environment (`ps -E`) contains that run's temp path, plus all of their descendants. This also catches language servers and sidecars that re-parent to launchd.
- **Workspace.** `microsoft/vscode-extension-samples` at a pinned commit (`setup_fixture.sh`), about 1,200 files. The 5 MB file is `big-5mb.txt`, a deterministic concatenation of the repo's `.ts` sources. It is plain text, so no language server parses it.
- **Cold start.** One warm-up launch is discarded. It is the profile's first-ever launch. Then 5 launches run round-robin across apps, so thermal and battery drift hits every app equally. Every launch starts a new process; the disk cache stays warm because a purge needs root.
  - *Workbench ready* (VS Code family only) comes from the product's own `--prof-append-timers` / `--prof-duration-markers`: the duration from `code/willLoadMainBundle` to `code/didStartWorkbench`. The first mark is the main process's Node `timeOrigin`, which is process start. The app writes the marks and exits by itself.
  - *Startup phases* (VS Code family only): every fixed-name perf mark 1.142.0 writes (about 135, listed in `stats.py`) is recorded as its offset from process start, via one `--prof-duration-markers=code/willLoadMainBundle-<mark>` per mark. The phase table is built from those offsets. Main-process and renderer marks are taken when the workbench is restored. Extension-host marks arrive once eager extensions have activated, or after 10 s at the latest. Both happen before the app exits by itself, 15 s after the workbench is ready. Marks with a `-` in their name can't be requested, because the CLI splits on `-`.
  - *Slowest contributions*: each run's `renderer.log` is kept (`results/logs/`). VS Code writes `Creation of workbench contribution '<id>' took N ms` at warn level, which is on by default, but only above 20 ms (BlockStartup/BlockRestore) or 100 ms (later phases). Faster contributions are not listed. The Node compile-cache status line is taken from `main.log` when the product writes one.
  - *First window* (all apps) uses an external clock. It runs from just before `open` until `CGWindowListCopyWindowInfo` lists a normal window (layer 0, at least 300×200) owned by the app (`winwait.swift`). It includes LaunchServices overhead.
- **Memory and CPU.** Three idle runs per arm, round-robin across arms, and the report gives the median [min–max]. Each run opens the workspace (the agent apps open no workspace) and waits 60 s after the first window. It then takes a snapshot: process count, summed RSS, and `footprint` total for the whole tree, which counts shared pages once. *CPU in the first 60 s* is the change in summed `ps` CPU time from the first window to that snapshot. *Idle CPU* is the change over the next 60 s. Both are a percentage of one core. Three more runs per arm open the workspace plus 20 `.ts` files at launch and take a snapshot at ready + 60 s.
- **A/B arms.** An arm is an app, a *settings variant* of an app (`friedliver+settings-perf`: the same binary, with extra settings merged into the throwaway profile's `settings.json`), or *FriedLiver patched*: a build from a FriedLiver-Code release tag, or from a Build FriedLiver workflow run's `friedliver-fork-macos-arm64` artifact. A run artifact is checked against the SHA-256 digest GitHub records when it is uploaded. The workflow inputs `apps`, `variants`, `friedliver_ref` and `scenarios` choose the arms. With the defaults, the arms are VS Code, the FriedLiver release, and FriedLiver + settings-perf.
- **A/B verdict.** For each metric, Δ is the arm median minus the baseline median (VS Code, and the FriedLiver release for the FriedLiver arms). It counts as *better* or *worse* only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point of CPU. Otherwise it is *noise*. Keeping a change needs that verdict in two separate CI runs (CORE-PERF-PLAN §4.4).
- **Scenario: slow shell.** VS Code resolves the user's login-shell environment (`$SHELL -i -l -c`) before it starts the extension host. On a fresh `HOME` this costs almost nothing. With nvm or oh-my-zsh it is commonly 0.3–2 s. Each VS Code and FriedLiver arm gets a separate profile with a probe extension. The probe activates on `*` and calls `workspace.findFiles('**/*.ts', 1)`, the same extension-host file search Quick Open uses. It then writes its timestamps to a file. Three runs use a `.zshrc` that runs `sleep 1.0`, and three use none, interleaved, after one discarded warm-up. The scenario reports extension host ready (perf mark, from process start) and the first file-search result (wall clock from `open`).
- **Scenario: large repo.** `microsoft/TypeScript` v5.6.3 (`d48a5cf8`), shallow, about 70k files, opened by each VS Code and FriedLiver arm three times, round-robin. It uses the same idle method: footprint, CPU in the first 60 s (watcher crawl, git, extension host) and idle CPU after that.
- **5 MB file.** Three launches use `--goto big-5mb.txt:1`. The reported number is the `code/willRestoreEditors → code/didRestoreEditors` duration minus the same mark from the plain cold-start runs. The CLI gives no "file is visible" event after launch, so this is the closest objective proxy.
- **p90** uses the nearest-rank method. With 5 runs, it is the slowest run.

## Caveats

- **No extensions and no sign-in.** Real-world numbers with the owner's extensions, accounts and indexes will be higher, especially for Cursor and Antigravity, whose AI features are idle without an account.
- **Background services.** Cursor and Antigravity IDE start extra processes (language server, agent services) even when signed out. Those count toward their totals because they are part of the cost of running the app.
- **Antigravity (agent app) and OpenCode Desktop are not editors.** They are Electron agent-manager shells. They get no workspace and have no workbench mark, so compare them only on first window, memory, CPU and processes.
- **Network.** Both agent apps run an electron-updater that downloads, and for Antigravity installs on quit, a newer build. Their Chromium network stack is therefore pointed at a dead proxy (`--proxy-server=127.0.0.1:9`). Localhost sidecars and Node/Go child processes still have network access. The VS Code-family apps have full network access with `update.mode: none`.
- **OpenCode ignores `--user-data-dir`.** It pins its own profile path, so it runs only on CI, where the profile is throwaway.
- **Three idle samples per arm.** The spread of three runs is a rough noise estimate, so the A/B verdict also requires a floor (3 %, 10 MB, 1 point of CPU). Agent apps' memory and CPU still come from one 60 s window per run.
- **Probe extension.** The slow-shell runs add one tiny extension. It is the same for every arm, and those runs are compared only with each other, never with the plain cold runs.
- **First open of the large repo.** Each arm's first large-repo run is also the first time its profile sees that folder (no cached workspace state). Round-robin order spreads this effect evenly across arms.
- **Numbers are for this machine only.** See the next section.

## Runner vs laptop

| | GitHub `macos-latest` runner | Owner's laptop |
|---|---|---|
| Hardware | Apple M1 VM, 3 vCPU, 7 GB RAM (virtualised GPU) | MacBook Air M2, 8 cores (4P+4E), 8 GB |
| Power and thermal | AC power; noisy neighbours possible | Battery or AC; fanless, so it throttles under sustained load |
| App sources | Latest official builds, downloaded and verified each run | Whatever is installed in /Applications (versions can lag) |
| Display | Headless VM session; windows are composited without a real panel | Real Retina display |
| Load | Nothing else running | Owner's editor, browser and agents running |

On the runner, absolute timings are slower and memory pressure is higher, because it has fewer cores and a virtualised GPU. The **ranking between apps is the portable result**, not the absolute milliseconds. A single warm-up launch on the laptop (2026-10-17, battery, before the move to CI) is kept in `results/laptop-smoke-2026-10-17/` for orientation only. It measured process start → workbench: FriedLiver 1,714 ms, VS Code 1,979 ms, Cursor 2,902 ms, Antigravity IDE 3,625 ms.

