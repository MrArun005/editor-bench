# Editor benchmark — phase 1 (2026-10-17, GitHub Actions runner)

Machine: **Apple Virtual Machine 1 / VirtualMac2,1**, Apple M1 (Virtual), 3 cores, 7 GB RAM, macOS 26.6.2 (25G83), power: AC ?. Run: https://github.com/MrArun005/editor-bench/actions/runs/39051446594

## Apps

| App | Version | VS Code base | Install size (MB) | Source / verification |
|---|---|---|---:|---|
| FriedLiver | 1.142.0 | 1.142.0 | 562 | sha256 verified; codesign valid |
| Cursor | 3.25.6 | 1.128.0 | 974 | vendor publishes no hash; codesign valid |
| VS Code (stock) | 1.142.0 | 1.142.0 | 865 | vendor publishes no hash; codesign valid |
| Antigravity (agent app) | 2.24.0 | n/a (not a VS Code fork) | 466 | sha512 verified; codesign valid |
| OpenCode Desktop | 1.19.3 | n/a (not a VS Code fork) | 410 | sha512 verified; codesign valid |
| antigravity-ide | – | – | – | **skipped: Command '['curl', '-fsSL', '--retry', '3', '-o', '/Users/runner/work/_temp/bench/dl/antigravity-ide.zip', 'https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/2.5.5-4923483625488384/darwin-arm/Antigravity IDE.zip']' returned non-zero exit status 3.** |

## Cold start (1 warm-up discarded, then 5 runs, round-robin across apps)

| App | Launch → workbench ready, median (p90) ms | Launch → first window, median (p90) ms |
|---|---:|---:|
| FriedLiver | 2,934 (4,241) | 1,741 (2,353) |
| Cursor | 4,110 (5,539) | 2,374 (3,282) |
| VS Code (stock) | 2,817 (2,986) | 1,880 (1,979) |
| Antigravity (agent app) | – | 2,826 (2,901) |
| OpenCode Desktop | – | 4,881 (5,389) |

## Memory, processes and idle CPU (workspace open; ready + 60 s; CPU averaged over the next 60 s)

| App | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | After 20 files: footprint / RSS (MB) |
|---|---:|---:|---:|---:|---:|
| FriedLiver | 10 | 496 | 1,452 | 2.31 | 657 / 1,786 |
| Cursor | 17 | 1,678 | 3,059 | 8.21 | 1,994 / 3,217 |
| VS Code (stock) | 11 | 646 | 1,733 | 5.74 | 835 / 2,156 |
| Antigravity (agent app) | 7 | 295 | 784 | 3.98 | n/a |
| OpenCode Desktop | 7 | 390 | 954 | 5.09 | n/a |

## Opening a 5 MB file (VS Code family only)

| App | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |
|---|---:|---:|---:|
| FriedLiver | 894 | 53 | 841 |
| Cursor | 734 | 103 | 631 |
| VS Code (stock) | 937 | 244 | 693 |

## Method

- **One app at a time.** Every run waits until every process of the previous run is gone, then sleeps 10 s. A run is aborted (app killed) if free memory (`kern.memorystatus_level` × RAM) drops below 2 GB.
- **Throwaway profiles.** Each app gets its own temporary `HOME`, `XDG_*` dirs, `--user-data-dir`, and (VS Code family) `--extensions-dir`, plus `--use-mock-keychain --password-store=basic`. Apps are launched with `open -n -g` from an **empty environment**. Apps launched from an editor's terminal otherwise inherit `ELECTRON_RUN_AS_NODE` and the parent editor's `VSCODE_IPC_HOOK`. The only setting changed from defaults is `update.mode: none` (VS Code family). VS Code family apps also get `--disable-workspace-trust`, so no trust modal appears on a fresh profile.
- **Process attribution.** The process tree is every process whose argv or environment (`ps -E`) contains that run's temp path, plus all of their descendants. This also catches language servers and sidecars that re-parent to launchd.
- **Workspace.** `microsoft/vscode-extension-samples` at a pinned commit (`setup_fixture.sh`), about 1,200 files. The 5 MB file is `big-5mb.txt`, a deterministic concatenation of the repo's `.ts` sources. It is plain text, so no language server parses it.
- **Cold start.** One warm-up launch is discarded. It is the profile's first-ever launch. Then 5 launches run round-robin across apps, so thermal and battery drift hits every app equally. Every launch starts a new process; the disk cache stays warm because a purge needs root.
  - *Workbench ready* (VS Code family only) comes from the product's own `--prof-append-timers` / `--prof-duration-markers`: the duration from `code/willLoadMainBundle` to `code/didStartWorkbench`. The first mark is the main process's Node `timeOrigin`, which is process start. The app writes the marks and exits by itself.
  - *First window* (all apps) uses an external clock. It runs from just before `open` until `CGWindowListCopyWindowInfo` lists a normal window (layer 0, at least 300×200) owned by the app (`winwait.swift`). It includes LaunchServices overhead.
- **Memory and CPU.** For each app, one idle run opens the workspace (the agent apps open no workspace) and waits 60 s after the first window. It then takes a snapshot: process count, summed RSS, and `footprint` total for the whole tree, which counts shared pages once. CPU is the change in summed `ps` CPU time over the next 60 s, as a percentage of one core. A second run opens the workspace plus 20 `.ts` files at launch and takes a snapshot at ready + 60 s.
- **5 MB file.** Three launches use `--goto big-5mb.txt:1`. The reported number is the `code/willRestoreEditors → code/didRestoreEditors` duration minus the same mark from the plain cold-start runs. The CLI gives no "file is visible" event after launch, so this is the closest objective proxy.
- **p90** uses the nearest-rank method. With 5 runs, it is the slowest run.

## Caveats

- **No extensions and no sign-in.** Real-world numbers with the owner's extensions, accounts and indexes will be higher, especially for Cursor and Antigravity, whose AI features are idle without an account.
- **Background services.** Cursor and Antigravity IDE start extra processes (language server, agent services) even when signed out. Those count toward their totals because they are part of the cost of running the app.
- **Antigravity (agent app) and OpenCode Desktop are not editors.** They are Electron agent-manager shells. They get no workspace and have no workbench mark, so compare them only on first window, memory, CPU and processes.
- **Network.** Both agent apps run an electron-updater that downloads, and for Antigravity installs on quit, a newer build. Their Chromium network stack is therefore pointed at a dead proxy (`--proxy-server=127.0.0.1:9`). Localhost sidecars and Node/Go child processes still have network access. The VS Code-family apps have full network access with `update.mode: none`.
- **OpenCode ignores `--user-data-dir`.** It pins its own profile path, so it runs only on CI, where the profile is throwaway.
- **Single idle sample per app.** Memory and CPU come from one 60 s window each, so treat differences under about 10% as noise.
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

