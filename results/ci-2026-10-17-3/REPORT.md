# Editor benchmark — phases + A/B (2026-10-17, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39059210835

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
| FriedLiver | 3,094 (3,418) | 3,535 (3,803) | 1,807 (1,846) |
| VS Code (stock) | 2,029 (3,645) | 4,352 (7,699) | 1,319 (2,382) |
| FriedLiver patched | 2,857 (3,591) | 3,155 (4,103) | 1,889 (2,358) |

## Startup phases (cold runs, median ms, from the product's own perf marks)

The first seven rows are consecutive and add up to process start → workbench ready (each is a median, so the sum is close to the workbench median, not equal). The rows after the divider break that down or cover the extension host.

| Phase | Marks | FriedLiver | VS Code (stock) | FriedLiver patched |
|---|---|---:|---:|---:|
| Process start → main started | `willLoadMainBundle` → `didStartMain` | 613 | 320 | 650 |
| Main: switches, locale, app ready | `didStartMain` → `mainAppReady` | 176 | 156 | 215 |
| Main services → window opened | `mainAppReady` → `willOpenNewWindow` | 546 | 516 | 522 |
| Renderer start → workbench JS load | `willOpenNewWindow` → `willLoadWorkbenchMain` | 357 | 242 | 375 |
| Workbench JS load + evaluate | `willLoadWorkbenchMain` → `didLoadWorkbenchMain` | 461 | 386 | 374 |
| Workbench main → services start | `didLoadWorkbenchMain` → `willStartWorkbench` | 78 | 55 | 63 |
| Workbench services, contributions, restore | `willStartWorkbench` → `didStartWorkbench` | 760 | 468 | 708 |
| — | |  |  |  |
| · BlockStartup contributions | `willCreateWorkbenchContributions/1` → `didCreateWorkbenchContributions/1` | 23 | 20 | 21 |
| · BlockRestore contributions | `willCreateWorkbenchContributions/2` → `didCreateWorkbenchContributions/2` | 29 | 43 | 31 |
| · Editor restore | `willRestoreEditors` → `didRestoreEditors` | 59 | 214 | 42 |
| Extension scan + registration (renderer) | `willLoadExtensions` → `didLoadExtensions` | 221 | 376 | 278 |
| Extension host: connect to renderer | `extHost/willConnectToRenderer` → `extHost/didConnectToRenderer` | 1 | 5 | 1 |
| Workbench ready → extension host ready | `didStartWorkbench` → `extHost/ready` | 385 | 1,706 | 426 |
| Extension host ready (from process start) | `willLoadMainBundle` → `extHost/ready` | 3,535 | 4,352 | 3,155 |

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
- FriedLiver patched: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-zxqayy2s/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-zxqayy2s/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`

### Launch 1 (fresh profile, empty caches) vs launches 2–6

| Arm | Metric | Launch 1 | Launches 2–6 median [min–max] | Δ |
|---|---|---:|---:|---:|
| FriedLiver | Workbench ready | 6,080 | 3,094 [2,641–3,418] | -2,986 |
| FriedLiver | Extension host ready | 11,171 | 3,535 [3,089–3,803] | -7,636 |
| FriedLiver | Process start → main started | 1,297 | 613 [545–697] | -684 |
| FriedLiver | Workbench ready → extension host ready | 5,091 | 385 [316–465] | -4,706 |
| VS Code (stock) | Workbench ready | 4,625 | 2,029 [1,861–3,645] | -2,596 |
| VS Code (stock) | Extension host ready | 7,792 | 4,352 [3,261–7,699] | -3,440 |
| VS Code (stock) | Process start → main started | 1,010 | 320 [259–813] | -690 |
| VS Code (stock) | Workbench ready → extension host ready | 3,167 | 1,706 [1,400–4,054] | -1,461 |
| FriedLiver patched | Workbench ready | 3,288 | 2,857 [2,704–3,591] | -431 |
| FriedLiver patched | Extension host ready | 5,565 | 3,155 [3,130–4,103] | -2,410 |
| FriedLiver patched | Process start → main started | 598 | 650 [562–691] | +52 |
| FriedLiver patched | Workbench ready → extension host ready | 2,277 | 426 [283–512] | -1,851 |

## Memory, processes and idle CPU

Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.

| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 12 | 631 [496–640] | 1,715 [1,469–1,779] | 2.74 [2.36–2.97] | 26 [21–34] | 654 / 1,747 |
| VS Code (stock) | 14 | 813 [646–817] | 2,093 [1,728–2,122] | 5.71 [5–6.26] | 41 [36–50] | 818 / 2,134 |
| FriedLiver patched | 11 | 560 [529–590] | 1,582 [1,450–1,655] | 6.24 [5.83–6.42] | 30 [25–36] | 587 / 1,598 |

## Opening a 5 MB file (VS Code family only)

| Arm | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |
|---|---:|---:|---:|
| FriedLiver | 840 | 59 | 781 |
| VS Code (stock) | 1,096 | 214 | 882 |
| FriedLiver patched | 869 | 42 | 827 |

## Scenario: slow login shell

`.zshrc` sleeps 1.0 s (as nvm or oh-my-zsh can). Each arm gets its own profile with a probe extension: it activates on `*` and calls `workspace.findFiles`, the extension-host file search that also serves Quick Open. Extension host ready is measured from process start (perf mark). File search is measured from just before `open` (wall clock). Median [min–max] of 3 runs, ms.

| Arm | Ext host ready, fast shell | Ext host ready, slow shell | Δ | First file-search result, fast shell | Slow shell | Δ |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 1,726 [1,421–1,990] | 2,498 [1,867–2,545] | 772 | 2,251 [1,780–2,499] | 2,854 [2,170–2,937] | 603 |
| VS Code (stock) | 3,010 [2,221–3,224] | 3,589 [2,302–3,760] | 579 | 3,675 [2,587–4,253] | 4,274 [2,776–4,711] | 599 |
| FriedLiver patched | 2,080 [1,450–2,860] | 2,150 [1,507–3,632] | 70 | 2,512 [1,851–3,458] | 2,616 [1,824–4,138] | 104 |

## A/B deltas

Δ = arm median − baseline median (negative = the arm is faster or smaller). **better** or **worse** only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point (CPU). Otherwise *noise*. This is one run; the keep rule needs the same verdict in two separate CI runs.

### FriedLiver vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,029 | 3,094 | +1,065 | +52.5 % | 1,784 | 5/5 | noise |
| First window | 1,319 | 1,807 | +488 | +37.0 % | 1,098 | 5/5 | noise |
| Extension host ready | 4,352 | 3,535 | -817 | -18.8 % | 4,438 | 5/5 | noise |
| Process start → main started | 320 | 613 | +293 | +91.6 % | 554 | 5/5 | noise |
| Main: switches, locale, app ready | 156 | 176 | +20 | +12.8 % | 106 | 5/5 | noise |
| Main services → window opened | 516 | 546 | +30 | +5.8 % | 210 | 5/5 | noise |
| Renderer start → workbench JS load | 242 | 357 | +115 | +47.5 % | 230 | 5/5 | noise |
| Workbench JS load + evaluate | 386 | 461 | +75 | +19.4 % | 340 | 5/5 | noise |
| Workbench main → services start | 55 | 78 | +23 | +41.8 % | 74 | 5/5 | noise |
| Workbench services, contributions, restore | 468 | 760 | +292 | +62.4 % | 440 | 5/5 | noise |
| · BlockStartup contributions | 20 | 23 | +3 | +15.0 % | 26 | 5/5 | noise |
| · BlockRestore contributions | 43 | 29 | -14 | -32.6 % | 65 | 5/5 | noise |
| · Editor restore | 214 | 59 | -155 | -72.4 % | 165 | 5/5 | noise |
| Idle footprint | 813 | 631 | -182 | -22.4 % | 170 | 3/3 | **better** |
| Idle RSS | 2,093 | 1,715 | -378 | -18.1 % | 393 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 5.71 | 2.74 | -2.97 | -52.0 % | 1.26 | 3/3 | **better** |
| CPU, first 60 s after window | 41.06 | 26.03 | -15.03 | -36.6 % | 13.64 | 3/3 | **better** |
| 20 files: footprint | 818 | 654 | -164 | -20.0 % | 22 | 3/3 | **better** |
| Slow shell: extension host ready | 3,589 | 2,498 | -1,091 | -30.4 % | 1,458 | 3/3 | noise |
| Slow shell: first file-search result | 4,274 | 2,854 | -1,420 | -33.2 % | 1,935 | 3/3 | noise |
| Fast shell: first file-search result | 3,675 | 2,251 | -1,424 | -38.7 % | 1,666 | 3/3 | noise |

### FriedLiver patched vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,029 | 2,857 | +828 | +40.8 % | 1,784 | 5/5 | noise |
| First window | 1,319 | 1,889 | +570 | +43.2 % | 1,098 | 5/5 | noise |
| Extension host ready | 4,352 | 3,155 | -1,197 | -27.5 % | 4,438 | 5/5 | noise |
| Process start → main started | 320 | 650 | +330 | +103.1 % | 554 | 5/5 | noise |
| Main: switches, locale, app ready | 156 | 215 | +59 | +37.8 % | 106 | 5/5 | noise |
| Main services → window opened | 516 | 522 | +6 | +1.2 % | 218 | 5/5 | noise |
| Renderer start → workbench JS load | 242 | 375 | +133 | +55.0 % | 230 | 5/5 | noise |
| Workbench JS load + evaluate | 386 | 374 | -12 | -3.1 % | 340 | 5/5 | noise |
| Workbench main → services start | 55 | 63 | +8 | +14.5 % | 74 | 5/5 | noise |
| Workbench services, contributions, restore | 468 | 708 | +240 | +51.3 % | 345 | 5/5 | noise |
| · BlockStartup contributions | 20 | 21 | +1 | +5.0 % | 26 | 5/5 | noise |
| · BlockRestore contributions | 43 | 31 | -12 | -27.9 % | 65 | 5/5 | noise |
| · Editor restore | 214 | 42 | -172 | -80.4 % | 165 | 5/5 | **better** |
| Idle footprint | 813 | 560 | -254 | -31.2 % | 170 | 3/3 | **better** |
| Idle RSS | 2,093 | 1,582 | -510 | -24.4 % | 393 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 5.71 | 6.24 | +0.53 | +9.3 % | 1.26 | 3/3 | noise |
| CPU, first 60 s after window | 41.06 | 29.85 | -11.21 | -27.3 % | 13.64 | 3/3 | noise |
| 20 files: footprint | 818 | 587 | -231 | -28.3 % | 22 | 3/3 | **better** |
| Slow shell: extension host ready | 3,589 | 2,150 | -1,439 | -40.1 % | 2,125 | 3/3 | noise |
| Slow shell: first file-search result | 4,274 | 2,616 | -1,658 | -38.8 % | 2,314 | 3/3 | noise |
| Fast shell: first file-search result | 3,675 | 2,512 | -1,163 | -31.6 % | 1,666 | 3/3 | noise |

### FriedLiver patched vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 3,094 | 2,857 | -237 | -7.7 % | 887 | 5/5 | noise |
| First window | 1,807 | 1,889 | +82 | +4.5 % | 675 | 5/5 | noise |
| Extension host ready | 3,535 | 3,155 | -380 | -10.7 % | 973 | 5/5 | noise |
| Process start → main started | 613 | 650 | +37 | +6.0 % | 152 | 5/5 | noise |
| Main: switches, locale, app ready | 176 | 215 | +39 | +22.2 % | 63 | 5/5 | noise |
| Main services → window opened | 546 | 522 | -24 | -4.4 % | 218 | 5/5 | noise |
| Renderer start → workbench JS load | 357 | 375 | +18 | +5.0 % | 119 | 5/5 | noise |
| Workbench JS load + evaluate | 461 | 374 | -87 | -18.9 % | 224 | 5/5 | noise |
| Workbench main → services start | 78 | 63 | -15 | -19.2 % | 38 | 5/5 | noise |
| Workbench services, contributions, restore | 760 | 708 | -52 | -6.8 % | 440 | 5/5 | noise |
| · BlockStartup contributions | 23 | 21 | -2 | -8.7 % | 17 | 5/5 | noise |
| · BlockRestore contributions | 29 | 31 | +2 | +6.9 % | 16 | 5/5 | noise |
| · Editor restore | 59 | 42 | -17 | -28.8 % | 36 | 5/5 | noise |
| Idle footprint | 631 | 560 | -71 | -11.3 % | 144 | 3/3 | noise |
| Idle RSS | 1,715 | 1,582 | -133 | -7.7 % | 310 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.74 | 6.24 | +3.50 | +127.7 % | 0.61 | 3/3 | **worse** |
| CPU, first 60 s after window | 26.03 | 29.85 | +3.82 | +14.7 % | 13.21 | 3/3 | noise |
| 20 files: footprint | 654 | 587 | -67 | -10.3 % | 22 | 3/3 | **better** |
| Slow shell: extension host ready | 2,498 | 2,150 | -348 | -13.9 % | 2,125 | 3/3 | noise |
| Slow shell: first file-search result | 2,854 | 2,616 | -238 | -8.3 % | 2,314 | 3/3 | noise |
| Fast shell: first file-search result | 2,251 | 2,512 | +261 | +11.6 % | 1,607 | 3/3 | noise |


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

