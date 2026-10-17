#!/usr/bin/env python3
"""results/raw-runs.jsonl + machine.json -> results/summary.json, REPORT.md, report.html."""
import html, json, math, os, statistics

REPO = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get('BENCH_RESULTS', os.path.join(REPO, 'results'))
M = json.load(open(os.path.join(RES, 'machine.json')))
RUNS = [json.loads(l) for l in open(os.path.join(RES, 'raw-runs.jsonl')) if l.strip()]
ORDER = ['friedliver', 'cursor', 'antigravity-ide', 'vscode', 'antigravity', 'opencode']
APPS = [a for a in ORDER if a in M['apps']]
VSCODE_FAMILY = {'friedliver', 'cursor', 'antigravity-ide', 'vscode'}

def p90(xs):                                   # nearest-rank; with n=5 this is the slowest run
    xs = sorted(xs)
    return xs[max(0, math.ceil(0.9 * len(xs)) - 1)]

def agg(app, kind, key):
    xs = [r[key] for r in RUNS if r['app'] == app and r['kind'] == kind and r.get(key) is not None]
    return dict(median=round(statistics.median(xs)), p90=p90(xs), n=len(xs), runs=xs) if xs else None

def one(app, kind, key):
    r = next((r for r in RUNS if r['app'] == app and r['kind'] == kind and not r.get('error')), None)
    return r and r.get(key)

S = {}
for a in APPS:
    s = S[a] = dict(label=M['apps'][a]['label'], version=M['apps'][a]['version'],
                    vscode_base=M['apps'][a].get('vscode_base'), install_mb=M['apps'][a]['install_mb'],
                    cold_window_ms=agg(a, 'cold', 'window_ms'), cold_workbench_ms=agg(a, 'cold', 'workbench_ms'),
                    cold_restore_ms=agg(a, 'cold', 'restore_ms'), big5mb_restore_ms=agg(a, 'big5mb', 'restore_ms'),
                    big5mb_workbench_ms=agg(a, 'big5mb', 'workbench_ms'),
                    idle_procs=one(a, 'idle', 'n_procs'), idle_rss_mb=one(a, 'idle', 'rss_mb'),
                    idle_footprint_mb=one(a, 'idle', 'footprint_mb'), idle_cpu_pct=one(a, 'idle', 'cpu_pct'),
                    files20_rss_mb=one(a, 'files20', 'rss_mb'), files20_footprint_mb=one(a, 'files20', 'footprint_mb'),
                    files20_procs=one(a, 'files20', 'n_procs'),
                    errors=[f"{r['kind']}#{r['i']}: {r['error']}" for r in RUNS if r['app'] == a and r.get('error')])
    if s['big5mb_restore_ms'] and s['cold_restore_ms']:
        s['open5mb_delta_ms'] = s['big5mb_restore_ms']['median'] - s['cold_restore_ms']['median']
json.dump(dict(machine=M, apps=S), open(os.path.join(RES, 'summary.json'), 'w'), indent=2)

def med(d):
    return '–' if not d else f"{d['median']:,}"

def num(x, unit=''):
    return '–' if x is None else f'{x:,.0f}{unit}' if isinstance(x, (int, float)) and abs(x) >= 10 else f'{x}{unit}'

# ------------------------------------------------------------------------------------- REPORT.md
where = 'GitHub Actions runner' if M.get('ci') else 'owner laptop'
md = [f"# Editor benchmark — phase 1 ({M['date']}, {where})", '',
      f"Machine: **{M['model']}**, {M['chip']}, {M['cores']} cores, {M['ram']} RAM, macOS {M['macos']}, power: {M['power_at_start']}."
      + (f" Run: {M['run_url']}" if M.get('run_url') else ''), '',
      '## Apps', '', '| App | Version | VS Code base | Install size (MB) | Source / verification |', '|---|---|---|---:|---|']
fetch = M.get('fetch') or {}
for a in APPS:
    f = fetch.get(a, {})
    ver = f"{f.get('hash', '')}; codesign {f.get('codesign', '?')}" if f else 'local /Applications install'
    md.append(f"| {S[a]['label']} | {S[a]['version']} | {S[a]['vscode_base'] or 'n/a (not a VS Code fork)'} | {S[a]['install_mb']:,} | {ver} |")
for a, f in fetch.items():
    if f.get('status', 'ok') != 'ok':
        md.append(f"| {a} | – | – | – | **{f['status']}** |")
md += ['', '## Cold start (1 warm-up discarded, then 5 runs, round-robin across apps)', '',
       '| App | Launch → workbench ready, median (p90) ms | Launch → first window, median (p90) ms |', '|---|---:|---:|']
for a in APPS:
    wb, w = S[a]['cold_workbench_ms'], S[a]['cold_window_ms']
    mp = lambda d: f"{d['median']:,} ({d['p90']:,})" if d else '–'
    md.append(f"| {S[a]['label']} | {mp(wb)} | {mp(w)} |")
md += ['', '## Memory, processes and idle CPU (workspace open; ready + 60 s; CPU averaged over the next 60 s)', '',
       '| App | Processes | Physical footprint (MB) | Sum of RSS (MB) | Idle CPU (% of one core) | After 20 files: footprint / RSS (MB) |',
       '|---|---:|---:|---:|---:|---:|']
for a in APPS:
    s = S[a]
    f20 = f"{num(s['files20_footprint_mb'])} / {num(s['files20_rss_mb'])}" if s['files20_rss_mb'] else 'n/a'
    md.append(f"| {s['label']} | {num(s['idle_procs'])} | {num(s['idle_footprint_mb'])} | {num(s['idle_rss_mb'])} | {num(s['idle_cpu_pct'])} | {f20} |")
md += ['', '## Opening a 5 MB file (VS Code family only)', '',
       '| App | Editor restore with 5 MB file, median ms | Editor restore baseline, median ms | Delta ms |', '|---|---:|---:|---:|']
for a in APPS:
    if a in VSCODE_FAMILY:
        s = S[a]
        md.append(f"| {s['label']} | {med(s['big5mb_restore_ms'])} | {med(s['cold_restore_ms'])} | {num(s.get('open5mb_delta_ms'))} |")
errs = [(S[a]['label'], e) for a in APPS for e in S[a]['errors']]
if errs:
    md += ['', '## Run errors', ''] + [f'- {l}: {e}' for l, e in errs]
md += [open(os.path.join(REPO, 'METHOD.md')).read()]
open(os.path.join(REPO, 'REPORT.md'), 'w').write('\n'.join(md) + '\n')

# ------------------------------------------------------------------------------------ report.html
def bars(title, unit, rows, note=''):
    """Horizontal bar chart in inline SVG. rows: [(label, value, highlight)]. Lower is better."""
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return ''
    vmax = max(v for _, v, _ in rows) or 1
    h, lw, W = 44, 300, 1000
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

def rows(key, sub=None, family_only=False):
    return [(S[a]['label'], (S[a][key] or {}).get(sub) if sub else S[a][key], a == 'friedliver')
            for a in APPS if not family_only or a in VSCODE_FAMILY]

kpis = []
def best(key, sub=None):
    vals = [((S[a][key] or {}).get(sub) if sub else S[a][key], S[a]['label']) for a in APPS]
    return min((v, l) for v, l in vals if v is not None)
try:
    v, l = best('cold_workbench_ms', 'median'); kpis.append(('Fastest to workbench', f'{v:,} ms', l))
except ValueError:
    pass
try:
    v, l = best('idle_footprint_mb'); kpis.append(('Smallest idle footprint', f'{v:,.0f} MB', l))
except ValueError:
    pass
try:
    v, l = best('idle_cpu_pct'); kpis.append(('Quietest at idle', f'{v} % CPU', l))
except ValueError:
    pass
fl = S.get('friedliver')
if fl and fl['cold_workbench_ms']:
    kpis.append(('FriedLiver to workbench', f"{fl['cold_workbench_ms']['median']:,} ms", 'median of 5'))

charts = ''.join([
    bars('Cold start: launch → workbench ready (median)', ' ms', rows('cold_workbench_ms', 'median', True),
         'VS Code family only; from the product’s own startup marks (process start → code/didStartWorkbench).'),
    bars('Cold start: launch → first window (median)', ' ms', rows('cold_window_ms', 'median'),
         'All apps; external clock from `open` until the window server lists the app’s first normal window.'),
    bars('Physical footprint at idle (workspace open, ready + 60 s)', ' MB', rows('idle_footprint_mb'),
         'Whole process tree, `footprint` total (shared pages counted once).'),
    bars('Physical footprint after opening 20 files', ' MB', rows('files20_footprint_mb', None, True), 'VS Code family only.'),
    bars('Idle CPU, average over 60 s', ' %', rows('idle_cpu_pct'), '% of one core, summed over the process tree.'),
    bars('Processes at idle', '', rows('idle_procs'), 'Whole process tree, including language servers and sidecars.'),
    bars('Install size on disk', ' MB', rows('install_mb'), '`du` of the .app bundle.'),
])
table = ''.join(f"<tr><td>{html.escape(S[a]['label'])}</td><td>{html.escape(str(S[a]['version']))}</td>"
                f"<td>{med(S[a]['cold_workbench_ms'])}</td><td>{med(S[a]['cold_window_ms'])}</td>"
                f"<td>{num(S[a]['idle_footprint_mb'])}</td><td>{num(S[a]['idle_rss_mb'])}</td>"
                f"<td>{num(S[a]['idle_cpu_pct'])}</td><td>{num(S[a]['idle_procs'])}</td>"
                f"<td>{num(S[a]['files20_footprint_mb'])}</td><td>{num(S[a].get('open5mb_delta_ms'))}</td>"
                f"<td>{S[a]['install_mb']:,}</td></tr>" for a in APPS)
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Editor Benchmark</title><style>
:root{{--bg:#0f1115;--panel:#171a21;--line:#262b36;--text:#e6e8ee;--muted:#9aa3b2;--bar:#4b5566;--hi:#f2a33a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}}
main{{padding:24px 28px}}h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:16px;margin:0 0 4px}}
.sub,.note{{color:var(--muted);margin:0 0 12px}}.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:18px 0}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}.kpi b{{display:block;font-size:26px;color:var(--hi)}}
.kpi span{{color:var(--muted);font-size:13px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(560px,1fr));gap:14px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;overflow:hidden}}
svg text{{font-size:21px;fill:var(--text)}}svg .lbl{{fill:var(--muted)}}svg .lbl.hi{{fill:var(--hi);font-weight:600}}svg .val{{fill:var(--text)}}
.bar{{fill:var(--bar)}}.bar.hi{{fill:var(--hi)}}table{{width:100%;border-collapse:collapse;margin-top:8px;font-variant-numeric:tabular-nums}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}
th{{color:var(--muted);font-weight:500;font-size:13px}}.wrap{{overflow-x:auto}}
@media (max-width:640px){{main{{padding:16px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Desktop AI editor benchmark — phase 1</h1>
<p class="sub">{html.escape(M['model'])} · {html.escape(M['chip'])} · {html.escape(M['ram'])} RAM · macOS {html.escape(M['macos'])} · {html.escape(M['date'])} · {where}{f' · <a style="color:var(--hi)" href="{M["run_url"]}">workflow run</a>' if M.get('run_url') else ''}. Throwaway profiles, no extensions, no sign-in, no AI usage. FriedLiver highlighted.</p>
<div class="kpis">{''.join(f'<div class="kpi"><span>{html.escape(t)}</span><b>{html.escape(v)}</b><span>{html.escape(s)}</span></div>' for t, v, s in kpis)}</div>
<section class="card"><h2>All numbers</h2><div class="wrap"><table><tr><th>App</th><th>Version</th><th>Workbench ms</th><th>Window ms</th>
<th>Idle footprint MB</th><th>Idle RSS MB</th><th>Idle CPU %</th><th>Procs</th><th>20-file footprint MB</th><th>5 MB open Δ ms</th><th>Install MB</th></tr>{table}</table></div></section>
<div class="grid" style="margin-top:14px">{charts}</div>
<p class="note" style="margin-top:18px">Method and caveats: see REPORT.md. Medians of 5 runs after 1 discarded warm-up; memory/CPU from a single idle run per app.</p>
</main></body></html>'''
open(os.path.join(REPO, 'report.html'), 'w').write(page)
print('wrote REPORT.md, report.html, results/summary.json')
