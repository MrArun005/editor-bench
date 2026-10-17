#!/usr/bin/env python3
"""results/raw-runs.jsonl + machine.json -> results/summary.json, REPORT.md, report.html."""
import html, json, os, statistics
from collections import defaultdict

import stats

REPO = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get('BENCH_RESULTS', os.path.join(REPO, 'results'))
M = json.load(open(os.path.join(RES, 'machine.json')))
RUNS = [json.loads(l) for l in open(os.path.join(RES, 'raw-runs.jsonl')) if l.strip()]
APPS = list(M['apps'])                         # arms in run order: selected apps, patched build, variants
VSCODE_FAMILY = {a for a in APPS if M['apps'][a].get('vscode_base')}
REFS = [r for r in ('vscode', 'friedliver') if r in APPS]   # A/B baselines
HI = lambda a: a.startswith('friedliver')


def value(r, key):
    """A run's metric: a record field, or a startup phase computed from its perf marks."""
    if key in r:
        return r[key]
    return stats.phases(r.get('marks') or {}).get(key)


def vals(app, kind, key):
    return [v for r in RUNS if r['app'] == app and r['kind'] == kind and not r.get('error')
            for v in [value(r, key)] if v is not None]


def agg(app, kind, key):
    xs = vals(app, kind, key)
    if not xs:
        return None
    m = statistics.median(xs)
    return dict(median=round(m) if abs(m) >= 10 else round(m, 2), p90=stats.p90(xs), min=min(xs), max=max(xs),
                n=len(xs), runs=xs)


def slowest(app, n=8):
    """Contributions VS Code logged as slow (renderer.log, warn level), over the cold runs: median ms, runs seen."""
    seen = defaultdict(list)
    cold = [r for r in RUNS if r['app'] == app and r['kind'] == 'cold' and 'slow_contribs' in r]
    for r in cold:
        for cid, ms in r['slow_contribs']:
            seen[cid].append(ms)
    top = sorted(seen.items(), key=lambda kv: -statistics.median(kv[1]))[:n]
    return [(cid, round(statistics.median(ms)), len(ms), len(cold)) for cid, ms in top]


def launch_split(app):
    """Launch 1 (the warm-up: fresh profile, every cache empty) vs launches 2-6 (the 5 cold runs), for the
    metrics a compile cache should move, plus the node compile-cache folder after each launch."""
    warm = next((r for r in RUNS if r['app'] == app and r['kind'] == 'warmup' and not r.get('error')), None)
    if not warm or 'marks' not in warm:
        return None
    out = {}
    for label, key in (('Workbench ready', 'workbench_ms'), ('Extension host ready', 'exthost_ms'),
                       ('Process start → main started', 'Process start → main started'),
                       ('Workbench ready → extension host ready', 'Workbench ready → extension host ready')):
        later = vals(app, 'cold', key)
        out[label] = dict(first=value(warm, key), later=round(statistics.median(later)) if later else None,
                          later_min=min(later, default=None), later_max=max(later, default=None))
    cache = [r.get('node_cache') for r in RUNS if r['app'] == app and r['kind'] in ('warmup', 'cold')]
    out['node_cache_kb'] = [c['kb'] if c else None for c in cache]
    return out


def cpu_by_proc(app):
    """Idle CPU per process name, median over the idle runs (a name missing from a run counts as 0)."""
    runs = [r['cpu_by_proc'] for r in RUNS if r['app'] == app and r['kind'] == 'idle' and r.get('cpu_by_proc')]
    names = {n for r in runs for n in r}
    return dict(sorted(((n, round(statistics.median(r.get(n, 0) for r in runs), 2)) for n in names),
                       key=lambda kv: -kv[1])) if runs else None


IDLE_KEYS = ('n_procs', 'rss_mb', 'footprint_mb', 'cpu_pct', 'cpu_open_pct')
S = {}
for a in APPS:
    s = S[a] = dict(label=M['apps'][a]['label'], version=M['apps'][a]['version'], base=M['apps'][a].get('base'),
                    settings=M['apps'][a].get('settings'),
                    vscode_base=M['apps'][a].get('vscode_base'), install_mb=M['apps'][a]['install_mb'],
                    cold_window_ms=agg(a, 'cold', 'window_ms'), cold_workbench_ms=agg(a, 'cold', 'workbench_ms'),
                    cold_exthost_ms=agg(a, 'cold', 'exthost_ms'),
                    cold_restore_ms=agg(a, 'cold', 'restore_ms'), big5mb_restore_ms=agg(a, 'big5mb', 'restore_ms'),
                    big5mb_workbench_ms=agg(a, 'big5mb', 'workbench_ms'),
                    phases={p: agg(a, 'cold', p) for p, _, _ in stats.PHASES},
                    slowest_contribs=slowest(a),
                    compile_cache=sorted({l.split(' (status')[0].replace('[node-compile-cache] ', '') + ': '
                                          + l.split('status: ')[1].split(',')[0]
                                          for r in RUNS if r['app'] == a for l in r.get('compile_cache') or [] if 'status: ' in l}),
                    compile_cache_line=next((l for r in RUNS if r['app'] == a for l in r.get('compile_cache') or []
                                             if 'extension-host' in l), None),
                    launches=launch_split(a),
                    **{f'idle_{k}': agg(a, 'idle', k) for k in IDLE_KEYS},
                    **{f'files20_{k}': agg(a, 'files20', k) for k in ('n_procs', 'rss_mb', 'footprint_mb')},
                    **{f'bigrepo_{k}': agg(a, 'bigrepo', k) for k in IDLE_KEYS},
                    **{f'{kind.replace("-", "_")}_{k}': agg(a, kind, k)
                       for kind in ('shell-fast', 'shell-slow') for k in ('exthost_ms', 'search_ms', 'workbench_ms')},
                    idle_cpu_by_proc=cpu_by_proc(a),
                    errors=[f"{r['kind']}#{r['i']}: {r['error']}" for r in RUNS if r['app'] == a and r.get('error')])
    if s['big5mb_restore_ms'] and s['cold_restore_ms']:
        s['open5mb_delta_ms'] = s['big5mb_restore_ms']['median'] - s['cold_restore_ms']['median']

# A/B: (label, run kind, key, unit). Lower is better for all of them.
METRICS = ([('Workbench ready', 'cold', 'workbench_ms', 'ms'), ('First window', 'cold', 'window_ms', 'ms'),
            ('Extension host ready', 'cold', 'exthost_ms', 'ms')]
           + [(p, 'cold', p, 'ms') for p, _, _ in stats.PHASES[:stats.N_MAIN_PHASES + 3]]
           + [('Idle footprint', 'idle', 'footprint_mb', 'mb'), ('Idle RSS', 'idle', 'rss_mb', 'mb'),
              ('Idle CPU (ready+60→120 s)', 'idle', 'cpu_pct', 'pct'), ('CPU, first 60 s after window', 'idle', 'cpu_open_pct', 'pct'),
              ('20 files: footprint', 'files20', 'footprint_mb', 'mb'),
              ('Slow shell: extension host ready', 'shell-slow', 'exthost_ms', 'ms'),
              ('Slow shell: first file-search result', 'shell-slow', 'search_ms', 'ms'),
              ('Fast shell: first file-search result', 'shell-fast', 'search_ms', 'ms'),
              ('Large repo: footprint', 'bigrepo', 'footprint_mb', 'mb'),
              ('Large repo: CPU first 60 s', 'bigrepo', 'cpu_open_pct', 'pct'),
              ('Large repo: idle CPU', 'bigrepo', 'cpu_pct', 'pct')])
AB = {}
for ref in REFS:
    for a in APPS:
        if a == ref or a not in VSCODE_FAMILY or (ref == 'friedliver' and not HI(a)):
            continue
        ab_rows = []
        for label, kind, key, unit in METRICS:
            c = stats.compare(vals(ref, kind, key), vals(a, kind, key), unit)
            if c:
                ab_rows.append(dict(metric=label, unit=unit, **c))
        if ab_rows:
            AB[f'{a} vs {ref}'] = dict(arm=a, ref=ref, rows=ab_rows)
json.dump(dict(machine=M, apps=S, ab=AB), open(os.path.join(RES, 'summary.json'), 'w'), indent=2)


def med(d):
    return '–' if not d else f"{d['median']:,}"


def num(x, unit=''):
    return '–' if x is None else f'{x:,.0f}{unit}' if isinstance(x, (int, float)) and abs(x) >= 10 else f'{x}{unit}'


def mr(d):                                     # median [min–max]
    if not d:
        return '–'
    f = (lambda v: f'{v:,.0f}') if abs(d['median']) >= 10 else (lambda v: f'{v:g}')
    return f"{f(d['median'])} [{f(d['min'])}–{f(d['max'])}]" if d['n'] > 1 else f(d['median'])


# ------------------------------------------------------------------------------------- REPORT.md
where = 'GitHub Actions runner' if M.get('ci') else 'owner laptop'
fam = [a for a in APPS if a in VSCODE_FAMILY]
md = [f"# Editor benchmark — phases + A/B ({M['date']}, {where})", '',
      f"Machine: **{M['model']}**, {M['chip']}, {M['cores']} cores, {M['ram']} RAM, macOS {M['macos']}, power: {M['power_at_start']}."
      + (f" Run: {M['run_url']}" if M.get('run_url') else ''), '',
      f"Scenarios: {', '.join(M.get('scenarios') or []) or 'none'}.", '',
      '## Arms', '', '| Arm | Version | VS Code base | Install size (MB) | Source / verification |', '|---|---|---|---:|---|']
fetch = M.get('fetch') or {}
for a in APPS:
    s = S[a]
    f = fetch.get(a, {})
    if s['base']:
        ver = f"same binary as {S[s['base']]['label'] if s['base'] in S else s['base']} + settings below"
    elif f:
        ver = (f"{f['version']}; " if a == 'friedliver-patched' and f.get('version') else '') + \
              f"{f.get('hash', '')}; codesign {f.get('codesign', '?')}"
    else:
        ver = 'local /Applications install'
    md.append(f"| {s['label']} | {s['version']} | {s['vscode_base'] or 'n/a (not a VS Code fork)'} | {s['install_mb']:,} | {ver} |")
for a, f in fetch.items():
    if f.get('status', 'ok') != 'ok':
        md.append(f"| {a} | – | – | – | **{f['status']}** |")
for a in APPS:
    if S[a]['settings']:
        md += ['', f"Settings added for **{S[a]['label']}** (on top of `update.mode: none`):", '', '```json',
               json.dumps(S[a]['settings'], indent=1), '```']
mp = lambda d: f"{d['median']:,} ({d['p90']:,})" if d else '–'
md += ['', '## Cold start (1 warm-up discarded, then 5 runs, round-robin across arms)', '',
       '| Arm | Launch → workbench ready, median (p90) ms | Launch → extension host ready, median (p90) ms | Launch → first window, median (p90) ms |',
       '|---|---:|---:|---:|']
for a in APPS:
    md.append(f"| {S[a]['label']} | {mp(S[a]['cold_workbench_ms'])} | {mp(S[a]['cold_exthost_ms'])} | {mp(S[a]['cold_window_ms'])} |")
if fam:
    md += ['', "## Startup phases (cold runs, median ms, from the product's own perf marks)", '',
           'The first seven rows are consecutive and add up to process start → workbench ready (each is a median, so the sum is close to the workbench median, not equal). The rows after the divider break that down or cover the extension host.', '',
           '| Phase | Marks | ' + ' | '.join(S[a]['label'] for a in fam) + ' |', '|---|---|' + '---:|' * len(fam)]
    for k, (p, x, y) in enumerate(stats.PHASES):
        if k == stats.N_MAIN_PHASES:
            md.append('| — | | ' + ' | '.join('' for _ in fam) + ' |')
        md.append(f"| {p} | `{x.replace('code/', '')}` → `{y.replace('code/', '')}` | "
                  + ' | '.join(med(S[a]['phases'][p]) for a in fam) + ' |')
    md += ['', '### Slowest workbench contributions (renderer.log)', '',
           'VS Code logs a contribution at warn level only when creating it took over 20 ms (BlockStartup/BlockRestore) or 100 ms (later phases). Median ms over the cold runs it appeared in (runs seen / cold runs).', '']
    for a in fam:
        sc = S[a]['slowest_contribs']
        md.append(f"- **{S[a]['label']}**: " + (', '.join(f'`{c}` {ms} ms ({k}/{n})' for c, ms, k, n in sc)
                                              if sc else 'none above the threshold'))
    md += ['', '### Node compile cache', '',
           'Status per process, from the `[node-compile-cache]` line each process writes to its log; folder size of `CachedData/<commit>/node` after each launch (launch 1 = warm-up, 2–6 = the cold runs).', '',
           '| Arm | Status per process | Folder KB after launches 1…6 |', '|---|---|---|']
    for a in fam:
        L = S[a]['launches'] or {}
        md.append(f"| {S[a]['label']} | {'; '.join(S[a]['compile_cache']) or 'no status line'} | "
                  f"{' → '.join('–' if k is None else str(k) for k in L.get('node_cache_kb', [])) or '–'} |")
    ext = [(S[a]['label'], S[a]['compile_cache_line']) for a in fam if S[a]['compile_cache_line']]
    if ext:
        md += [''] + [f'- {l}: `{c}`' for l, c in ext]
    md += ['', '### Launch 1 (fresh profile, empty caches) vs launches 2–6', '',
           '| Arm | Metric | Launch 1 | Launches 2–6 median [min–max] | Δ |', '|---|---|---:|---:|---:|']
    for a in fam:
        for metric, d in (S[a]['launches'] or {}).items():
            if metric == 'node_cache_kb' or d['first'] is None or d['later'] is None:
                continue
            md.append(f"| {S[a]['label']} | {metric} | {d['first']:,} | {d['later']:,} [{d['later_min']:,}–{d['later_max']:,}] | {d['later'] - d['first']:+,} |")
md += ['', '## Memory, processes and idle CPU', '',
       'Workspace open; snapshot at ready + 60 s; idle CPU over the next 60 s. Median [min–max] of 3 runs.', '',
       '| Arm | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | CPU in the first 60 s (%) | After 20 files: footprint / RSS (MB) |',
       '|---|---:|---:|---:|---:|---:|---:|']
for a in APPS:
    s = S[a]
    f20 = f"{med(s['files20_footprint_mb'])} / {med(s['files20_rss_mb'])}" if s['files20_rss_mb'] else 'n/a'
    md.append(f"| {s['label']} | {med(s['idle_n_procs'])} | {mr(s['idle_footprint_mb'])} | {mr(s['idle_rss_mb'])} | "
              f"{mr(s['idle_cpu_pct'])} | {mr(s['idle_cpu_open_pct'])} | {f20} |")
byp = [a for a in APPS if S[a]['idle_cpu_by_proc']]
if byp:
    md += ['', '### Idle CPU by process (% of one core, median of the idle runs)', '',
           '| Arm | Processes, highest first |', '|---|---|']
    md += [f"| {S[a]['label']} | " + ', '.join(f'{n} {v:g}' for n, v in S[a]['idle_cpu_by_proc'].items() if v >= 0.05) + ' |'
           for a in byp]
md += ['', '## Opening a 5 MB file (VS Code family only)', '',
       '| Arm | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |', '|---|---:|---:|---:|']
for a in fam:
    s = S[a]
    md.append(f"| {s['label']} | {med(s['big5mb_restore_ms'])} | {med(s['cold_restore_ms'])} | {num(s.get('open5mb_delta_ms'))} |")
sh_arms = [a for a in fam if S[a]['shell_slow_exthost_ms'] or S[a]['shell_fast_exthost_ms']]
if sh_arms:
    dx = lambda f, sl: num(sl['median'] - f['median']) if f and sl else '–'
    md += ['', '## Scenario: slow login shell', '',
           f"`.zshrc` sleeps {M.get('shell_sleep', 1.0):g} s (as nvm or oh-my-zsh can)."
           ' Each arm gets its own profile with a probe extension: it activates on `*` and calls `workspace.findFiles`, the extension-host file search that also serves Quick Open. '
           'Extension host ready is measured from process start (perf mark). File search is measured from just before `open` (wall clock). Median [min–max] of 3 runs, ms.', '',
           '| Arm | Ext host ready, fast shell | Ext host ready, slow shell | Δ | First file-search result, fast shell | Slow shell | Δ |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for a in sh_arms:
        s = S[a]
        md.append(f"| {s['label']} | {mr(s['shell_fast_exthost_ms'])} | {mr(s['shell_slow_exthost_ms'])} | "
                  f"{dx(s['shell_fast_exthost_ms'], s['shell_slow_exthost_ms'])} | {mr(s['shell_fast_search_ms'])} | "
                  f"{mr(s['shell_slow_search_ms'])} | {dx(s['shell_fast_search_ms'], s['shell_slow_search_ms'])} |")
br = [a for a in fam if S[a]['bigrepo_footprint_mb']]
if br:
    b = M.get('bigrepo') or {}
    md += ['', f"## Scenario: large repo ({b.get('repo', '?')} @ {str(b.get('commit', ''))[:10]}, {b.get('files', 0):,} files)", '',
           'Median [min–max] of 3 runs.', '',
           '| Arm | Processes | Footprint (MB) | CPU in the first 60 s after the window (%) | Idle CPU, ready+60→120 s (%) |', '|---|---:|---:|---:|---:|']
    for a in br:
        s = S[a]
        md.append(f"| {s['label']} | {med(s['bigrepo_n_procs'])} | {mr(s['bigrepo_footprint_mb'])} | {mr(s['bigrepo_cpu_open_pct'])} | {mr(s['bigrepo_cpu_pct'])} |")
if AB:
    md += ['', '## A/B deltas', '',
           'Δ = arm median − baseline median (negative = the arm is faster or smaller). **better** or **worse** only when |Δ| is larger than '
           "either side's min–max spread **and** at least 3 % (times), 10 MB (memory) or 1 point (CPU). Otherwise *noise*. "
           'This is one run; the keep rule needs the same verdict in two separate CI runs.']
    for ab in AB.values():
        md += ['', f"### {S[ab['arm']]['label']} vs {S[ab['ref']]['label']}", '',
               '| Metric | Baseline median | Arm median | Δ | Δ % | Spread | n (base/arm) | Verdict |', '|---|---:|---:|---:|---:|---:|---:|---|']
        for r in ab['rows']:
            f = (lambda v: f'{v:,.0f}') if r['unit'] != 'pct' else (lambda v: f'{v:.2f}')
            d = f'{r["delta"]:+,.0f}' if r['unit'] != 'pct' else f'{r["delta"]:+.2f}'
            pct = '–' if r['pct'] is None else f"{r['pct']:+.1f} %"
            v = {'better': '**better**', 'worse': '**worse**', 'noise': 'noise'}[r['verdict']]
            md.append(f"| {r['metric']} | {f(r['base'])} | {f(r['arm'])} | {d} | {pct} | {f(r['spread'])} | {r['n'][0]}/{r['n'][1]} | {v} |")
errs = [(S[a]['label'], e) for a in APPS for e in S[a]['errors']]
if errs:
    md += ['', '## Run errors', ''] + [f'- {l}: {e}' for l, e in errs]
md += ['', open(os.path.join(REPO, 'METHOD.md')).read()]
open(os.path.join(REPO, 'REPORT.md'), 'w').write('\n'.join(md) + '\n')


# ------------------------------------------------------------------------------------ report.html
def bars(title, unit, rows, note=''):
    """Horizontal bar chart in inline SVG. rows: [(label, value, highlight)]. Lower is better."""
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return ''
    vmax = max(v for _, v, _ in rows) or 1
    h, lw, W = 44, 330, 1000
    out = [f'<svg viewBox="0 0 {W} {len(rows) * h + 8}" role="img" aria-label="{html.escape(title)}" width="100%">']
    for i, (label, v, hi) in enumerate(sorted(rows, key=lambda r: r[1])):
        y = i * h + 4
        w = max(2, (W - lw - 130) * v / vmax)
        out.append(f'<text x="{lw - 12}" y="{y + 27}" text-anchor="end" class="lbl{" hi" if hi else ""}">{html.escape(label)}</text>'
                   f'<rect x="{lw}" y="{y + 6}" width="{w:.1f}" height="{h - 12}" rx="4" class="bar{" hi" if hi else ""}"/>'
                   f'<text x="{lw + w + 8:.1f}" y="{y + 27}" class="val">{(f"{v:,.1f}" if v < 10 else f"{v:,.0f}")}{unit}</text>')
    out.append('</svg>')
    return (f'<section class="card"><h2>{html.escape(title)}</h2>'
            f'<p class="note">{html.escape(note)} Lower is better.</p>{"".join(out)}</section>')


def phase_chart():
    """Stacked bars: the consecutive startup phases per VS Code-family arm (medians)."""
    main = [p for p, _, _ in stats.PHASES[:stats.N_MAIN_PHASES]]
    data = [(a, [((S[a]['phases'][p] or {}).get('median') or 0) for p in main]) for a in fam]
    data = [(a, v) for a, v in data if sum(v)]
    if not data:
        return ''
    vmax = max(sum(v) for _, v in data)
    h, lw, W = 46, 330, 1000
    out = [f'<svg viewBox="0 0 {W} {len(data) * h + 70}" role="img" aria-label="Startup phases" width="100%">']
    for i, (a, v) in enumerate(data):
        y, x = i * h + 4, lw
        out.append(f'<text x="{lw - 12}" y="{y + 28}" text-anchor="end" class="lbl{" hi" if HI(a) else ""}">{html.escape(S[a]["label"])}</text>')
        for k, ms in enumerate(v):
            w = (W - lw - 110) * max(ms, 0) / vmax
            out.append(f'<rect x="{x:.1f}" y="{y + 6}" width="{w:.1f}" height="{h - 12}" class="ph{k}"><title>{html.escape(main[k])}: {ms:,} ms</title></rect>')
            x += w
        out.append(f'<text x="{x + 8:.1f}" y="{y + 28}" class="val">{sum(v):,} ms</text>')
    ly = len(data) * h + 14
    for k, p in enumerate(main):
        lx, yy = 10 + (k % 4) * 245, ly + (k // 4) * 26
        out.append(f'<rect x="{lx}" y="{yy}" width="16" height="16" rx="3" class="ph{k}"/><text x="{lx + 22}" y="{yy + 14}" class="leg">{html.escape(p)}</text>')
    out.append('</svg>')
    return ('<section class="card wide"><h2>Startup phases, process start → workbench ready (median)</h2>'
            f'<p class="note">From the product’s own perf marks; hover a segment for its phase and value.</p>{"".join(out)}</section>')


def delta_chart(ab):
    rows = [r for r in ab['rows'] if r['pct'] is not None]
    if not rows:
        return ''
    lim = max(10, min(100, max(abs(r['pct']) for r in rows)))
    h, lw, W = 34, 380, 1000
    half = (W - lw - 90) / 2
    mid = lw + half
    out = [f'<svg viewBox="0 0 {W} {len(rows) * h + 8}" role="img" aria-label="delta percent" width="100%">',
           f'<line x1="{mid}" y1="0" x2="{mid}" y2="{len(rows) * h + 8}" class="axis"/>']
    for i, r in enumerate(rows):
        y = i * h + 4
        p = max(-lim, min(lim, r['pct']))
        w = abs(p) / lim * half
        x = mid - w if p < 0 else mid
        out.append(f'<text x="{lw - 12}" y="{y + 21}" text-anchor="end" class="lbl small">{html.escape(r["metric"])}</text>'
                   f'<rect x="{x:.1f}" y="{y + 5}" width="{max(w, 1.5):.1f}" height="{h - 10}" rx="3" class="d-{r["verdict"]}"/>'
                   f'<text x="{(mid + w + 6) if p >= 0 else (mid - w - 6):.1f}" y="{y + 21}" text-anchor="{"start" if p >= 0 else "end"}" class="val small">{r["pct"]:+.1f}%</text>')
    out.append('</svg>')
    return (f'<section class="card"><h2>{html.escape(S[ab["arm"]]["label"])} vs {html.escape(S[ab["ref"]]["label"])}: Δ %</h2>'
            '<p class="note">Left of the line = the arm is lower (better). Green or red = beyond noise; grey = noise. Axis clipped at ±'
            f'{lim:.0f} %.</p>{"".join(out)}</section>')


def rows(key, family_only=False):
    return [(S[a]['label'], (S[a][key] or {}).get('median') if isinstance(S[a][key], dict) or S[a][key] is None else S[a][key], HI(a))
            for a in APPS if not family_only or a in VSCODE_FAMILY]


kpis = []
for t, key, fm in (('Fastest to workbench', 'cold_workbench_ms', lambda v: f'{v:,} ms'),
                   ('Smallest idle footprint', 'idle_footprint_mb', lambda v: f'{v:,.0f} MB'),
                   ('Quietest at idle', 'idle_cpu_pct', lambda v: f'{v} % CPU')):
    cands = [(v, l) for l, v, _ in rows(key) if v is not None]
    if cands:
        v, l = min(cands)
        kpis.append((t, fm(v), l))

charts = ''.join([
    bars('Cold start: launch → workbench ready (median)', ' ms', rows('cold_workbench_ms', True),
         'VS Code family only; from the product’s own startup marks (process start → code/didStartWorkbench).'),
    bars('Cold start: launch → extension host ready (median)', ' ms', rows('cold_exthost_ms', True),
         'Process start → code/extHost/ready.'),
    bars('Cold start: launch → first window (median)', ' ms', rows('cold_window_ms'),
         'All apps; external clock from `open` until the window server lists the app’s first normal window.'),
    bars('Physical footprint at idle (median of 3)', ' MB', rows('idle_footprint_mb'),
         'Whole process tree, `footprint` total (shared pages counted once).'),
    bars('Physical footprint after opening 20 files (median of 3)', ' MB', rows('files20_footprint_mb', True), 'VS Code family only.'),
    bars('Idle CPU, average over 60 s (median of 3)', ' %', rows('idle_cpu_pct'), '% of one core, summed over the process tree.'),
    bars('Slow shell: first file-search result (median)', ' ms', rows('shell_slow_search_ms', True), 'From `open`; `.zshrc` sleeps 1 s.'),
    bars('Large repo: CPU in the first 60 s (median)', ' %', rows('bigrepo_cpu_open_pct', True), 'Watcher, git and extension host on the large repo.'),
    bars('Install size on disk', ' MB', [(S[a]['label'], S[a]['install_mb'], HI(a)) for a in APPS if not S[a]['base']],
         '`du` of the .app bundle.'),
])
deltas = ''.join(delta_chart(ab) for ab in AB.values())
table = ''.join(f"<tr><td>{html.escape(S[a]['label'])}</td><td>{html.escape(str(S[a]['version']))}</td>"
                f"<td>{med(S[a]['cold_workbench_ms'])}</td><td>{med(S[a]['cold_exthost_ms'])}</td><td>{med(S[a]['cold_window_ms'])}</td>"
                f"<td>{mr(S[a]['idle_footprint_mb'])}</td><td>{mr(S[a]['idle_rss_mb'])}</td>"
                f"<td>{mr(S[a]['idle_cpu_pct'])}</td><td>{med(S[a]['idle_n_procs'])}</td>"
                f"<td>{med(S[a]['files20_footprint_mb'])}</td><td>{num(S[a].get('open5mb_delta_ms'))}</td>"
                f"<td>{S[a]['install_mb']:,}</td></tr>" for a in APPS)
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Editor Benchmark</title><style>
:root{{--bg:#0f1115;--panel:#171a21;--line:#262b36;--text:#e6e8ee;--muted:#9aa3b2;--bar:#4b5566;--hi:#f2a33a;--good:#3fb27f;--bad:#e5534b;
--p0:#5b6b85;--p1:#6f86b3;--p2:#8aa4d6;--p3:#4f9d9a;--p4:#f2a33a;--p5:#c77dba;--p6:#d9d27a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}}
main{{padding:24px 28px}}h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:16px;margin:0 0 4px}}
.sub,.note{{color:var(--muted);margin:0 0 12px}}.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:18px 0}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}.kpi b{{display:block;font-size:26px;color:var(--hi)}}
.kpi span{{color:var(--muted);font-size:13px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(560px,1fr));gap:14px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;overflow:hidden}}.wide{{margin-top:14px}}
svg text{{font-size:21px;fill:var(--text)}}svg .lbl{{fill:var(--muted)}}svg .lbl.hi{{fill:var(--hi);font-weight:600}}svg .val{{fill:var(--text)}}
svg .small{{font-size:17px}}svg .leg{{font-size:15px;fill:var(--muted)}}svg .axis{{stroke:var(--line);stroke-width:2}}
.bar{{fill:var(--bar)}}.bar.hi{{fill:var(--hi)}}.d-better{{fill:var(--good)}}.d-worse{{fill:var(--bad)}}.d-noise{{fill:var(--bar)}}
.ph0{{fill:var(--p0)}}.ph1{{fill:var(--p1)}}.ph2{{fill:var(--p2)}}.ph3{{fill:var(--p3)}}.ph4{{fill:var(--p4)}}.ph5{{fill:var(--p5)}}.ph6{{fill:var(--p6)}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-variant-numeric:tabular-nums}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}
th{{color:var(--muted);font-weight:500;font-size:13px}}.wrap{{overflow-x:auto}}
@media (max-width:640px){{main{{padding:16px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Desktop editor benchmark — phases + A/B</h1>
<p class="sub">{html.escape(M['model'])} · {html.escape(M['chip'])} · {html.escape(M['ram'])} RAM · macOS {html.escape(M['macos'])} · {html.escape(M['date'])} · {where}{f' · <a style="color:var(--hi)" href="{M["run_url"]}">workflow run</a>' if M.get('run_url') else ''}. Throwaway profiles, no extensions, no sign-in. FriedLiver arms highlighted. Full tables in REPORT.md.</p>
<div class="kpis">{''.join(f'<div class="kpi"><span>{html.escape(t)}</span><b>{html.escape(v)}</b><span>{html.escape(s)}</span></div>' for t, v, s in kpis)}</div>
<section class="card"><h2>All numbers (median; [min–max] where there are 3 samples)</h2><div class="wrap"><table><tr><th>Arm</th><th>Version</th><th>Workbench ms</th><th>Ext host ms</th><th>Window ms</th>
<th>Idle footprint MB</th><th>Idle RSS MB</th><th>Idle CPU %</th><th>Procs</th><th>20-file footprint MB</th><th>5 MB open Δ ms</th><th>Install MB</th></tr>{table}</table></div></section>
{phase_chart()}
<div class="grid" style="margin-top:14px">{deltas}</div>
<div class="grid" style="margin-top:14px">{charts}</div>
<p class="note" style="margin-top:18px">Method and caveats: see REPORT.md. Cold start: medians of 5 runs after 1 discarded warm-up. Memory and CPU: medians of 3 idle runs.</p>
</main></body></html>'''
open(os.path.join(REPO, 'report.html'), 'w').write(page)
print('wrote REPORT.md, report.html, results/summary.json')
