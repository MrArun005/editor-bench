#!/usr/bin/env python3
"""HTML report for a token-bench results directory: python3 report.py DIR -> DIR/report.html.
Medians over repetitions, [min-max] spread, comparisons only inside a parity group."""
import html, json, os, statistics, sys

GROUP_BASELINE = {'anthropic': 'claude', 'openai': 'codex', 'google': 'gemini'}
CATS = [('input', 'Input (uncached)', '#5b8def'), ('cache_write', 'Cache write', '#c08cf0'),
        ('cache_read', 'Cache read', '#4fb39a'), ('output', 'Output', '#e7a33e')]


def load(d):
    rows = []
    with open(os.path.join(d, 'results.jsonl')) as f:
        rows = [json.loads(l) for l in f if l.strip()]
    run = {}
    if os.path.exists(os.path.join(d, 'run.json')):
        with open(os.path.join(d, 'run.json')) as f:
            run = json.load(f)
    extra = {}
    for name in ('context-replay.json',):
        p = os.path.join(d, name)
        if os.path.exists(p):
            with open(p) as f:
                extra[name] = json.load(f)
    return rows, run, extra


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def cell(rows, arm, scn):
    return [r for r in rows if r['arm'] == arm and r['scenario'] == scn]


def summarize(rows):
    """{(arm, scenario): medians} and per-arm totals (sum over scenarios of the medians)."""
    arms = list(dict.fromkeys(r['arm'] for r in rows))
    scns = sorted(set(r['scenario'] for r in rows))
    cells, totals = {}, {}
    for a in arms:
        t = {k: None for k in ('cost_usd', 'tool_calls', 'bytes_read', 'wall_s', 'interventions')}  # None = not observable
        t.update({k: 0 for k, _, _ in CATS}, total_tokens=0)
        t.update(ok=0, n=0, group=None, model=None, unreported=0, missing=[])
        for s in scns:
            rs = cell(rows, a, s)
            if not rs:
                t['missing'].append(s)
                continue
            c = {'total_tokens': med([r['total_tokens'] for r in rs]),
                 'min': min(r['total_tokens'] for r in rs), 'max': max(r['total_tokens'] for r in rs),
                 'cost_usd': med([r['cost_usd'] for r in rs]), 'tool_calls': med([r['tool_calls'] for r in rs]),
                 'bytes_read': med([r['bytes_read'] for r in rs]), 'wall_s': med([r['wall_s'] for r in rs]),
                 'ok': sum(1 for r in rs if r['success']), 'n': len(rs),
                 'interventions': med([r.get('interventions', 0) for r in rs]),
                 'unreported': any(not r.get('usage_reported', True) for r in rs)}
            for k, _, _ in CATS:
                c[k] = med([r['tokens'][k] for r in rs])
            cells[(a, s)] = c
            for k in ('total_tokens', 'cost_usd', 'tool_calls', 'bytes_read', 'wall_s', 'interventions') + tuple(k for k, _, _ in CATS):
                if c[k] is not None:
                    t[k] = (t[k] or 0) + c[k]
            t['ok'] += c['ok']
            t['n'] += c['n']
            t['unreported'] += c['unreported']
            t['group'], t['model'] = rs[0]['group'], rs[0]['model']
        totals[a] = t
    return arms, scns, cells, totals


def fmt(n, unit=''):
    if n is None:
        return '<span class="muted">n/a</span>'
    if unit == '$':
        return f'${n:,.3f}'
    if unit == 's':
        return f'{n:,.0f} s'
    if abs(n) >= 1e6:
        return f'{n / 1e6:.2f}M'
    if abs(n) >= 1e3:
        return f'{n / 1e3:.1f}k'
    return f'{n:,.0f}'


def delta(v, base):
    if not base or v is None:
        return ''
    d = (v - base) / base * 100
    cls = 'good' if d < -3 else 'bad' if d > 3 else 'muted'
    return f' <span class="{cls}">{d:+.0f}%</span>'


def stacked_bars(arms, totals):
    """Horizontal stacked bars of token categories per arm, one scale for all."""
    w, lh, left = 1000, 30, 170
    mx = max((totals[a]['total_tokens'] for a in arms), default=1) or 1
    out = [f'<svg viewBox="0 0 {w} {lh * len(arms) + 34}" class="chart" role="img" aria-label="Tokens per arm by category">']
    for i, a in enumerate(arms):
        y, x = i * lh + 4, left
        out.append(f'<text x="{left - 8}" y="{y + 17}" text-anchor="end" class="lbl">{html.escape(a)}</text>')
        for k, name, color in CATS:
            bw = (w - left - 90) * (totals[a][k] / mx)
            if bw > 0:
                out.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="22" fill="{color}"><title>{html.escape(a)} {name}: {totals[a][k]:,.0f}</title></rect>')
            x += bw
        out.append(f'<text x="{x + 6:.1f}" y="{y + 17}" class="val">{fmt(totals[a]["total_tokens"])}</text>')
    ly = lh * len(arms) + 22
    lx = left
    for k, name, color in CATS:
        out.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" fill="{color}"/><text x="{lx + 18}" y="{ly}" class="lbl">{name}</text>')
        lx += 160
    out.append('</svg>')
    return ''.join(out)


def scenario_bars(arms, scns, cells, titles):
    """Small multiples: one panel per scenario, median total tokens per arm with min-max whisker."""
    panels = []
    for s in scns:
        present = [a for a in arms if (a, s) in cells]
        mx = max((cells[(a, s)]['max'] for a in present), default=1) or 1
        w, lh, left = 460, 22, 140
        svg = [f'<svg viewBox="0 0 {w} {lh * len(present) + 6}" class="chart" role="img" aria-label="{s} tokens per arm">']
        for i, a in enumerate(present):
            c, y = cells[(a, s)], i * lh + 3
            scale = (w - left - 60) / mx
            svg.append(f'<text x="{left - 6}" y="{y + 13}" text-anchor="end" class="lbl">{html.escape(a)}</text>')
            fill = '#5b8def' if c['ok'] == c['n'] else '#d9534f'
            svg.append(f'<rect x="{left}" y="{y}" width="{c["total_tokens"] * scale:.1f}" height="16" fill="{fill}"><title>{a}: median {c["total_tokens"]:,.0f}, {c["ok"]}/{c["n"]} passed</title></rect>')
            if c['max'] > c['min']:
                svg.append(f'<line x1="{left + c["min"] * scale:.1f}" x2="{left + c["max"] * scale:.1f}" y1="{y + 8}" y2="{y + 8}" class="whisker"/>')
            svg.append(f'<text x="{left + c["total_tokens"] * scale + 5:.1f}" y="{y + 13}" class="val">{fmt(c["total_tokens"])}</text>')
        svg.append('</svg>')
        panels.append(f'<figure><figcaption>{s} {html.escape(titles.get(s, ""))}</figcaption>{"".join(svg)}</figure>')
    return '<div class="grid">' + ''.join(panels) + '</div>'


def render(d):
    rows, run, extra = load(d)
    arms, scns, cells, totals = summarize(rows)
    titles = {r['scenario']: r.get('title', '') for r in rows}
    modes = sorted(set(r['mode'] for r in rows))
    groups = list(dict.fromkeys(totals[a]['group'] for a in arms))
    banner = ''
    if 'replay' in modes:
        banner = ('<div class="banner">REPLAY OF SYNTHETIC FIXTURES. These numbers test the pipeline and are not measurements of any tool. '
                  'A real run needs the keys listed in the README.</div>')
    if 'manual' in modes:
        banner += '<div class="note">Rows marked manual were read off a GUI by hand (see README, manual protocol).</div>'

    # Totals table, grouped by parity group, deltas against the group's baseline arm.
    trows = []
    for g in groups:
        base = totals.get(GROUP_BASELINE.get(g))
        trows.append(f'<tr class="grp"><td colspan="13">{html.escape(str(g))} group: compared with {GROUP_BASELINE.get(g, "-")}</td></tr>')
        for a in [a for a in arms if totals[a]['group'] == g]:
            t = totals[a]
            flag = ' <span class="bad" title="the tool did not report token usage">tokens not reported</span>' if t['unreported'] else ''
            miss = f' <span class="muted">(no {", ".join(t["missing"])})</span>' if t['missing'] else ''
            trows.append(
                f'<tr><td>{html.escape(a)}{flag}{miss}</td><td>{html.escape(str(t["model"]))}</td>'
                f'<td>{fmt(t["total_tokens"])}{delta(t["total_tokens"], base and base["total_tokens"])}</td>'
                + ''.join(f'<td>{fmt(t[k])}</td>' for k, _, _ in CATS)
                + f'<td>{fmt(t["cost_usd"], "$")}{delta(t["cost_usd"], base and base["cost_usd"])}</td>'
                f'<td>{fmt(t["tool_calls"])}</td><td>{fmt(t["bytes_read"])}</td><td>{fmt(t["wall_s"], "s")}</td>'
                f'<td>{t["ok"]}/{t["n"]}</td><td>{fmt(t["interventions"])}</td></tr>')
    totals_table = ('<table><thead><tr><th>Arm</th><th>Model</th><th>Total tokens</th>'
                    + ''.join(f'<th>{n}</th>' for _, n, _ in CATS)
                    + '<th>Cost (list)</th><th>Tool calls</th><th>Bytes read</th><th>Wall</th><th>Passed</th><th>Interventions</th></tr></thead><tbody>'
                    + ''.join(trows) + '</tbody></table>')

    # Arm x scenario table.
    head = '<tr><th>Arm</th>' + ''.join(f'<th>{s}<br><span class="muted">{html.escape(titles.get(s, ""))}</span></th>' for s in scns) + '</tr>'
    body = []
    for a in arms:
        tds = []
        for s in scns:
            c = cells.get((a, s))
            if not c:
                tds.append('<td class="muted">-</td>')
                continue
            ok = 'good' if c['ok'] == c['n'] else 'bad'
            tds.append(f'<td>{fmt(c["total_tokens"])} <span class="muted">[{fmt(c["min"])}-{fmt(c["max"])}]</span><br>'
                       f'{fmt(c["cost_usd"], "$")} · {fmt(c["tool_calls"])} calls · <span class="{ok}">{c["ok"]}/{c["n"]}</span></td>')
        body.append(f'<tr><td>{html.escape(a)}</td>{"".join(tds)}</tr>')
    matrix = f'<table class="matrix"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table>'

    ctx = ''
    for r in extra.get('context-replay.json', []):
        rws = ''.join(f'<tr><td>{html.escape(t["tool"])}</td>'
                      + ''.join(f'<td>{html.escape(k)}: {fmt(v["est_tokens"])}</td>' for k, v in t['steps'].items())
                      + f'<td><b>{fmt(t["est_tokens"])}</b> ({fmt(t["bytes"])} B)</td></tr>' for t in r['tools'])
        ix = r.get('index') or {}
        ixline = (f'<p>FriedLiver index on this repo: {ix.get("files_indexed", 0):,} files, full build {ix.get("build_ms", 0):,} ms, '
                  f're-open {ix.get("reopen_ms", 0):,} ms, saved index {fmt(ix.get("saved_bytes"))} B'
                  f'{", Merkle root " + str(ix["merkle_root"])[:12] if ix.get("merkle_root") else ""}. '
                  'Claude Code, Codex and Gemini CLI keep no index (0 B, search on demand). Cursor indexes in its cloud; not observable headlessly.</p>') if ix else ''
        ctx += (f'<h3>{r["scenario"]}: <code>{html.escape(r["symbol"])}</code> '
                f'<span class="muted">({r["definition_hits"]} definition hits, {r["caller_hits"]} caller lines)</span></h3>'
                f'{ixline}<table><thead><tr><th>Tool</th><th>Step 1</th><th>Step 2</th><th>Step 3</th><th>Context (est. tokens)</th></tr></thead><tbody>{rws}</tbody></table>')
    if ctx:
        ctx = ('<h2>IDE-side: S3 context cost without an LLM</h2><p class="muted">One fixed trace (find definition, find callers, read the file) '
               'through each tool\'s output format and caps. Tokens = bytes/4. FriedLiver\'s row is its real index code; the others are emulations (context_replay.py).</p>' + ctx)

    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Token Bench Report</title><style>
:root{{--bg:#0f1115;--panel:#171a21;--line:#2a2f3a;--text:#e6e8ee;--muted:#8b93a4;--good:#4fb39a;--bad:#e5636b;--accent:#5b8def}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
main{{width:100%;padding:24px 32px}}h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:17px;margin:28px 0 8px}}h3{{font-size:14px;margin:18px 0 6px}}
table{{width:100%;border-collapse:collapse;background:var(--panel);margin:8px 0}}th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{color:var(--muted);font-weight:600;font-size:12px}}td{{font-variant-numeric:tabular-nums}}tr.grp td{{background:#1d2230;color:var(--accent);font-weight:600}}
.muted{{color:var(--muted)}}.good{{color:var(--good)}}.bad{{color:var(--bad)}}code{{font-family:ui-monospace,Menlo,monospace}}
.banner{{background:#3a1d20;border:1px solid var(--bad);color:#ffd5d8;padding:10px 14px;margin:12px 0;font-weight:600}}.note{{color:var(--muted);margin:6px 0}}
.chart{{width:100%;height:auto;background:var(--panel)}}.lbl{{fill:var(--muted);font-size:12px}}.val{{fill:var(--text);font-size:12px}}.whisker{{stroke:var(--text);stroke-width:1.5}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:12px}}figure{{margin:0}}figcaption{{color:var(--muted);font-size:12px;margin:4px 0}}
.matrix td{{font-size:12px}}@media(max-width:700px){{main{{padding:16px}}.grid{{grid-template-columns:1fr}}table{{display:block;overflow-x:auto}}}}
</style></head><body><main>
<h1>Token efficiency: FriedLiver agents vs other coding tools</h1>
<div class="muted">config {html.escape(str(run.get("config", "?")))} · mode {", ".join(modes)} · {len(set(r["rep"] for r in rows))} repetition(s) · medians, [min-max] · list prices from prices.json</div>
{banner}
<h2>Totals per arm (sum of per-scenario medians)</h2>{totals_table}
<h2>Where the tokens go</h2>{stacked_bars(arms, totals)}
<h2>Per scenario</h2><p class="muted">Bar = median total tokens, line = min-max, red = at least one failed repetition.</p>{scenario_bars(arms, scns, cells, titles)}
<h2>Arm x scenario</h2>{matrix}
{ctx}
<h2>How to read this</h2><ul class="muted">
<li>Compare arms only inside a group: same model family, the same model where the tools allow it.</li>
<li>Total tokens = uncached input + cache write + cache read + output (reasoning included). Cache reads are cheap but still count: they are context the tool chose to resend.</li>
<li>Cost is computed from each arm's token counts at list price, so Cursor and Antigravity rows are list-price equivalents, not what their plans bill.</li>
<li>Bytes read = tool output that went back into the model's context, as each tool reports it. n/a = the tool does not expose it.</li></ul>
</main></body></html>'''


def main(d):
    out = os.path.join(d, 'report.html')
    with open(out, 'w') as f:
        f.write(render(d))
    print(out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
