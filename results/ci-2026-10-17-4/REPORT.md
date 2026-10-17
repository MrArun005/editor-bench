# Editor benchmark — phases + A/B (2026-10-17, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39062025866

Scenarios: slow-shell.

## Arms

| Arm | Version | VS Code base | Install size (MB) | Source / verification |
|---|---|---|---:|---|
| FriedLiver | 1.142.0 | 1.142.0 | 563 | sha256 verified; codesign valid |
| VS Code (stock) | 1.142.0 | 1.142.0 | 865 | vendor publishes no hash; codesign valid |
| FriedLiver patched | 1.142.0 | 1.142.0 | 518 | run 39055910922: perf/core@3f198b5401 (workflow_dispatch); trusted run; artifact sha256 digest verified; codesign valid |

## Cold start (1 warm-up discarded, then 5 runs, round-robin across arms)

| Arm | Launch → workbench ready, median (p90) ms | Launch → extension host ready, median (p90) ms | Launch → first window, median (p90) ms |
|---|---:|---:|---:|
| FriedLiver | 2,462 (3,315) | 2,737 (3,934) | 1,582 (1,977) |
| VS Code (stock) | 2,089 (3,484) | 3,689 (6,555) | 1,417 (2,524) |
| FriedLiver patched | 2,334 (3,246) | 2,751 (3,836) | 1,481 (1,885) |

## Startup phases (cold runs, median ms, from the product's own perf marks)

The first seven rows are consecutive and add up to process start → workbench ready (each is a median, so the sum is close to the workbench median, not equal). The rows after the divider break that down or cover the extension host.

| Phase | Marks | FriedLiver | VS Code (stock) | FriedLiver patched |
|---|---|---:|---:|---:|
| Process start → main started | `willLoadMainBundle` → `didStartMain` | 540 | 464 | 489 |
| Main: switches, locale, app ready | `didStartMain` → `mainAppReady` | 189 | 135 | 168 |
| Main services → window opened | `mainAppReady` → `willOpenNewWindow` | 449 | 411 | 413 |
| Renderer start → workbench JS load | `willOpenNewWindow` → `willLoadWorkbenchMain` | 337 | 274 | 319 |
| Workbench JS load + evaluate | `willLoadWorkbenchMain` → `didLoadWorkbenchMain` | 363 | 396 | 332 |
| Workbench main → services start | `didLoadWorkbenchMain` → `willStartWorkbench` | 60 | 43 | 47 |
| Workbench services, contributions, restore | `willStartWorkbench` → `didStartWorkbench` | 678 | 434 | 601 |
| — | |  |  |  |
| · BlockStartup contributions | `willCreateWorkbenchContributions/1` → `didCreateWorkbenchContributions/1` | 19 | 14 | 14 |
| · BlockRestore contributions | `willCreateWorkbenchContributions/2` → `didCreateWorkbenchContributions/2` | 19 | 52 | 17 |
| · Editor restore | `willRestoreEditors` → `didRestoreEditors` | 45 | 187 | 43 |
| Extension scan + registration (renderer) | `willLoadExtensions` → `didLoadExtensions` | 188 | 370 | 206 |
| Extension host: connect to renderer | `extHost/willConnectToRenderer` → `extHost/didConnectToRenderer` | 0 | 8 | 1 |
| Workbench ready → extension host ready | `didStartWorkbench` → `extHost/ready` | 329 | 1,784 | 359 |
| Extension host ready (from process start) | `willLoadMainBundle` → `extHost/ready` | 2,737 | 3,689 | 2,751 |

### Slowest workbench contributions (renderer.log)

VS Code logs a contribution at warn level only when creating it took over 20 ms (BlockStartup/BlockRestore) or 100 ms (later phases). Median ms over the cold runs it appeared in (runs seen / cold runs).

- **FriedLiver**: none above the threshold
- **VS Code (stock)**: none above the threshold
- **FriedLiver patched**: none above the threshold

### Node compile cache

Status per process, from the `[node-compile-cache]` line each process writes to its log; folder size of `CachedData/<commit>/node` after each launch (launch 1 = warm-up, 2–6 = the cold runs).

| Arm | Status per process | Folder KB after launches 1…6 |
|---|---|---|
| FriedLiver | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 → 0 → 0 → 0 → 0 → 0 |
| VS Code (stock) | agent-host: packaged cache inactive: disabled; extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 → 0 → 0 → 0 → 0 → 0 |
| FriedLiver patched | extension-host: packaged cache inactive: enabled; main: packaged cache inactive: disabled | 4406 → 4469 → 4532 → 4595 → 4658 → 4721 |

- FriedLiver: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- VS Code (stock): `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/vscode/Visual Studio Code.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver patched: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-b538ochc/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-b538ochc/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`

### Launch 1 (fresh profile, empty caches) vs launches 2–6

| Arm | Metric | Launch 1 | Launches 2–6 median [min–max] | Δ |
|---|---|---:|---:|---:|
| FriedLiver | Workbench ready | 2,782 | 2,462 [2,315–3,315] | -320 |
| FriedLiver | Extension host ready | 3,953 | 2,737 [2,607–3,934] | -1,216 |
| FriedLiver | Process start → main started | 526 | 540 [430–677] | +14 |
| FriedLiver | Workbench ready → extension host ready | 1,171 | 329 [251–619] | -842 |
| VS Code (stock) | Workbench ready | 2,098 | 2,089 [1,900–3,484] | -9 |
| VS Code (stock) | Extension host ready | 4,082 | 3,689 [3,049–6,555] | -393 |
| VS Code (stock) | Process start → main started | 467 | 464 [268–1,087] | -3 |
| VS Code (stock) | Workbench ready → extension host ready | 1,984 | 1,784 [1,147–3,071] | -200 |
| FriedLiver patched | Workbench ready | 1,861 | 2,334 [2,236–3,246] | +473 |
| FriedLiver patched | Extension host ready | 3,257 | 2,751 [2,546–3,836] | -506 |
| FriedLiver patched | Process start → main started | 330 | 489 [429–653] | +159 |
| FriedLiver patched | Workbench ready → extension host ready | 1,396 | 359 [310–590] | -1,037 |

## Memory, processes and idle CPU

Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.

| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 12 | 634 [516–635] | 1,745 [1,470–1,772] | 2.35 [2.31–2.67] | 29 [26–32] | 649 / 1,763 |
| VS Code (stock) | 14 | 811 [647–813] | 2,086 [1,862–2,152] | 5.64 [5.26–6.17] | 40 [35–42] | 800 / 2,083 |
| FriedLiver patched | 11 | 566 [514–570] | 1,614 [1,463–1,656] | 5.42 [5.35–5.56] | 30 [27–30] | 570 / 1,622 |

## Opening a 5 MB file (VS Code family only)

| Arm | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |
|---|---:|---:|---:|
| FriedLiver | 800 | 45 | 755 |
| VS Code (stock) | 1,186 | 187 | 999 |
| FriedLiver patched | 614 | 43 | 571 |

## Scenario: slow login shell

`.zshrc` sleeps 3 s (as nvm or oh-my-zsh can). Each arm gets its own profile with a probe extension: it activates on `*` and calls `workspace.findFiles`, the extension-host file search that also serves Quick Open. Extension host ready is measured from process start (perf mark). File search is measured from just before `open` (wall clock). Median [min–max] of 3 runs, ms.

| Arm | Ext host ready, fast shell | Ext host ready, slow shell | Δ | First file-search result, fast shell | Slow shell | Δ |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 2,447 [1,914–2,508] | 4,082 [3,853–4,474] | 1,635 | 3,166 [2,390–3,289] | 4,472 [4,248–5,315] | 1,306 |
| VS Code (stock) | 4,453 [2,102–4,863] | 4,507 [4,140–4,799] | 54 | 5,265 [2,746–5,727] | 5,084 [4,604–5,446] | -181 |
| FriedLiver patched | 2,042 [1,954–2,185] | 1,964 [1,832–3,094] | -78 | 2,554 [2,372–2,950] | 2,402 [2,187–3,554] | -152 |

## A/B deltas

Δ = arm median − baseline median (negative = the arm is faster or smaller). **better** or **worse** only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point (CPU). Otherwise *noise*. This is one run; the keep rule needs the same verdict in two separate CI runs.

### FriedLiver vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,089 | 2,462 | +373 | +17.9 % | 1,584 | 5/5 | noise |
| First window | 1,417 | 1,582 | +165 | +11.6 % | 1,429 | 5/5 | noise |
| Extension host ready | 3,689 | 2,737 | -952 | -25.8 % | 3,506 | 5/5 | noise |
| Process start → main started | 464 | 540 | +76 | +16.4 % | 819 | 5/5 | noise |
| Main: switches, locale, app ready | 135 | 189 | +54 | +40.0 % | 169 | 5/5 | noise |
| Main services → window opened | 411 | 449 | +38 | +9.2 % | 273 | 5/5 | noise |
| Renderer start → workbench JS load | 274 | 337 | +63 | +23.0 % | 184 | 5/5 | noise |
| Workbench JS load + evaluate | 396 | 363 | -33 | -8.3 % | 161 | 5/5 | noise |
| Workbench main → services start | 43 | 60 | +17 | +39.5 % | 32 | 5/5 | noise |
| Workbench services, contributions, restore | 434 | 678 | +244 | +56.2 % | 412 | 5/5 | noise |
| · BlockStartup contributions | 14 | 19 | +5 | +35.7 % | 9 | 5/5 | noise |
| · BlockRestore contributions | 52 | 19 | -33 | -63.5 % | 23 | 5/5 | **better** |
| · Editor restore | 187 | 45 | -142 | -75.9 % | 90 | 5/5 | **better** |
| Idle footprint | 811 | 634 | -176 | -21.7 % | 166 | 3/3 | **better** |
| Idle RSS | 2,086 | 1,745 | -340 | -16.3 % | 302 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 5.64 | 2.35 | -3.29 | -58.3 % | 0.91 | 3/3 | **better** |
| CPU, first 60 s after window | 40.23 | 29.43 | -10.80 | -26.8 % | 7.32 | 3/3 | **better** |
| 20 files: footprint | 800 | 649 | -151 | -18.9 % | 34 | 3/3 | **better** |
| Slow shell: extension host ready | 4,507 | 4,082 | -425 | -9.4 % | 659 | 3/3 | noise |
| Slow shell: first file-search result | 5,084 | 4,472 | -612 | -12.0 % | 1,067 | 3/3 | noise |
| Fast shell: first file-search result | 5,265 | 3,166 | -2,099 | -39.9 % | 2,981 | 3/3 | noise |

### FriedLiver patched vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,089 | 2,334 | +245 | +11.7 % | 1,584 | 5/5 | noise |
| First window | 1,417 | 1,481 | +64 | +4.5 % | 1,429 | 5/5 | noise |
| Extension host ready | 3,689 | 2,751 | -938 | -25.4 % | 3,506 | 5/5 | noise |
| Process start → main started | 464 | 489 | +25 | +5.4 % | 819 | 5/5 | noise |
| Main: switches, locale, app ready | 135 | 168 | +33 | +24.4 % | 169 | 5/5 | noise |
| Main services → window opened | 411 | 413 | +2 | +0.5 % | 273 | 5/5 | noise |
| Renderer start → workbench JS load | 274 | 319 | +45 | +16.4 % | 184 | 5/5 | noise |
| Workbench JS load + evaluate | 396 | 332 | -64 | -16.2 % | 197 | 5/5 | noise |
| Workbench main → services start | 43 | 47 | +4 | +9.3 % | 37 | 5/5 | noise |
| Workbench services, contributions, restore | 434 | 601 | +167 | +38.5 % | 324 | 5/5 | noise |
| · BlockStartup contributions | 14 | 14 | +0 | +0.0 % | 10 | 5/5 | noise |
| · BlockRestore contributions | 52 | 17 | -35 | -67.3 % | 23 | 5/5 | **better** |
| · Editor restore | 187 | 43 | -144 | -77.0 % | 90 | 5/5 | **better** |
| Idle footprint | 811 | 566 | -245 | -30.2 % | 166 | 3/3 | **better** |
| Idle RSS | 2,086 | 1,614 | -471 | -22.6 % | 291 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 5.64 | 5.42 | -0.22 | -3.9 % | 0.91 | 3/3 | noise |
| CPU, first 60 s after window | 40.23 | 30.05 | -10.18 | -25.3 % | 7.32 | 3/3 | **better** |
| 20 files: footprint | 800 | 570 | -230 | -28.7 % | 34 | 3/3 | **better** |
| Slow shell: extension host ready | 4,507 | 1,964 | -2,543 | -56.4 % | 1,262 | 3/3 | **better** |
| Slow shell: first file-search result | 5,084 | 2,402 | -2,682 | -52.8 % | 1,367 | 3/3 | **better** |
| Fast shell: first file-search result | 5,265 | 2,554 | -2,711 | -51.5 % | 2,981 | 3/3 | noise |

### FriedLiver patched vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,462 | 2,334 | -128 | -5.2 % | 1,010 | 5/5 | noise |
| First window | 1,582 | 1,481 | -101 | -6.4 % | 643 | 5/5 | noise |
| Extension host ready | 2,737 | 2,751 | +14 | +0.5 % | 1,327 | 5/5 | noise |
| Process start → main started | 540 | 489 | -51 | -9.4 % | 247 | 5/5 | noise |
| Main: switches, locale, app ready | 189 | 168 | -21 | -11.1 % | 68 | 5/5 | noise |
| Main services → window opened | 449 | 413 | -36 | -8.0 % | 198 | 5/5 | noise |
| Renderer start → workbench JS load | 337 | 319 | -18 | -5.3 % | 103 | 5/5 | noise |
| Workbench JS load + evaluate | 363 | 332 | -31 | -8.5 % | 197 | 5/5 | noise |
| Workbench main → services start | 60 | 47 | -13 | -21.7 % | 37 | 5/5 | noise |
| Workbench services, contributions, restore | 678 | 601 | -77 | -11.4 % | 412 | 5/5 | noise |
| · BlockStartup contributions | 19 | 14 | -5 | -26.3 % | 10 | 5/5 | noise |
| · BlockRestore contributions | 19 | 17 | -2 | -10.5 % | 22 | 5/5 | noise |
| · Editor restore | 45 | 43 | -2 | -4.4 % | 49 | 5/5 | noise |
| Idle footprint | 634 | 566 | -68 | -10.8 % | 120 | 3/3 | noise |
| Idle RSS | 1,745 | 1,614 | -131 | -7.5 % | 302 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.35 | 5.42 | +3.07 | +130.6 % | 0.36 | 3/3 | **worse** |
| CPU, first 60 s after window | 29.43 | 30.05 | +0.62 | +2.1 % | 6.28 | 3/3 | noise |
| 20 files: footprint | 649 | 570 | -79 | -12.1 % | 25 | 3/3 | **better** |
| Slow shell: extension host ready | 4,082 | 1,964 | -2,118 | -51.9 % | 1,262 | 3/3 | **better** |
| Slow shell: first file-search result | 4,472 | 2,402 | -2,070 | -46.3 % | 1,367 | 3/3 | **better** |
| Fast shell: first file-search result | 3,166 | 2,554 | -612 | -19.3 % | 899 | 3/3 | noise |


## Method

- **One app at a time.** Every run waits until every process of the previous run is gone, then sleeps 10 s. A run is aborted (app killed) if free memory (`kern.memorystatus_level` × RAM) drops below 2 GB.
- **Throwaway profiles.** Each app gets its own temporary `HOME`, `XDG_*` dirs, `--user-data-dir`, and (VS Code family) `--extensions-dir`, plus `--use-mock-keychain --password-store=basic`. Apps are launched with `open -n -g` from an **empty environment**. Apps launched from an editor's terminal otherwise inherit `ELECTRON_RUN_AS_NODE` and the parent editor's `VSCODE_IPC_HOOK`. The only setting changed from defaults is `update.mode: none` (VS Code family), except in settings-variant arms (below). VS Code family apps also get `--disable-workspace-trust`, so no trust modal appears on a fresh profile.
- **Process attribution.** The process tree is every process whose argv or environment (`ps -E`) contains that run's temp path, plus all of their descendants. This also catches language servers and sidecars that re-parent to launchd.
- **Workspace.** `microsoft/vscode-extension-samples` at a pinned commit (`setup_fixture.sh`), about 1,200 files. The 5 MB file is `big-5mb.txt`, a deterministic concatenation of the repo's `.ts` sources. It is plain text, so no language server parses it.
- **Cold start.** One warm-up launch is discarded. It is the profile's first-ever launch. Then 5 launches run round-robin across apps, so thermal and battery drift hits every app equally. Every launch starts a new process; the disk cache stays warm because a purge needs root.
  - *Workbench ready* (VS Code family only) comes from the product's own `--prof-append-timers` / `--prof-duration-markers`: the duration from `code/willLoadMainBundle` to `code/didStartWorkbench`. The first mark is the main process's Node `timeOrigin`, which is process start. The app writes the marks and exits by itself.
  - *Startup phases* (VS Code family only): every fixed-name perf mark 1.142.0 writes (about 135, listed in `stats.py`) is recorded as its offset from process start, via one `--prof-duration-markers=code/willLoadMainBundle-<mark>` per mark. The phase table is built from those offsets. Main-process and renderer marks are taken when the workbench is restored. Extension-host marks arrive once eager extensions have activated, or after 10 s at the latest. Both happen before the app exits by itself, 15 s after the workbench is ready. Marks with a `-` in their name can't be requested, because the CLI splits on `-`.
  - *Slowest contributions*: each run's `renderer.log` is kept (`results/logs/`). VS Code writes `Creation of workbench contribution '<id>' took N ms` at warn level, which is on by default, but only above 20 ms (BlockStartup/BlockRestore) or 100 ms (later phases). Faster contributions are not listed. Every `[node-compile-cache] <process>: … (status: …)` line from the run's logs (main, shared process, pty host, extension host) is recorded. So is the size of `CachedData/<commit>/node` after every run, which is where FriedLiver's writable compile cache lives. The report sets launch 1 (the warm-up, with every cache empty) against launches 2–6 (the five cold runs).
  - *First window* (all apps) uses an external clock. It runs from just before `open` until `CGWindowListCopyWindowInfo` lists a normal window (layer 0, at least 300×200) owned by the app (`winwait.swift`). It includes LaunchServices overhead.
- **Memory and CPU.** Three idle runs per arm, round-robin across arms, and the report gives the median [min–max]. Each run opens the workspace (the agent apps open no workspace) and waits 60 s after the first window. It then takes a snapshot: process count, summed RSS, and `footprint` total for the whole tree, which counts shared pages once. *CPU in the first 60 s* is the change in summed `ps` CPU time from the first window to that snapshot. *Idle CPU* is the change over the next 60 s. Both are a percentage of one core. Three more runs per arm open the workspace plus 20 `.ts` files at launch and take a snapshot at ready + 60 s.
- **A/B arms.** An arm is an app, a *settings variant* of an app (`friedliver+settings-perf`: the same binary, with extra settings merged into the throwaway profile's `settings.json`), or *FriedLiver patched*: a build from a FriedLiver-Code release tag, or from a Build FriedLiver workflow run's `friedliver-fork-macos-arm64` artifact. A run artifact is used only if the run is a Build FriedLiver (`build.yml`) run on `MrArun005/FriedLiver-Code` itself (no forks), triggered by a push or a manual dispatch, from `main`, `perf/*`, `release/*`, `ui/*` or a `v*` tag. It is also checked against the SHA-256 digest GitHub records at upload. The GitHub token is available to the download step only, never to the step that runs the apps. The workflow inputs `apps`, `variants`, `friedliver_ref` and `scenarios` choose the arms. With the defaults, the arms are VS Code, the FriedLiver release, and FriedLiver + settings-perf.
- **A/B verdict.** For each metric, Δ is the arm median minus the baseline median (VS Code, and the FriedLiver release for the FriedLiver arms). It counts as *better* or *worse* only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point of CPU. Otherwise it is *noise*. Keeping a change needs that verdict in two separate CI runs (CORE-PERF-PLAN §4.4).
- **Scenario: slow shell.** VS Code resolves the user's login-shell environment (`$SHELL -i -l -c`) before it starts the extension host. On a fresh `HOME` this costs almost nothing. With nvm or oh-my-zsh it is commonly 0.3–2 s. Each VS Code and FriedLiver arm gets a separate profile with a probe extension. The probe activates on `*` and calls `workspace.findFiles('**/*.ts', 1)`, the same extension-host file search Quick Open uses. It then writes its timestamps to a file. Three runs use a `.zshrc` that runs `sleep <shell_sleep>` (workflow input, default 1.0 s), and three use none, interleaved, after one discarded warm-up. The main process starts resolving the shell right after the first window opens, so a shell that is faster than the gap from window open to extension-host start (about 1–1.5 s on the runner) is hidden. Use `shell_sleep` 3 or more to see the wait. The scenario reports extension host ready (perf mark, from process start) and the first file-search result (wall clock from `open`).
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

