# Editor benchmark — phases + A/B (2026-10-17, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39073005329

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
- FriedLiver patched: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-oukcr7h6/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-oukcr7h6/friedliver-patched/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`
- FriedLiver + blink: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + deferred-activation: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + one-tsserver: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + no-welcome: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver + watcher-excludes: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /Users/runner/work/_temp/bench/apps/friedliver/FriedLiver.app/Contents/Resources/app/node-compile-cache/extension-host, active: none)`
- FriedLiver patched + no-compile-cache: `[node-compile-cache] extension-host: packaged cache inactive (status: disabled, configured: /private/tmp/ebp-oukcr7h6/friedliver-patched+no-compile-cache/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: none)`
- FriedLiver patched + no-fast-shell: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-oukcr7h6/friedliver-patched+no-fast-shell/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-oukcr7h6/friedliver-patched+no-fast-shell/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`
- FriedLiver patched + caret-smooth: `[node-compile-cache] extension-host: packaged cache inactive (status: enabled, configured: /private/tmp/ebp-oukcr7h6/friedliver-patched+caret-smooth/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host, active: /private/tmp/ebp-oukcr7h6/friedliver-patched+caret-smooth/udd/CachedData/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/node/extension-host/v24.21.0-arm64-c3a7e8f2-501)`

### Launch 1 (fresh profile, empty caches) vs launches 2–6

| Arm | Metric | Launch 1 | Launches 2–6 median [min–max] | Δ |
|---|---|---:|---:|---:|

## Memory, processes and idle CPU

Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.

| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|
| FriedLiver | 9 | 408 [406–438] | 1,275 [1,266–1,307] | 0.44 [0.4–0.45] | 12 [10–21] | n/a |
| FriedLiver patched | 9 | 399 [399–426] | 1,272 [1,256–1,282] | 0.43 [0.33–0.48] | 12 [11–14] | n/a |
| FriedLiver + blink | 9 | 412 [408–435] | 1,300 [1,280–1,322] | 0.41 [0.36–0.41] | 14 [13–16] | n/a |
| FriedLiver + deferred-activation | 9 | 413 [409–431] | 1,308 [1,272–1,355] | 0.48 [0.39–0.53] | 14 [11–14] | n/a |
| FriedLiver + one-tsserver | 9 | 409 [406–435] | 1,269 [1,268–1,295] | 0.4 [0.38–0.51] | 15 [13–15] | n/a |
| FriedLiver + no-welcome | 9 | 404 [395–425] | 1,288 [1,257–1,300] | 0.51 [0.3–1.15] | 16 [14–18] | n/a |
| FriedLiver + watcher-excludes | 9 | 412 [409–434] | 1,302 [1,292–1,323] | 0.4 [0.26–0.53] | 16 [14–19] | n/a |
| FriedLiver patched + no-compile-cache | 9 | 403 [401–424] | 1,265 [1,257–1,272] | 0.33 [0.26–0.41] | 16 [12–17] | n/a |
| FriedLiver patched + no-fast-shell | 9 | 401 [400–426] | 1,279 [1,258–1,295] | 0.51 [0.5–0.51] | 13 [13–14] | n/a |
| FriedLiver patched + caret-smooth | 9 | 401 [399–422] | 1,276 [1,251–1,294] | 0.38 [0.38–0.38] | 12 [10–14] | n/a |

### Idle CPU by process (% of one core, median of the idle runs)

| Arm | Processes, highest first |
|---|---|
| FriedLiver | renderer 0.2, main 0.1 |
| FriedLiver patched | renderer 0.2, main 0.12 |
| FriedLiver + blink | renderer 0.18, main 0.1 |
| FriedLiver + deferred-activation | renderer 0.23, main 0.12 |
| FriedLiver + one-tsserver | renderer 0.2, main 0.1 |
| FriedLiver + no-welcome | renderer 0.21, main 0.12, extensionHostProcess 0.05, gpu 0.05, watcherMain 0.05 |
| FriedLiver + watcher-excludes | renderer 0.18, main 0.1 |
| FriedLiver patched + no-compile-cache | renderer 0.15, main 0.08 |
| FriedLiver patched + no-fast-shell | renderer 0.26, main 0.1 |
| FriedLiver patched + caret-smooth | renderer 0.18, main 0.1 |

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
| Idle footprint | 408 | 399 | -9 | -2.2 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,272 | -3 | -0.3 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.43 | -0.01 | -2.3 % | 0.15 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.20 | +0.00 | +0.0 % | 0.05 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.12 | +0.02 | +20.0 % | 0.07 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 12.30 | +0.48 | +4.1 % | 10.62 | 3/3 | noise |

### FriedLiver + blink vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 412 | +4 | +0.9 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,300 | +25 | +2.0 % | 43 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.41 | -0.03 | -6.8 % | 0.05 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.18 | -0.02 | -10.0 % | 0.04 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.03 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.00 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.03 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.10 | +0.00 | +0.0 % | 0.03 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 13.97 | +2.15 | +18.2 % | 10.62 | 3/3 | noise |

### FriedLiver + deferred-activation vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 413 | +5 | +1.2 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,308 | +33 | +2.6 % | 83 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.48 | +0.04 | +9.1 % | 0.14 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.23 | +0.03 | +15.0 % | 0.06 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.03 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.03 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.12 | +0.02 | +20.0 % | 0.03 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 14.23 | +2.41 | +20.4 % | 10.62 | 3/3 | noise |

### FriedLiver + one-tsserver vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 409 | +1 | +0.2 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,269 | -6 | -0.5 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.40 | -0.04 | -9.1 % | 0.13 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.20 | +0.00 | +0.0 % | 0.07 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.03 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.03 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.10 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 14.75 | +2.93 | +24.8 % | 10.62 | 3/3 | noise |

### FriedLiver + no-welcome vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 404 | -4 | -1.1 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,288 | +13 | +1.0 % | 43 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.51 | +0.07 | +15.9 % | 0.85 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.21 | +0.01 | +5.0 % | 0.43 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.05 | +0.02 | +66.7 % | 0.16 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.05 | +0.02 | +66.7 % | 0.05 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.12 | +0.02 | +20.0 % | 0.17 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 16.04 | +4.22 | +35.7 % | 10.62 | 3/3 | noise |

### FriedLiver + watcher-excludes vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 412 | +4 | +1.1 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,302 | +27 | +2.1 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.40 | -0.04 | -9.1 % | 0.27 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.18 | -0.02 | -10.0 % | 0.08 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.03 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.10 | +0.00 | +0.0 % | 0.08 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 16.45 | +4.63 | +39.2 % | 10.62 | 3/3 | noise |

### FriedLiver patched + no-compile-cache vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 403 | -5 | -1.2 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,265 | -10 | -0.8 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.33 | -0.11 | -25.0 % | 0.15 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.15 | -0.05 | -25.0 % | 0.10 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.02 | -0.01 | -33.3 % | 0.00 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.00 | -0.02 | -100.0 % | 0.00 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.08 | -0.02 | -20.0 % | 0.02 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 16.41 | +4.59 | +38.8 % | 10.62 | 3/3 | noise |

### FriedLiver patched + no-fast-shell vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 401 | -7 | -1.7 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,279 | +4 | +0.3 % | 41 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.51 | +0.07 | +15.9 % | 0.05 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.26 | +0.06 | +30.0 % | 0.05 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.03 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.10 | +0.00 | +0.0 % | 0.03 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 13.14 | +1.32 | +11.2 % | 10.62 | 3/3 | noise |

### FriedLiver patched + caret-smooth vs FriedLiver

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 408 | 401 | -7 | -1.8 % | 31 | 3/3 | noise |
| Idle RSS | 1,275 | 1,276 | +1 | +0.1 % | 43 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.44 | 0.38 | -0.06 | -13.6 % | 0.05 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.18 | -0.02 | -10.0 % | 0.03 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: network | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.10 | 0.10 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| CPU, first 60 s after window | 11.82 | 12.14 | +0.32 | +2.7 % | 10.62 | 3/3 | noise |

### FriedLiver patched + no-compile-cache vs FriedLiver patched

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 399 | 403 | +4 | +1.0 % | 28 | 3/3 | noise |
| Idle RSS | 1,272 | 1,265 | -7 | -0.5 % | 25 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.43 | 0.33 | -0.10 | -23.3 % | 0.15 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.15 | -0.05 | -25.0 % | 0.10 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.12 | 0.08 | -0.04 | -33.3 % | 0.07 | 3/3 | noise |
| CPU, first 60 s after window | 12.30 | 16.41 | +4.11 | +33.4 % | 5.22 | 3/3 | noise |

### FriedLiver patched + no-fast-shell vs FriedLiver patched

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 399 | 401 | +2 | +0.5 % | 28 | 3/3 | noise |
| Idle RSS | 1,272 | 1,279 | +7 | +0.6 % | 37 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.43 | 0.51 | +0.08 | +18.6 % | 0.15 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.26 | +0.06 | +30.0 % | 0.05 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.03 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.01 | 3/3 | noise |
| · idle CPU: network | 0.00 | 0.02 | +0.02 | – | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.12 | 0.10 | -0.02 | -16.7 % | 0.07 | 3/3 | noise |
| CPU, first 60 s after window | 12.30 | 13.14 | +0.84 | +6.8 % | 2.68 | 3/3 | noise |

### FriedLiver patched + caret-smooth vs FriedLiver patched

| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Idle footprint | 399 | 401 | +2 | +0.4 % | 28 | 3/3 | noise |
| Idle RSS | 1,272 | 1,276 | +4 | +0.3 % | 43 | 3/3 | noise |
| Idle CPU (ready+60→120 s) | 0.43 | 0.38 | -0.05 | -11.6 % | 0.15 | 3/3 | noise |
| · idle CPU: renderer | 0.20 | 0.18 | -0.02 | -10.0 % | 0.05 | 3/3 | noise |
| · idle CPU: gpu | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: extensionHostProcess | 0.03 | 0.02 | -0.01 | -33.3 % | 0.01 | 3/3 | noise |
| · idle CPU: sharedProcessMain | 0.02 | 0.02 | +0.00 | +0.0 % | 0.00 | 3/3 | noise |
| · idle CPU: network | 0.00 | 0.02 | +0.02 | – | 0.02 | 3/3 | noise |
| · idle CPU: main | 0.12 | 0.10 | -0.02 | -16.7 % | 0.07 | 3/3 | noise |
| CPU, first 60 s after window | 12.30 | 12.14 | -0.16 | -1.3 % | 3.44 | 3/3 | noise |


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
- **Idle suite** (`suite: idle`): only the warm-up and 3 idle runs per arm, so up to about 10 arms fit the job. It is for bisecting an idle-CPU or memory change one setting at a time. A variant can also set environment variables, e.g. `no-compile-cache` sets `NODE_DISABLE_COMPILE_CACHE=1`.
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

