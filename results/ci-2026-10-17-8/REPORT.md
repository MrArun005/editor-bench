# Editor benchmark — phases + A/B (2026-10-18, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39086017877

Scenarios: slow-shell.

## Arms

| Arm | Version | VS Code base | Install size (MB) | Source / verification |
|---|---|---|---:|---|
| FriedLiver | 1.142.0 | 1.142.0 | 570 | sha256 verified; codesign valid |
| VS Code (stock) | 1.142.0 | 1.142.0 | 865 | vendor publishes no hash; codesign valid |
| FriedLiver patched | 1.142.0 | 1.142.0 | 518 | run 39085377230: perf/core@cc94be1202 (workflow_dispatch); trusted run; artifact sha256 digest verified; codesign valid |

## Cold start (1 warm-up discarded, then 5 runs, round-robin across arms)

| Arm | Launch → workbench ready, median (p90) ms | Launch → extension host ready, median (p90) ms | Launch → first window, median (p90) ms |
|---|---:|---:|---:|
| FriedLiver | 2,353 (2,988) | 2,729 (3,439) | 1,507 (1,804) |
| VS Code (stock) | 1,708 (2,601) | 3,181 (5,649) | 983 (1,607) |
| FriedLiver patched | 2,869 (3,390) | 3,222 (3,911) | 1,876 (1,950) |

## Startup phases (cold runs, median ms, from the product's own perf marks)

The first seven rows are consecutive and add up to process start → workbench ready (each is a median, so the sum is close to the workbench median, not equal). The rows after the divider break that down or cover the extension host.

| Phase | Marks | FriedLiver | VS Code (stock) | FriedLiver patched |
|---|---|---:|---:|---:|
| Process start → main started | `willLoadMainBundle` → `didStartMain` | 453 | 271 | 626 |
| Main: switches, locale, app ready | `didStartMain` → `mainAppReady` | 150 | 111 | 187 |
| Main services → window opened | `mainAppReady` → `willOpenNewWindow` | 433 | 382 | 564 |
| Renderer start → workbench JS load | `willOpenNewWindow` → `willLoadWorkbenchMain` | 311 | 205 | 342 |
| Workbench JS load + evaluate | `willLoadWorkbenchMain` → `didLoadWorkbenchMain` | 301 | 305 | 334 |
| Workbench main → services start | `didLoadWorkbenchMain` → `willStartWorkbench` | 49 | 39 | 64 |
| Workbench services, contributions, restore | `willStartWorkbench` → `didStartWorkbench` | 638 | 464 | 613 |
| — | |  |  |  |
| · BlockStartup contributions | `willCreateWorkbenchContributions/1` → `didCreateWorkbenchContributions/1` | 17 | 15 | 19 |
| · BlockRestore contributions | `willCreateWorkbenchContributions/2` → `didCreateWorkbenchContributions/2` | 21 | 32 | 19 |
| · Editor restore | `willRestoreEditors` → `didRestoreEditors` | 46 | 228 | 32 |
| Extension scan + registration (renderer) | `willLoadExtensions` → `didLoadExtensions` | 187 | 347 | 200 |
| Extension host: connect to renderer | `extHost/willConnectToRenderer` → `extHost/didConnectToRenderer` | 1 | 3 | 1 |
| Workbench ready → extension host ready | `didStartWorkbench` → `extHost/ready` | 355 | 1,504 | 323 |
| Extension host ready (from process start) | `willLoadMainBundle` → `extHost/ready` | 2,729 | 3,181 | 3,222 |

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
- FriedLiver patched: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-u2lf9ckr/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-u2lf9ckr/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`

### Launch 1 (fresh profile, empty caches) vs launches 2–6

| Arm | Metric | Launch 1 | Launches 2–6 median [min–max] | Δ |
|---|---|---:|---:|---:|
| FriedLiver | Workbench ready | 3,700 | 2,353 [2,039–2,988] | -1,347 |
| FriedLiver | Extension host ready | 6,194 | 2,729 [2,254–3,439] | -3,465 |
| FriedLiver | Process start → main started | 733 | 453 [287–607] | -280 |
| FriedLiver | Workbench ready → extension host ready | 2,494 | 355 [215–451] | -2,139 |
| VS Code (stock) | Workbench ready | 2,624 | 1,708 [1,386–2,601] | -916 |
| VS Code (stock) | Extension host ready | 4,737 | 3,181 [2,874–5,649] | -1,556 |
| VS Code (stock) | Process start → main started | 502 | 271 [195–338] | -231 |
| VS Code (stock) | Workbench ready → extension host ready | 2,113 | 1,504 [1,375–3,048] | -609 |
| FriedLiver patched | Workbench ready | 2,399 | 2,869 [1,847–3,390] | +470 |
| FriedLiver patched | Extension host ready | 3,857 | 3,222 [2,081–3,911] | -635 |
| FriedLiver patched | Process start → main started | 542 | 626 [404–662] | +84 |
| FriedLiver patched | Workbench ready → extension host ready | 1,458 | 323 [234–521] | -1,135 |

## Memory, processes and idle CPU

Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.

| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 12 | 641 [516–642] | 1,759 [1,495–1,814] | 2.04 [1.38–2.58] | 22 [19–37] | 638 / 1,767 |
| VS Code (stock) | 14 | 807 [648–811] | 2,063 [1,717–2,143] | 4.91 [4.09–5.1] | 35 [26–45] | 808 / 2,133 |
| FriedLiver patched | 11 | 556 [514–577] | 1,597 [1,474–1,631] | 1.93 [1.47–1.96] | 26 [18–32] | 556 / 1,599 |

### Idle CPU by process (% of one core, median of the idle runs)

| Arm | Processes, highest first |
|---|---|
| FriedLiver | gpu 0.82, renderer 0.67, tsserver 0.39, main 0.1 |
| VS Code (stock) | renderer 2.43, gpu 1.82, tsserver 0.3, main 0.1, agentHostMain 0.05 |
| FriedLiver patched | gpu 0.81, renderer 0.66, tsserver 0.16, main 0.12 |

## Opening a 5 MB file (VS Code family only)

| Arm | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |
|---|---:|---:|---:|
| FriedLiver | 691 | 46 | 645 |
| VS Code (stock) | 785 | 228 | 557 |
| FriedLiver patched | 576 | 32 | 544 |

## Scenario: slow login shell

`.zshrc` sleeps 3 s (as nvm or oh-my-zsh can). Each arm gets its own profile with a probe extension: it activates on `*` and calls `workspace.findFiles`, the extension-host file search that also serves Quick Open. Extension host ready is measured from process start (perf mark). File search is measured from just before `open` (wall clock). Median [min–max] of 3 runs, ms.

| Arm | Ext host ready, fast shell | Ext host ready, slow shell | Δ | First file-search result, fast shell | Slow shell | Δ |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 1,620 [1,614–1,620] | 3,910 [3,774–3,944] | 2,290 | 2,032 [2,028–2,064] | 4,254 [4,046–4,295] | 2,222 |
| VS Code (stock) | 2,572 [2,516–2,575] | 4,128 [4,012–4,129] | 1,556 | 3,029 [3,015–3,125] | 4,591 [4,425–4,637] | 1,562 |
| FriedLiver patched | 2,025 [1,624–2,462] | 1,444 [1,373–2,424] | -581 | 2,447 [2,060–3,393] | 1,795 [1,677–3,419] | -652 |

## A/B deltas

Δ = arm median − baseline median (negative = the arm is faster or smaller). **better** or **worse** only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point (CPU). Otherwise *noise*. This is one run; the keep rule needs the same verdict in two separate CI runs.

### FriedLiver vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 1,708 | 2,353 | +645 | +37.8 % | 1,215 | 5/5 | noise |
| First window | 983 | 1,507 | +524 | +53.3 % | 671 | 5/5 | noise |
| Extension host ready | 3,181 | 2,729 | -452 | -14.2 % | 2,775 | 5/5 | noise |
| Process start → main started | 271 | 453 | +182 | +67.2 % | 320 | 5/5 | noise |
| Main: switches, locale, app ready | 111 | 150 | +39 | +35.1 % | 95 | 5/5 | noise |
| Main services → window opened | 382 | 433 | +51 | +13.4 % | 244 | 5/5 | noise |
| Renderer start → workbench JS load | 205 | 311 | +106 | +51.7 % | 171 | 5/5 | noise |
| Workbench JS load + evaluate | 305 | 301 | -4 | -1.3 % | 235 | 5/5 | noise |
| Workbench main → services start | 39 | 49 | +10 | +25.6 % | 51 | 5/5 | noise |
| Workbench services, contributions, restore | 464 | 638 | +174 | +37.5 % | 382 | 5/5 | noise |
| · BlockStartup contributions | 15 | 17 | +2 | +13.3 % | 13 | 5/5 | noise |
| · BlockRestore contributions | 32 | 21 | -11 | -34.4 % | 30 | 5/5 | noise |
| · Editor restore | 228 | 46 | -182 | -79.8 % | 174 | 5/5 | **better** |
| Idle footprint | 807 | 641 | -167 | -20.7 % | 164 | 3/3 | **better** |
| Idle RSS | 2,063 | 1,759 | -304 | -14.8 % | 426 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 4.91 | 2.04 | -2.87 | -58.5 % | 1.20 | 3/3 | **better** |
| · idle CPU: renderer | 2.43 | 0.67 | -1.76 | -72.4 % | 0.33 | 3/3 | **better** |
| · idle CPU: gpu | 1.82 | 0.82 | -1.00 | -54.9 % | 0.29 | 3/3 | **better** |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.03 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.10 | +0.00 | +0.0 % | 0.05 | 3/3 | noise |
| · idle CPU: tsserver | 0.30 | 0.39 | +0.09 | +30.0 % | 0.53 | 3/3 | noise |
| CPU, first 60 s after window | 35.25 | 21.54 | -13.71 | -38.9 % | 18.86 | 3/3 | noise |
| 20 files: footprint | 808 | 638 | -171 | -21.1 % | 46 | 3/3 | **better** |
| Slow shell: extension host ready | 4,128 | 3,910 | -218 | -5.3 % | 170 | 3/3 | **better** |
| Slow shell: first file-search result | 4,591 | 4,254 | -337 | -7.3 % | 249 | 3/3 | **better** |
| Fast shell: first file-search result | 3,029 | 2,032 | -997 | -32.9 % | 110 | 3/3 | **better** |

### FriedLiver patched vs VS Code (stock)

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 1,708 | 2,869 | +1,161 | +68.0 % | 1,543 | 5/5 | noise |
| First window | 983 | 1,876 | +893 | +90.8 % | 819 | 5/5 | **worse** |
| Extension host ready | 3,181 | 3,222 | +41 | +1.3 % | 2,775 | 5/5 | noise |
| Process start → main started | 271 | 626 | +355 | +131.0 % | 258 | 5/5 | **worse** |
| Main: switches, locale, app ready | 111 | 187 | +76 | +68.5 % | 112 | 5/5 | noise |
| Main services → window opened | 382 | 564 | +182 | +47.6 % | 412 | 5/5 | noise |
| Renderer start → workbench JS load | 205 | 342 | +137 | +66.8 % | 268 | 5/5 | noise |
| Workbench JS load + evaluate | 305 | 334 | +29 | +9.5 % | 235 | 5/5 | noise |
| Workbench main → services start | 39 | 64 | +25 | +64.1 % | 51 | 5/5 | noise |
| Workbench services, contributions, restore | 464 | 613 | +149 | +32.1 % | 440 | 5/5 | noise |
| · BlockStartup contributions | 15 | 19 | +4 | +26.7 % | 13 | 5/5 | noise |
| · BlockRestore contributions | 32 | 19 | -13 | -40.6 % | 30 | 5/5 | noise |
| · Editor restore | 228 | 32 | -196 | -86.0 % | 174 | 5/5 | **better** |
| Idle footprint | 807 | 556 | -251 | -31.1 % | 164 | 3/3 | **better** |
| Idle RSS | 2,063 | 1,597 | -466 | -22.6 % | 426 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 4.91 | 1.93 | -2.98 | -60.7 % | 1.01 | 3/3 | **better** |
| · idle CPU: renderer | 2.43 | 0.66 | -1.77 | -72.8 % | 0.33 | 3/3 | **better** |
| · idle CPU: gpu | 1.82 | 0.81 | -1.01 | -55.5 % | 0.24 | 3/3 | **better** |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.03 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.03 | 3/3 | noise |
| · idle CPU: network | 0.00 | 0.02 | +0.02 | – | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.12 | +0.02 | +20.0 % | 0.05 | 3/3 | noise |
| · idle CPU: tsserver | 0.30 | 0.16 | -0.14 | -46.7 % | 0.38 | 3/3 | noise |
| CPU, first 60 s after window | 35.25 | 26.05 | -9.20 | -26.1 % | 18.86 | 3/3 | noise |
| 20 files: footprint | 808 | 556 | -252 | -31.2 % | 29 | 3/3 | **better** |
| Slow shell: extension host ready | 4,128 | 1,444 | -2,684 | -65.0 % | 1,051 | 3/3 | **better** |
| Slow shell: first file-search result | 4,591 | 1,795 | -2,796 | -60.9 % | 1,742 | 3/3 | **better** |
| Fast shell: first file-search result | 3,029 | 2,447 | -582 | -19.2 % | 1,333 | 3/3 | noise |

### FriedLiver patched vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,353 | 2,869 | +516 | +21.9 % | 1,543 | 5/5 | noise |
| First window | 1,507 | 1,876 | +369 | +24.5 % | 819 | 5/5 | noise |
| Extension host ready | 2,729 | 3,222 | +493 | +18.1 % | 1,830 | 5/5 | noise |
| Process start → main started | 453 | 626 | +173 | +38.2 % | 320 | 5/5 | noise |
| Main: switches, locale, app ready | 150 | 187 | +37 | +24.7 % | 112 | 5/5 | noise |
| Main services → window opened | 433 | 564 | +131 | +30.3 % | 412 | 5/5 | noise |
| Renderer start → workbench JS load | 311 | 342 | +31 | +10.0 % | 268 | 5/5 | noise |
| Workbench JS load + evaluate | 301 | 334 | +33 | +11.0 % | 219 | 5/5 | noise |
| Workbench main → services start | 49 | 64 | +15 | +30.6 % | 33 | 5/5 | noise |
| Workbench services, contributions, restore | 638 | 613 | -25 | -3.9 % | 440 | 5/5 | noise |
| · BlockStartup contributions | 17 | 19 | +2 | +11.8 % | 9 | 5/5 | noise |
| · BlockRestore contributions | 21 | 19 | -2 | -9.5 % | 15 | 5/5 | noise |
| · Editor restore | 46 | 32 | -14 | -30.4 % | 23 | 5/5 | noise |
| Idle footprint | 641 | 556 | -84 | -13.2 % | 126 | 3/3 | noise |
| Idle RSS | 1,759 | 1,597 | -161 | -9.2 % | 319 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.04 | 1.93 | -0.11 | -5.4 % | 1.20 | 3/3 | noise |
| · idle CPU: renderer | 0.67 | 0.66 | -0.01 | -1.5 % | 0.28 | 3/3 | noise |
| · idle CPU: gpu | 0.82 | 0.81 | -0.01 | -1.2 % | 0.29 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.02 | 0.02 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.03 | 3/3 | noise |
| · idle CPU: network | 0.00 | 0.02 | +0.02 | – | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.12 | +0.02 | +20.0 % | 0.05 | 3/3 | noise |
| · idle CPU: tsserver | 0.39 | 0.16 | -0.23 | -59.0 % | 0.53 | 3/3 | noise |
| CPU, first 60 s after window | 21.54 | 26.05 | +4.51 | +20.9 % | 17.58 | 3/3 | noise |
| 20 files: footprint | 638 | 556 | -81 | -12.8 % | 46 | 3/3 | **better** |
| Slow shell: extension host ready | 3,910 | 1,444 | -2,466 | -63.1 % | 1,051 | 3/3 | **better** |
| Slow shell: first file-search result | 4,254 | 1,795 | -2,459 | -57.8 % | 1,742 | 3/3 | **better** |
| Fast shell: first file-search result | 2,032 | 2,447 | +415 | +20.4 % | 1,333 | 3/3 | noise |


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
- **Memory and CPU.** Three idle runs per arm, round-robin across arms, and the report gives the median [min–max]. Each run opens the workspace (the agent apps open no workspace) and waits 60 s after the first window. It then takes a snapshot: process count, summed RSS, and `footprint` total for the whole tree, which counts shared pages once. *CPU in the first 60 s* is the change in summed `ps` CPU time from the first window to that snapshot. *Idle CPU* is the change over the next 60 s. Both are a percentage of one core. Idle CPU is also split by process role, read from each process's `ps -E` line: `--type=renderer`/`gpu-process`, Chromium utility sub-type (network, …), VS Code's utility processes by `VSCODE_ESM_ENTRYPOINT` (extensionHostProcess, sharedProcessMain, ptyHostMain, …), Node scripts by name (tsserver), `main`. A process that exits inside the window loses its CPU time, because `ps` stops reporting it. Three more runs per arm open the workspace plus 20 `.ts` files at launch and take a snapshot at ready + 60 s.
- **A/B arms.** An arm is an app, a *settings variant* of an app (`friedliver+settings-perf`: the same binary, with extra settings merged into the throwaway profile's `settings.json`), or *FriedLiver patched*: a build from a FriedLiver-Code release tag, or from a Build FriedLiver workflow run's `friedliver-fork-macos-arm64` artifact. A run artifact is used only if the run is a Build FriedLiver (`build.yml`) run on `MrArun005/FriedLiver-Code` itself (no forks), triggered by a push or a manual dispatch, from `main`, `perf/*`, `release/*`, `ui/*` or a `v*` tag. It is also checked against the SHA-256 digest GitHub records at upload. The GitHub token is available to the download step only, never to the step that runs the apps. The workflow inputs `apps`, `variants`, `friedliver_ref` and `scenarios` choose the arms. With the defaults, the arms are VS Code, the FriedLiver release, and FriedLiver + settings-perf.
- **Idle suite** (`suite: idle`): only the warm-up and 3 idle runs per arm, so up to about 10 arms fit the job. It is for bisecting an idle-CPU or memory change one setting at a time. `suite: idle-editor` does the same with one `.ts` file opened last, so a text editor has focus and its caret is showing. A variant can also set environment variables, e.g. `no-compile-cache` sets `NODE_DISABLE_COMPILE_CACHE=1`.
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
- **What is open at idle depends on the runs before it.** In the full suite the idle runs come after the three 5 MB-file launches, so the window restores `big-5mb.txt` in a focused editor (about +150–200 MB footprint and 2–3 more processes compared with an empty window). Its caret is then live during the idle window. For the caret this is the realistic case: you read code with the editor focused. It also explains why the full suite's idle CPU depends on `editor.cursorBlinking` and the idle-only suite's does not.
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

