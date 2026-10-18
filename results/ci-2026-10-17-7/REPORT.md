# Editor benchmark — phases + A/B (2026-10-17, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39080483386

Scenarios: none.

## Arms

| Arm | Version | VS Code base | Install size (MB) | Source / verification |
|---|---|---|---:|---|
| FriedLiver | 1.142.0 | 1.142.0 | 563 | sha256 verified; codesign valid |
| FriedLiver patched | 1.142.0 | 1.142.0 | 518 | run 39055910922: perf/core@3f198b5401 (workflow_dispatch); trusted run; artifact sha256 digest verified; codesign valid |
| FriedLiver + blink | 1.142.0 | 1.142.0 | 563 | same binary as FriedLiver + settings below |
| FriedLiver + deferred-activation | 1.142.0 | 1.142.0 | 563 | same binary as FriedLiver + settings below |
| FriedLiver + one-tsserver | 1.142.0 | 1.142.0 | 563 | same binary as FriedLiver + settings below |
| FriedLiver + no-welcome | 1.142.0 | 1.142.0 | 563 | same binary as FriedLiver + settings below |
| FriedLiver + watcher-excludes | 1.142.0 | 1.142.0 | 563 | same binary as FriedLiver + settings below |
| FriedLiver patched + no-compile-cache | 1.142.0 | 1.142.0 | 518 | same binary as FriedLiver patched + settings below |
| FriedLiver patched + no-fast-shell | 1.142.0 | 1.142.0 | 518 | same binary as FriedLiver patched + settings below |
| FriedLiver patched + caret-smooth | 1.142.0 | 1.142.0 | 518 | same binary as FriedLiver patched + settings below |

Settings added for **FriedLiver + blink** (on top of `update.mode: none`):

```json
{
 "editor.cursorBlinking": "blink"
}
```

Settings added for **FriedLiver + deferred-activation** (on top of `update.mode: none`):

```json
{
 "extensions.experimental.deferredStartupFinishedActivation": true
}
```

Settings added for **FriedLiver + one-tsserver** (on top of `update.mode: none`):

```json
{
 "typescript.tsserver.useSyntaxServer": "never"
}
```

Settings added for **FriedLiver + no-welcome** (on top of `update.mode: none`):

```json
{
 "workbench.startupEditor": "none"
}
```

Settings added for **FriedLiver + watcher-excludes** (on top of `update.mode: none`):

```json
{
 "files.watcherExclude": {
  "**/node_modules/*/**": true,
  "**/.venv/**": true,
  "**/venv/**": true,
  "**/__pycache__/**": true,
  "**/.mypy_cache/**": true,
  "**/.pytest_cache/**": true,
  "**/.next/**": true,
  "**/.nuxt/**": true,
  "**/.turbo/**": true,
  "**/.parcel-cache/**": true,
  "**/.gradle/**": true
 }
}
```

Environment added for **FriedLiver patched + no-compile-cache**: `NODE_DISABLE_COMPILE_CACHE=1`

Settings added for **FriedLiver patched + no-fast-shell** (on top of `update.mode: none`):

```json
{
 "friedliver.fastShellEnv": false
}
```

Settings added for **FriedLiver patched + caret-smooth** (on top of `update.mode: none`):

```json
{
 "editor.cursorBlinking": "smooth"
}
```

## Cold start (1 warm-up discarded, then 5 runs, round-robin across arms)

| Arm | Launch → workbench ready, median (p90) ms | Launch → extension host ready, median (p90) ms | Launch → first window, median (p90) ms |
|---|---:|---:|---:|
| FriedLiver | – | – | – |
| FriedLiver patched | – | – | – |
| FriedLiver + blink | – | – | – |
| FriedLiver + deferred-activation | – | – | – |
| FriedLiver + one-tsserver | – | – | – |
| FriedLiver + no-welcome | – | – | – |
| FriedLiver + watcher-excludes | – | – | – |
| FriedLiver patched + no-compile-cache | – | – | – |
| FriedLiver patched + no-fast-shell | – | – | – |
| FriedLiver patched + caret-smooth | – | – | – |

## Startup phases (cold runs, median ms, from the product's own perf marks)

The first seven rows are consecutive and add up to process start → workbench ready (each is a median, so the sum is close to the workbench median, not equal). The rows after the divider break that down or cover the extension host.

| Phase | Marks | FriedLiver | FriedLiver patched | FriedLiver + blink | FriedLiver + deferred-activation | FriedLiver + one-tsserver | FriedLiver + no-welcome | FriedLiver + watcher-excludes | FriedLiver patched + no-compile-cache | FriedLiver patched + no-fast-shell | FriedLiver patched + caret-smooth |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Process start → main started | `willLoadMainBundle` → `didStartMain` | – | – | – | – | – | – | – | – | – | – |
| Main: switches, locale, app ready | `didStartMain` → `mainAppReady` | – | – | – | – | – | – | – | – | – | – |
| Main services → window opened | `mainAppReady` → `willOpenNewWindow` | – | – | – | – | – | – | – | – | – | – |
| Renderer start → workbench JS load | `willOpenNewWindow` → `willLoadWorkbenchMain` | – | – | – | – | – | – | – | – | – | – |
| Workbench JS load + evaluate | `willLoadWorkbenchMain` → `didLoadWorkbenchMain` | – | – | – | – | – | – | – | – | – | – |
| Workbench main → services start | `didLoadWorkbenchMain` → `willStartWorkbench` | – | – | – | – | – | – | – | – | – | – |
| Workbench services, contributions, restore | `willStartWorkbench` → `didStartWorkbench` | – | – | – | – | – | – | – | – | – | – |
| — | |  |  |  |  |  |  |  |  |  |  |
| · BlockStartup contributions | `willCreateWorkbenchContributions/1` → `didCreateWorkbenchContributions/1` | – | – | – | – | – | – | – | – | – | – |
| · BlockRestore contributions | `willCreateWorkbenchContributions/2` → `didCreateWorkbenchContributions/2` | – | – | – | – | – | – | – | – | – | – |
| · Editor restore | `willRestoreEditors` → `didRestoreEditors` | – | – | – | – | – | – | – | – | – | – |
| Extension scan + registration (renderer) | `willLoadExtensions` → `didLoadExtensions` | – | – | – | – | – | – | – | – | – | – |
| Extension host: connect to renderer | `extHost/willConnectToRenderer` → `extHost/didConnectToRenderer` | – | – | – | – | – | – | – | – | – | – |
| Workbench ready → extension host ready | `didStartWorkbench` → `extHost/ready` | – | – | – | – | – | – | – | – | – | – |
| Extension host ready (from process start) | `willLoadMainBundle` → `extHost/ready` | – | – | – | – | – | – | – | – | – | – |

### Slowest workbench contributions (renderer.log)

VS Code logs a contribution at warn level only when creating it took over 20 ms (BlockStartup/BlockRestore) or 100 ms (later phases). Median ms over the cold runs it appeared in (runs seen / cold runs).

- **FriedLiver**: none above the threshold
- **FriedLiver patched**: none above the threshold
- **FriedLiver + blink**: none above the threshold
- **FriedLiver + deferred-activation**: none above the threshold
- **FriedLiver + one-tsserver**: none above the threshold
- **FriedLiver + no-welcome**: none above the threshold
- **FriedLiver + watcher-excludes**: none above the threshold
- **FriedLiver patched + no-compile-cache**: none above the threshold
- **FriedLiver patched + no-fast-shell**: none above the threshold
- **FriedLiver patched + caret-smooth**: none above the threshold

### Node compile cache

Status per process, from the `[node-compile-cache]` line each process writes to its log; folder size of `CachedData/<commit>/node` after each launch (launch 1 = warm-up, 2–6 = the cold runs).

| Arm | Status per process | Folder KB after launches 1…6 |
|---|---|---|
| FriedLiver | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 |
| FriedLiver patched | extension-host: packaged cache inactive: enabled; main: packaged cache inactive: disabled | 4406 |
| FriedLiver + blink | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 |
| FriedLiver + deferred-activation | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 |
| FriedLiver + one-tsserver | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 |
| FriedLiver + no-welcome | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 |
| FriedLiver + watcher-excludes | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 |
| FriedLiver patched + no-compile-cache | extension-host: packaged cache inactive: disabled; main: packaged cache inactive: disabled | 0 |
| FriedLiver patched + no-fast-shell | extension-host: packaged cache inactive: enabled; main: packaged cache inactive: disabled | 4406 |
| FriedLiver patched + caret-smooth | extension-host: packaged cache inactive: enabled; main: packaged cache inactive: disabled | 4406 |

- FriedLiver: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver patched: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-7qplaai2/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-7qplaai2/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`
- FriedLiver + blink: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + deferred-activation: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + one-tsserver: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + no-welcome: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + watcher-excludes: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver patched + no-compile-cache: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /private/tmp/ebp-7qplaai2/friedliver-patched+no-compile-cache/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: none)`
- FriedLiver patched + no-fast-shell: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-7qplaai2/friedliver-patched+no-fast-shell/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-7qplaai2/friedliver-patched+no-fast-shell/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`
- FriedLiver patched + caret-smooth: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-7qplaai2/friedliver-patched+caret-smooth/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-7qplaai2/friedliver-patched+caret-smooth/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`

### Launch 1 (fresh profile, empty caches) vs launches 2–6

| Arm | Metric | Launch 1 | Launches 2–6 median [min–max] | Δ |
|---|---|---:|---:|---:|

## Memory, processes and idle CPU

Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.

| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 12 | 648 [632–680] | 1,807 [1,788–1,829] | 2.56 [2.52–2.69] | 25 [22–28] | n/a |
| FriedLiver patched | 11 | 584 [561–585] | 1,629 [1,606–1,634] | 7.1 [6.09–7.22] | 25 [20–29] | n/a |
| FriedLiver + blink | 12 | 661 [654–664] | 1,772 [1,758–1,773] | 5.97 [5.82–7.46] | 23 [23–23] | n/a |
| FriedLiver + deferred-activation | 12 | 645 [633–651] | 1,772 [1,761–1,784] | 2.76 [2.18–2.8] | 20 [20–32] | n/a |
| FriedLiver + one-tsserver | 11 | 566 [550–568] | 1,589 [1,589–1,604] | 2.03 [2–2.77] | 21 [18–24] | n/a |
| FriedLiver + no-welcome | 12 | 636 [620–654] | 1,757 [1,739–1,791] | 2.16 [2.14–2.31] | 21 [19–24] | n/a |
| FriedLiver + watcher-excludes | 12 | 652 [640–660] | 1,766 [1,765–1,802] | 2.55 [2.42–2.66] | 22 [22–22] | n/a |
| FriedLiver patched + no-compile-cache | 11 | 580 [565–580] | 1,609 [1,594–1,636] | 5.99 [5.57–6.16] | 25 [24–26] | n/a |
| FriedLiver patched + no-fast-shell | 11 | 565 [563–585] | 1,677 [1,658–1,681] | 5.92 [5.77–6.05] | 27 [25–29] | n/a |
| FriedLiver patched + caret-smooth | 11 | 548 [547–569] | 1,617 [1,597–1,636] | 2.38 [2.18–2.61] | 20 [20–26] | n/a |

### Idle CPU by process (% of one core, median of the idle runs)

| Arm | Processes, highest first |
|---|---|
| FriedLiver | gpu 0.94, renderer 0.89, tsserver 0.48, main 0.13, watcherMain 0.05 |
| FriedLiver patched | renderer 3.93, gpu 2.61, tsserver 0.31, main 0.13, extensionHostProcess 0.05, watcherMain 0.05 |
| FriedLiver + blink | renderer 3.18, gpu 2.23, tsserver 0.38, main 0.12 |
| FriedLiver + deferred-activation | renderer 1.06, gpu 0.92, tsserver 0.49, main 0.12 |
| FriedLiver + one-tsserver | gpu 0.92, renderer 0.76, tsserver 0.23, main 0.1 |
| FriedLiver + no-welcome | gpu 0.82, renderer 0.79, tsserver 0.36, main 0.1 |
| FriedLiver + watcher-excludes | gpu 0.94, renderer 0.86, tsserver 0.48, main 0.12 |
| FriedLiver patched + no-compile-cache | renderer 3.27, gpu 2.27, tsserver 0.25, main 0.15, extensionHostProcess 0.07 |
| FriedLiver patched + no-fast-shell | renderer 3.23, gpu 2.27, tsserver 0.25, main 0.1 |
| FriedLiver patched + caret-smooth | gpu 0.97, renderer 0.89, tsserver 0.31, main 0.12 |

## Opening a 5 MB file (VS Code family only)

| Arm | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |
|---|---:|---:|---:|
| FriedLiver | – | – | – |
| FriedLiver patched | – | – | – |
| FriedLiver + blink | – | – | – |
| FriedLiver + deferred-activation | – | – | – |
| FriedLiver + one-tsserver | – | – | – |
| FriedLiver + no-welcome | – | – | – |
| FriedLiver + watcher-excludes | – | – | – |
| FriedLiver patched + no-compile-cache | – | – | – |
| FriedLiver patched + no-fast-shell | – | – | – |
| FriedLiver patched + caret-smooth | – | – | – |

## A/B deltas

Δ = arm median − baseline median (negative = the arm is faster or smaller). **better** or **worse** only when |Δ| is larger than either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point (CPU). Otherwise *noise*. This is one run; the keep rule needs the same verdict in two separate CI runs.

### FriedLiver patched vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 584 | -64 | -9.9 % | 48 | 3/3 | **better** |
| Idle RSS | 1,807 | 1,629 | -178 | -9.9 % | 41 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 2.56 | 7.10 | +4.54 | +177.3 % | 1.13 | 3/3 | **worse** |
| · idle CPU: renderer | 0.89 | 3.93 | +3.04 | +341.6 % | 0.76 | 3/3 | **worse** |
| · idle CPU: gpu | 0.94 | 2.61 | +1.67 | +177.7 % | 0.23 | 3/3 | **worse** |
| · idle CPU: extensionHostProcess | 0.03 | 0.05 | +0.02 | +66.7 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.13 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.31 | -0.17 | -35.4 % | 0.10 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 25.39 | +0.30 | +1.2 % | 8.43 | 3/3 | noise |

### FriedLiver + blink vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 661 | +13 | +2.0 % | 48 | 3/3 | noise |
| Idle RSS | 1,807 | 1,772 | -35 | -2.0 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.56 | 5.97 | +3.41 | +133.2 % | 1.64 | 3/3 | **worse** |
| · idle CPU: renderer | 0.89 | 3.18 | +2.29 | +257.3 % | 1.26 | 3/3 | **worse** |
| · idle CPU: gpu | 0.94 | 2.23 | +1.29 | +137.2 % | 0.44 | 3/3 | **worse** |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.03 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.12 | -0.01 | -7.7 % | 0.05 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.38 | -0.10 | -20.8 % | 0.08 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 23.23 | -1.86 | -7.4 % | 6.34 | 3/3 | noise |

### FriedLiver + deferred-activation vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 645 | -3 | -0.5 % | 48 | 3/3 | noise |
| Idle RSS | 1,807 | 1,772 | -35 | -1.9 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.56 | 2.76 | +0.20 | +7.8 % | 0.62 | 3/3 | noise |
| · idle CPU: renderer | 0.89 | 1.06 | +0.17 | +19.1 % | 0.23 | 3/3 | noise |
| · idle CPU: gpu | 0.94 | 0.92 | -0.02 | -2.1 % | 0.22 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.05 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.02 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.03 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.12 | -0.01 | -7.7 % | 0.07 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.49 | +0.01 | +2.1 % | 0.11 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 20.26 | -4.83 | -19.3 % | 12.17 | 3/3 | noise |

### FriedLiver + one-tsserver vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 566 | -82 | -12.6 % | 48 | 3/3 | **better** |
| Idle RSS | 1,807 | 1,589 | -218 | -12.0 % | 41 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 2.56 | 2.03 | -0.53 | -20.7 % | 0.77 | 3/3 | noise |
| · idle CPU: renderer | 0.89 | 0.76 | -0.13 | -14.6 % | 0.23 | 3/3 | noise |
| · idle CPU: gpu | 0.94 | 0.92 | -0.02 | -2.1 % | 0.47 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.02 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.10 | -0.03 | -23.1 % | 0.04 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.23 | -0.25 | -52.1 % | 0.12 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 20.97 | -4.12 | -16.4 % | 6.34 | 3/3 | noise |

### FriedLiver + no-welcome vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 636 | -12 | -1.9 % | 48 | 3/3 | noise |
| Idle RSS | 1,807 | 1,757 | -50 | -2.8 % | 52 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.56 | 2.16 | -0.40 | -15.6 % | 0.17 | 3/3 | noise |
| · idle CPU: renderer | 0.89 | 0.79 | -0.10 | -11.2 % | 0.23 | 3/3 | noise |
| · idle CPU: gpu | 0.94 | 0.82 | -0.12 | -12.8 % | 0.08 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.02 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.10 | -0.03 | -23.1 % | 0.03 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.36 | -0.12 | -25.0 % | 0.06 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 20.91 | -4.18 | -16.7 % | 6.34 | 3/3 | noise |

### FriedLiver + watcher-excludes vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 652 | +4 | +0.6 % | 48 | 3/3 | noise |
| Idle RSS | 1,807 | 1,766 | -41 | -2.3 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 2.56 | 2.55 | -0.01 | -0.4 % | 0.24 | 3/3 | noise |
| · idle CPU: renderer | 0.89 | 0.86 | -0.03 | -3.4 % | 0.23 | 3/3 | noise |
| · idle CPU: gpu | 0.94 | 0.94 | +0.00 | +0.0 % | 0.11 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.04 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.12 | -0.01 | -7.7 % | 0.02 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.48 | +0.00 | +0.0 % | 0.18 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 21.92 | -3.17 | -12.6 % | 6.34 | 3/3 | noise |

### FriedLiver patched + no-compile-cache vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 580 | -68 | -10.5 % | 48 | 3/3 | **better** |
| Idle RSS | 1,807 | 1,609 | -198 | -11.0 % | 41 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 2.56 | 5.99 | +3.43 | +134.0 % | 0.59 | 3/3 | **worse** |
| · idle CPU: renderer | 0.89 | 3.27 | +2.38 | +267.4 % | 0.47 | 3/3 | **worse** |
| · idle CPU: gpu | 0.94 | 2.27 | +1.33 | +141.5 % | 0.19 | 3/3 | **worse** |
| · idle CPU: extensionHostProcess | 0.03 | 0.07 | +0.04 | +133.3 % | 0.04 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.15 | +0.02 | +15.4 % | 0.05 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.25 | -0.23 | -47.9 % | 0.06 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 24.76 | -0.33 | -1.3 % | 6.34 | 3/3 | noise |

### FriedLiver patched + no-fast-shell vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 565 | -83 | -12.7 % | 48 | 3/3 | **better** |
| Idle RSS | 1,807 | 1,677 | -130 | -7.2 % | 41 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 2.56 | 5.92 | +3.36 | +131.2 % | 0.28 | 3/3 | **worse** |
| · idle CPU: renderer | 0.89 | 3.23 | +2.34 | +262.9 % | 0.26 | 3/3 | **worse** |
| · idle CPU: gpu | 0.94 | 2.27 | +1.33 | +141.5 % | 0.08 | 3/3 | **worse** |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.10 | -0.03 | -23.1 % | 0.02 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.25 | -0.23 | -47.9 % | 0.07 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 27.19 | +2.10 | +8.4 % | 6.34 | 3/3 | noise |

### FriedLiver patched + caret-smooth vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 648 | 548 | -100 | -15.4 % | 48 | 3/3 | **better** |
| Idle RSS | 1,807 | 1,617 | -190 | -10.5 % | 41 | 3/3 | **better** |
| Idle CPU (ready+60→120 s) | 2.56 | 2.38 | -0.18 | -7.0 % | 0.43 | 3/3 | noise |
| · idle CPU: renderer | 0.89 | 0.89 | +0.00 | +0.0 % | 0.25 | 3/3 | noise |
| · idle CPU: gpu | 0.94 | 0.97 | +0.03 | +3.2 % | 0.18 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.12 | -0.01 | -7.7 % | 0.02 | 3/3 | noise |
| · idle CPU: tsserver | 0.48 | 0.31 | -0.17 | -35.4 % | 0.06 | 3/3 | noise |
| CPU, first 60 s after window | 25.09 | 20.24 | -4.85 | -19.3 % | 6.34 | 3/3 | noise |

### FriedLiver patched + no-compile-cache vs FriedLiver patched

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 584 | 580 | -4 | -0.7 % | 24 | 3/3 | noise |
| Idle RSS | 1,629 | 1,609 | -20 | -1.2 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 7.10 | 5.99 | -1.11 | -15.6 % | 1.13 | 3/3 | noise |
| · idle CPU: renderer | 3.93 | 3.27 | -0.66 | -16.8 % | 0.76 | 3/3 | noise |
| · idle CPU: gpu | 2.61 | 2.27 | -0.34 | -13.0 % | 0.23 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.05 | 0.07 | +0.02 | +40.0 % | 0.04 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.00 | 0.02 | +0.02 | – | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.15 | +0.02 | +15.4 % | 0.05 | 3/3 | noise |
| · idle CPU: tsserver | 0.31 | 0.25 | -0.06 | -19.4 % | 0.10 | 3/3 | noise |
| CPU, first 60 s after window | 25.39 | 24.76 | -0.63 | -2.5 % | 8.43 | 3/3 | noise |

### FriedLiver patched + no-fast-shell vs FriedLiver patched

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 584 | 565 | -18 | -3.2 % | 24 | 3/3 | noise |
| Idle RSS | 1,629 | 1,677 | +48 | +3.0 % | 28 | 3/3 | **worse** |
| Idle CPU (ready+60→120 s) | 7.10 | 5.92 | -1.18 | -16.6 % | 1.13 | 3/3 | **better** |
| · idle CPU: renderer | 3.93 | 3.23 | -0.70 | -17.8 % | 0.76 | 3/3 | noise |
| · idle CPU: gpu | 2.61 | 2.27 | -0.34 | -13.0 % | 0.23 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.05 | 0.02 | -0.03 | -60.0 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.00 | 0.02 | +0.02 | – | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.10 | -0.03 | -23.1 % | 0.00 | 3/3 | noise |
| · idle CPU: tsserver | 0.31 | 0.25 | -0.06 | -19.4 % | 0.10 | 3/3 | noise |
| CPU, first 60 s after window | 25.39 | 27.19 | +1.80 | +7.1 % | 8.43 | 3/3 | noise |

### FriedLiver patched + caret-smooth vs FriedLiver patched

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 584 | 548 | -36 | -6.1 % | 24 | 3/3 | **better** |
| Idle RSS | 1,629 | 1,617 | -12 | -0.7 % | 39 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 7.10 | 2.38 | -4.72 | -66.5 % | 1.13 | 3/3 | **better** |
| · idle CPU: renderer | 3.93 | 0.89 | -3.04 | -77.4 % | 0.76 | 3/3 | **better** |
| · idle CPU: gpu | 2.61 | 0.97 | -1.64 | -62.8 % | 0.23 | 3/3 | **better** |
| · idle CPU: extensionHostProcess | 0.05 | 0.03 | -0.02 | -40.0 % | 0.02 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: main | 0.13 | 0.12 | -0.01 | -7.7 % | 0.00 | 3/3 | noise |
| · idle CPU: tsserver | 0.31 | 0.31 | +0.00 | +0.0 % | 0.10 | 3/3 | noise |
| CPU, first 60 s after window | 25.39 | 20.24 | -5.15 | -20.3 % | 8.43 | 3/3 | noise |


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

