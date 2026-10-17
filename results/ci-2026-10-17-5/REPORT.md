# Editor benchmark — phases + A/B (2026-10-17, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39066571434

Scenarios: none.

## Arms

| Arm | Version | VS Code base | Install size (MB) | Source / verification |
|---|---|---|---:|---|
| FriedLiver | 1.142.0 | 1.142.0 | 563 | sha256 verified; codesign valid |
| FriedLiver patched | 1.142.0 | 1.142.0 | 518 | run 39055910922: perf/core@3f198b5401 (workflow_dispatch); trusted run; artifact sha256 digest verified; codesign valid |
| FriedLiver patched + caret-smooth | 1.142.0 | 1.142.0 | 518 | same binary as FriedLiver patched + settings below |
| FriedLiver patched + welcome | 1.142.0 | 1.142.0 | 518 | same binary as FriedLiver patched + settings below |

Settings added for **FriedLiver patched + caret-smooth** (on top of `update.mode: none`):

```json
{
 "editor.cursorBlinking": "smooth"
}
```

Settings added for **FriedLiver patched + welcome** (on top of `update.mode: none`):

```json
{
 "workbench.startupEditor": "welcomePage"
}
```

## Cold start (1 warm-up discarded, then 5 runs, round-robin across arms)

| Arm | Launch → workbench ready, median (p90) ms | Launch → extension host ready, median (p90) ms | Launch → first window, median (p90) ms |
|---|---:|---:|---:|
| FriedLiver | 2,519 (4,064) | 2,771 (4,584) | 1,600 (2,679) |
| FriedLiver patched | 2,252 (2,711) | 2,680 (3,082) | 1,529 (1,859) |
| FriedLiver patched + caret-smooth | 1,485 (2,147) | 1,750 (2,622) | 994 (1,214) |
| FriedLiver patched + welcome | 1,745 (1,806) | 2,087 (2,090) | 974 (1,058) |

## Startup phases (cold runs, median ms, from the product's own perf marks)

The first seven rows are consecutive and add up to process start → workbench ready (each is a median, so the sum is close to the workbench median, not equal). The rows after the divider break that down or cover the extension host.

| Phase | Marks | FriedLiver | FriedLiver patched | FriedLiver patched + caret-smooth | FriedLiver patched + welcome |
|---|---|---:|---:|---:|---:|
| Process start → main started | `willLoadMainBundle` → `didStartMain` | 518 | 581 | 189 | 174 |
| Main: switches, locale, app ready | `didStartMain` → `mainAppReady` | 174 | 175 | 111 | 117 |
| Main services → window opened | `mainAppReady` → `willOpenNewWindow` | 454 | 410 | 307 | 333 |
| Renderer start → workbench JS load | `willOpenNewWindow` → `willLoadWorkbenchMain` | 332 | 326 | 183 | 204 |
| Workbench JS load + evaluate | `willLoadWorkbenchMain` → `didLoadWorkbenchMain` | 358 | 314 | 233 | 283 |
| Workbench main → services start | `didLoadWorkbenchMain` → `willStartWorkbench` | 47 | 52 | 37 | 40 |
| Workbench services, contributions, restore | `willStartWorkbench` → `didStartWorkbench` | 591 | 539 | 443 | 510 |
| — | |  |  |  |  |
| · BlockStartup contributions | `willCreateWorkbenchContributions/1` → `didCreateWorkbenchContributions/1` | 16 | 14 | 12 | 12 |
| · BlockRestore contributions | `willCreateWorkbenchContributions/2` → `didCreateWorkbenchContributions/2` | 20 | 17 | 17 | 17 |
| · Editor restore | `willRestoreEditors` → `didRestoreEditors` | 50 | 26 | 23 | 39 |
| Extension scan + registration (renderer) | `willLoadExtensions` → `didLoadExtensions` | 164 | 202 | 183 | 164 |
| Extension host: connect to renderer | `extHost/willConnectToRenderer` → `extHost/didConnectToRenderer` | 1 | 1 | 1 | 1 |
| Workbench ready → extension host ready | `didStartWorkbench` → `extHost/ready` | 253 | 371 | 267 | 298 |
| Extension host ready (from process start) | `willLoadMainBundle` → `extHost/ready` | 2,771 | 2,680 | 1,750 | 2,087 |

### Slowest workbench contributions (renderer.log)

VS Code logs a contribution at warn level only when creating it took over 20 ms (BlockStartup/BlockRestore) or 100 ms (later phases). Median ms over the cold runs it appeared in (runs seen / cold runs).

- **FriedLiver**: none above the threshold
- **FriedLiver patched**: none above the threshold
- **FriedLiver patched + caret-smooth**: none above the threshold
- **FriedLiver patched + welcome**: none above the threshold

### Node compile cache

Status per process, from the `[node-compile-cache]` line each process writes to its log; folder size of `CachedData/<commit>/node` after each launch (launch 1 = warm-up, 2–6 = the cold runs).

| Arm | Status per process | Folder KB after launches 1…6 |
|---|---|---|
| FriedLiver | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 → 0 → 0 → 0 → 0 → 0 |
| FriedLiver patched | extension-host: packaged cache inactive: enabled; main: packaged cache inactive: disabled | 4406 → 4469 → 4532 → 4595 → 4658 → 4721 |
| FriedLiver patched + caret-smooth | extension-host: packaged cache inactive: enabled; main: packaged cache inactive: disabled | 4406 → 4469 → 4532 → 4595 → 4658 → 4721 |
| FriedLiver patched + welcome | extension-host: packaged cache inactive: enabled; main: packaged cache inactive: disabled | 4406 → 4469 → 4532 → 4595 → 4658 → 4721 |

- FriedLiver: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver patched: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-w5b6_183/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-w5b6_183/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`
- FriedLiver patched + caret-smooth: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-w5b6_183/friedliver-patched+caret-smooth/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-w5b6_183/friedliver-patched+caret-smooth/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`
- FriedLiver patched + welcome: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-w5b6_183/friedliver-patched+welcome/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-w5b6_183/friedliver-patched+welcome/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`

### Launch 1 (fresh profile, empty caches) vs launches 2–6

| Arm | Metric | Launch 1 | Launches 2–6 median [min–max] | Δ |
|---|---|---:|---:|---:|
| FriedLiver | Workbench ready | 4,940 | 2,519 [2,021–4,064] | -2,421 |
| FriedLiver | Extension host ready | 7,118 | 2,771 [2,314–4,584] | -4,347 |
| FriedLiver | Process start → main started | 901 | 518 [460–833] | -383 |
| FriedLiver | Workbench ready → extension host ready | 2,178 | 253 [229–520] | -1,925 |
| FriedLiver patched | Workbench ready | 3,286 | 2,252 [1,947–2,711] | -1,034 |
| FriedLiver patched | Extension host ready | 5,604 | 2,680 [2,220–3,082] | -2,924 |
| FriedLiver patched | Process start → main started | 655 | 581 [472–643] | -74 |
| FriedLiver patched | Workbench ready → extension host ready | 2,318 | 371 [235–428] | -1,947 |
| FriedLiver patched + caret-smooth | Workbench ready | 2,833 | 1,485 [1,412–2,147] | -1,348 |
| FriedLiver patched + caret-smooth | Extension host ready | 4,113 | 1,750 [1,666–2,622] | -2,363 |
| FriedLiver patched + caret-smooth | Process start → main started | 245 | 189 [178–201] | -56 |
| FriedLiver patched + caret-smooth | Workbench ready → extension host ready | 1,280 | 267 [254–475] | -1,013 |
| FriedLiver patched + welcome | Workbench ready | 2,730 | 1,745 [1,388–1,806] | -985 |
| FriedLiver patched + welcome | Extension host ready | 4,497 | 2,087 [1,694–2,090] | -2,410 |
| FriedLiver patched + welcome | Process start → main started | 232 | 174 [140–197] | -58 |
| FriedLiver patched + welcome | Workbench ready → extension host ready | 1,767 | 298 [233–342] | -1,469 |

## Memory, processes and idle CPU

Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.

| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 12 | 636 [516–650] | 1,732 [1,477–1,760] | 2.03 [1.93–2.36] | 27 [22–27] | 637 / 1,746 |
| FriedLiver patched | 11 | 562 [524–564] | 1,569 [1,479–1,587] | 6.26 [5.82–6.59] | 24 [24–26] | 569 / 1,599 |
| FriedLiver patched + caret-smooth | 11 | 552 [509–552] | 1,585 [1,466–1,623] | 1.99 [1.83–2.27] | 23 [21–26] | 552 / 1,572 |
| FriedLiver patched + welcome | 11 | 563 [530–570] | 1,596 [1,491–1,630] | 6.1 [5.99–6.29] | 25 [23–25] | 590 / 1,648 |

### Idle CPU by process (% of one core, median of the idle runs)

| Arm | Processes, highest first |
|---|---|
| FriedLiver | FriedLiver Helper (Renderer) 0.89, FriedLiver Helper 0.84, FriedLiver Helper (Plugin) 0.38, FriedLiver 0.12 |
| FriedLiver patched | FriedLiver Helper (Renderer) 3.41, FriedLiver Helper 2.41, FriedLiver Helper (Plugin) 0.31, FriedLiver 0.12 |
| FriedLiver patched + caret-smooth | FriedLiver Helper 0.92, FriedLiver Helper (Renderer) 0.81, FriedLiver Helper (Plugin) 0.26, FriedLiver 0.1 |
| FriedLiver patched + welcome | FriedLiver Helper (Renderer) 3.38, FriedLiver Helper 2.47, FriedLiver Helper (Plugin) 0.25, FriedLiver 0.1 |

## Opening a 5 MB file (VS Code family only)

| Arm | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |
|---|---:|---:|---:|
| FriedLiver | 576 | 50 | 526 |
| FriedLiver patched | 374 | 26 | 348 |
| FriedLiver patched + caret-smooth | 512 | 23 | 489 |
| FriedLiver patched + welcome | 615 | 39 | 576 |

## A/B deltas

Δ = arm median − baseline median (negative = the arm is faster or smaller). **better** or **worse** only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point (CPU). Otherwise *noise*. This is one run; the keep rule needs the same verdict in two separate CI runs.

### FriedLiver patched vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,519 | 2,252 | -267 | -10.6 % | 2,043 | 5/5 | noise |
| First window | 1,600 | 1,529 | -71 | -4.4 % | 1,345 | 5/5 | noise |
| Extension host ready | 2,771 | 2,680 | -91 | -3.3 % | 2,270 | 5/5 | noise |
| Process start → main started | 518 | 581 | +63 | +12.2 % | 373 | 5/5 | noise |
| Main: switches, locale, app ready | 174 | 175 | +1 | +0.6 % | 258 | 5/5 | noise |
| Main services → window opened | 454 | 410 | -44 | -9.7 % | 280 | 5/5 | noise |
| Renderer start → workbench JS load | 332 | 326 | -6 | -1.8 % | 245 | 5/5 | noise |
| Workbench JS load + evaluate | 358 | 314 | -44 | -12.3 % | 363 | 5/5 | noise |
| Workbench main → services start | 47 | 52 | +5 | +10.6 % | 112 | 5/5 | noise |
| Workbench services, contributions, restore | 591 | 539 | -52 | -8.8 % | 517 | 5/5 | noise |
| · BlockStartup contributions | 16 | 14 | -2 | -12.5 % | 12 | 5/5 | noise |
| · BlockRestore contributions | 20 | 17 | -3 | -15.0 % | 14 | 5/5 | noise |
| · Editor restore | 50 | 26 | -24 | -48.0 % | 46 | 5/5 | noise |
| Idle footprint | 636 | 562 | -74 | -11.6 % | 134 | 3/3 | noise |
| Idle RSS | 1,732 | 1,569 | -163 | -9.4 % | 283 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.03 | 6.26 | +4.23 | +208.4 % | 0.77 | 3/3 | **worse** |
| CPU, first 60 s after window | 27.27 | 24.43 | -2.84 | -10.4 % | 5.39 | 3/3 | noise |
| 20 files: footprint | 637 | 569 | -68 | -10.6 % | 26 | 3/3 | **better** |

### FriedLiver patched + caret-smooth vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,519 | 1,485 | -1,034 | -41.0 % | 2,043 | 5/5 | noise |
| First window | 1,600 | 994 | -606 | -37.9 % | 1,345 | 5/5 | noise |
| Extension host ready | 2,771 | 1,750 | -1,021 | -36.8 % | 2,270 | 5/5 | noise |
| Process start → main started | 518 | 189 | -329 | -63.5 % | 373 | 5/5 | noise |
| Main: switches, locale, app ready | 174 | 111 | -63 | -36.2 % | 258 | 5/5 | noise |
| Main services → window opened | 454 | 307 | -147 | -32.4 % | 280 | 5/5 | noise |
| Renderer start → workbench JS load | 332 | 183 | -149 | -44.9 % | 245 | 5/5 | noise |
| Workbench JS load + evaluate | 358 | 233 | -125 | -34.9 % | 363 | 5/5 | noise |
| Workbench main → services start | 47 | 37 | -10 | -21.3 % | 112 | 5/5 | noise |
| Workbench services, contributions, restore | 591 | 443 | -148 | -25.0 % | 517 | 5/5 | noise |
| · BlockStartup contributions | 16 | 12 | -4 | -25.0 % | 12 | 5/5 | noise |
| · BlockRestore contributions | 20 | 17 | -3 | -15.0 % | 14 | 5/5 | noise |
| · Editor restore | 50 | 23 | -27 | -54.0 % | 46 | 5/5 | noise |
| Idle footprint | 636 | 552 | -84 | -13.2 % | 134 | 3/3 | noise |
| Idle RSS | 1,732 | 1,585 | -146 | -8.4 % | 283 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.03 | 1.99 | -0.04 | -2.0 % | 0.44 | 3/3 | noise |
| CPU, first 60 s after window | 27.27 | 22.67 | -4.60 | -16.9 % | 5.64 | 3/3 | noise |
| 20 files: footprint | 637 | 552 | -85 | -13.4 % | 28 | 3/3 | **better** |

### FriedLiver patched + welcome vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Workbench ready | 2,519 | 1,745 | -774 | -30.7 % | 2,043 | 5/5 | noise |
| First window | 1,600 | 974 | -626 | -39.1 % | 1,345 | 5/5 | noise |
| Extension host ready | 2,771 | 2,087 | -684 | -24.7 % | 2,270 | 5/5 | noise |
| Process start → main started | 518 | 174 | -344 | -66.4 % | 373 | 5/5 | noise |
| Main: switches, locale, app ready | 174 | 117 | -57 | -32.8 % | 258 | 5/5 | noise |
| Main services → window opened | 454 | 333 | -121 | -26.7 % | 280 | 5/5 | noise |
| Renderer start → workbench JS load | 332 | 204 | -128 | -38.6 % | 245 | 5/5 | noise |
| Workbench JS load + evaluate | 358 | 283 | -75 | -20.9 % | 363 | 5/5 | noise |
| Workbench main → services start | 47 | 40 | -7 | -14.9 % | 112 | 5/5 | noise |
| Workbench services, contributions, restore | 591 | 510 | -81 | -13.7 % | 517 | 5/5 | noise |
| · BlockStartup contributions | 16 | 12 | -4 | -25.0 % | 12 | 5/5 | noise |
| · BlockRestore contributions | 20 | 17 | -3 | -15.0 % | 14 | 5/5 | noise |
| · Editor restore | 50 | 39 | -11 | -22.0 % | 46 | 5/5 | noise |
| Idle footprint | 636 | 563 | -73 | -11.4 % | 134 | 3/3 | noise |
| Idle RSS | 1,732 | 1,596 | -136 | -7.8 % | 283 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.03 | 6.10 | +4.07 | +200.5 % | 0.43 | 3/3 | **worse** |
| CPU, first 60 s after window | 27.27 | 25.45 | -1.82 | -6.7 % | 5.39 | 3/3 | noise |
| 20 files: footprint | 637 | 590 | -47 | -7.3 % | 26 | 3/3 | **better** |


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

