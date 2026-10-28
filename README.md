# editor-bench

Reproducible measurements of what code editors cost at idle on macOS: memory, process count and CPU for VS Code, Cursor, Antigravity, OpenCode and [FriedLiver](https://github.com/MrArun005/FriedLiver), each launched one at a time from a throwaway profile in an empty environment.

The headline FriedLiver uses (314 MB idle against 761 MB for VS Code on the same machine) comes from this harness.

- [`METHOD.md`](METHOD.md): how a run is isolated, how processes are attributed to an app, and what is measured
- [`bench.py`](bench.py), [`report.py`](report.py), [`stats.py`](stats.py): run, summarise, and test the results
- [`setup_fixture.sh`](setup_fixture.sh), [`fetch_apps.py`](fetch_apps.py): the shared project fixture and the app versions under test
- [`results/`](results): raw measurements
- [`PHASE2.md`](PHASE2.md): design for a follow-up agent-task benchmark (not run yet)

```bash
./setup_fixture.sh
python3 fetch_apps.py
python3 bench.py          # one app at a time; aborts a run if free memory drops below 2 GB
python3 report.py         # tables from results/
```
