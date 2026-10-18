#!/usr/bin/env python3
"""Token-efficiency benchmark: FriedLiver's agents vs Claude Code, Codex CLI, Gemini CLI, Cursor and
Antigravity on the same scenarios. Python stdlib only.

    bench.py run --config repos/public.json --out results-local/x [--arms a,b] [--reps 3] [--replay fixtures]
    bench.py import-manual --config C --arm antigravity-ide --csv sheet.csv --out DIR
    bench.py estimate --config repos/public.json [--arms ...] [--reps 3]
    bench.py context-replay --config C --repo-dir DIR --out DIR   (S3 context cost per tool, no LLM)
    report.py DIR                                                  (HTML report)

`--replay DIR` reads recorded raw outputs instead of starting any tool: no keys, no network, no cost.
"""
import argparse, contextlib, csv, datetime, json, os, re, shutil, statistics, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adapters  # noqa: E402

SCHEMA = 1

# Each arm: how it runs, the model it runs on, the price row, the key it needs, and its parity group
# (rows are compared only within a group: same model family, ideally the same model).
ARMS = {
    'claude':            {'kind': 'cli', 'tool': 'claude', 'model': 'claude-sonnet-5-5', 'price': 'claude-sonnet-5-5', 'key': 'ANTHROPIC_API_KEY', 'group': 'anthropic'},
    'friedliver-claude': {'kind': 'acp', 'argv': ['claude-agent-acp'], 'model_env': 'ANTHROPIC_MODEL', 'model': 'claude-sonnet-5-5', 'price': 'claude-sonnet-5-5', 'key': 'ANTHROPIC_API_KEY', 'group': 'anthropic'},
    'cursor':            {'kind': 'cli', 'tool': 'cursor', 'model': 'sonnet-5.5', 'price': 'claude-sonnet-5-5', 'key': 'CURSOR_API_KEY', 'group': 'anthropic'},
    'codex':             {'kind': 'cli', 'tool': 'codex', 'model': 'gpt-5.5', 'price': 'gpt-5.5', 'key': 'OPENAI_API_KEY', 'group': 'openai'},
    'friedliver-codex':  {'kind': 'acp', 'argv': ['codex-acp', '-c', 'model="{model}"'], 'model': 'gpt-5.5', 'price': 'gpt-5.5', 'key': 'OPENAI_API_KEY', 'group': 'openai'},
    'gemini':            {'kind': 'cli', 'tool': 'gemini', 'model': 'gemini-3.1-pro-preview', 'price': 'gemini-3.1-pro-preview', 'key': 'GEMINI_API_KEY', 'group': 'google'},
    'friedliver-gemini': {'kind': 'acp', 'argv': ['gemini', '--acp', '-m', '{model}'], 'model': 'gemini-3.1-pro-preview', 'price': 'gemini-3.1-pro-preview', 'key': 'GEMINI_API_KEY', 'group': 'google'},
    # agy authenticates only through a cached interactive login: local runs only.
    'antigravity':       {'kind': 'cli', 'tool': 'antigravity', 'model': 'gemini-3.1-pro', 'price': 'gemini-3.1-pro-preview', 'key': None, 'group': 'google'},
    # GUI runs, numbers come from import-manual: FriedLiver's own chat UI (index tools on) and the
    # Antigravity IDE's agent (no headless path).
    'friedliver-ui':     {'kind': 'manual', 'model': 'claude-sonnet-5-5', 'price': 'claude-sonnet-5-5', 'key': None, 'group': 'anthropic'},
    'antigravity-ide':   {'kind': 'manual', 'model': 'gemini-3.1-pro', 'price': 'gemini-3.1-pro-preview', 'key': None, 'group': 'google'},
}

# ---- Secrets: each tool sees only its own key; nothing key-shaped is written to disk ----

KEY_VARS = ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'CODEX_API_KEY', 'GEMINI_API_KEY', 'CURSOR_API_KEY')
EXTRA_KEYS = {'OPENAI_API_KEY': ('CODEX_API_KEY',)}  # codex exec reads CODEX_API_KEY
BASE_ENV = ('PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'USER', 'SHELL', 'TERM')
KEY_PATTERNS = re.compile(r'sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|key_[0-9a-f]{32,}')


def arm_env(arm):
    """The whole environment for one arm's processes: an allowlist plus that tool's own key(s).
    arm=None (setup commands, success checks) gets no key at all."""
    env = {k: os.environ[k] for k in BASE_ENV if k in os.environ}
    key = ARMS[arm]['key'] if arm else None
    for k in (key, *EXTRA_KEYS.get(key, ())) if key else ():
        if os.environ.get(k):
            env[k] = os.environ[k]
    if key == 'OPENAI_API_KEY' and 'OPENAI_API_KEY' in env:
        env.setdefault('CODEX_API_KEY', env['OPENAI_API_KEY'])
    return env


def redact(text):
    """Removes the exact values of the key variables, then anything shaped like an API key."""
    for k in KEY_VARS:
        v = os.environ.get(k)
        if v and len(v) >= 8:
            text = text.replace(v, '[REDACTED]')
    return KEY_PATTERNS.sub('[REDACTED]', text)


def runnable(scenarios):
    """In CI, scenarios that need the network (web lookup) are left out: agents there get no web tools."""
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        skipped = [s['id'] for s in scenarios if s.get('network')]
        if skipped:
            print(f'CI: skipping network scenarios {skipped} (run them locally)')
        return [s for s in scenarios if not s.get('network')]
    return scenarios


with open(os.path.join(HERE, 'prices.json')) as f:
    PRICES = json.load(f)


# ---- Config and the public/private guard ----

def load_config(path):
    with open(path) as f:
        cfg = json.load(f)
    ids = [s['id'] for s in cfg['scenarios']]
    for s in cfg['scenarios']:
        if s['repo'] not in cfg['repos']:
            raise ValueError(f"{s['id']}: unknown repo {s['repo']}")
        if s.get('after') and ids.index(s['after']) > ids.index(s['id']):
            raise ValueError(f"{s['id']}: comes after {s['after']}, so list it later")
    return cfg


def bench_repo_root():
    r = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=HERE, capture_output=True, text=True)
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 else os.path.realpath(HERE)


def guard_private(cfg, out_dir):
    """A private repo's prompts, symbols and outputs must never reach the public repo or public CI."""
    if not cfg.get('private'):
        return
    if os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI'):
        sys.exit('refusing: a private config does not run in CI. Run it on your own machine.')
    out, root = os.path.realpath(out_dir), bench_repo_root()
    if out == root or out.startswith(root + os.sep):
        sys.exit(f'refusing: results of a private config must live outside {root} (got {out}).')


def chains(scenarios, only=None):
    """Scenarios grouped into sessions: a scenario with `after` continues its predecessor's session."""
    out, by_id = [], {}
    for s in scenarios:
        if only and s['id'] not in only:
            continue
        if s.get('after') in by_id:  # predecessor left out: this one starts its own session
            by_id[s['after']].append(s)
            by_id[s['id']] = by_id[s['after']]
        else:
            chain = [s]
            out.append(chain)
            by_id[s['id']] = chain
    return out


# ---- Repos ----

def sh(cmd, cwd, timeout=1800):
    """Setup commands and success checks run repo code: no keys in their environment."""
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout, env=arm_env(None))


def prepare_repo(name, spec, work):
    """A checkout at the pinned commit, set up once. A public repo is fetched; a private one becomes a
    detached git worktree of your local clone, so your own working tree is never touched."""
    path = os.path.join(work, name)
    if not os.path.isdir(os.path.join(path, '.git')) and not os.path.isfile(os.path.join(path, '.git')):
        if spec.get('local_path'):
            src = os.path.expanduser(spec['local_path'])
            r = sh(['git', '-C', src, 'worktree', 'add', '--detach', path, spec['ref']], cwd=work)
        else:
            os.makedirs(path, exist_ok=True)
            r = sh(f"git init -q && git remote add origin {spec['url']} && git fetch -q --depth 1 origin {spec['sha']} && git checkout -q FETCH_HEAD", cwd=path)
        if r.returncode:
            raise RuntimeError(f'{name}: checkout failed: {r.stderr[-2000:]}')
        for cmd in spec.get('setup', []):
            r = sh(cmd, cwd=path, timeout=3600)
            if r.returncode:
                raise RuntimeError(f'{name}: setup `{cmd}` failed: {r.stderr[-2000:]}')
    return path


@contextlib.contextmanager
def throwaway(base):
    """A disposable checkout of `base`'s pinned commit for one chain: a detached git worktree in a temp
    dir, with base's installed node_modules linked in. The agent never touches the prepared checkout."""
    tmp = tempfile.mkdtemp(prefix='token-bench-')
    path = os.path.join(tmp, os.path.basename(base.rstrip(os.sep)))
    r = sh(['git', '-C', base, 'worktree', 'add', '-q', '--detach', path, 'HEAD'], cwd=base)
    if r.returncode:
        raise RuntimeError(f'worktree failed: {r.stderr}')
    if os.path.isdir(os.path.join(base, 'node_modules')):
        os.symlink(os.path.join(base, 'node_modules'), os.path.join(path, 'node_modules'))
    try:
        yield path
    finally:
        sh(['git', '-C', base, 'worktree', 'remove', '--force', path], cwd=base)
        shutil.rmtree(tmp, ignore_errors=True)


def reset_repo(path, spec):
    sh(['git', 'reset', '-q', '--hard', spec.get('sha') or spec['ref']], cwd=path)
    sh(['git', 'clean', '-fdq', '-e', 'node_modules'], cwd=path)


# ---- Success checks ----

def check(scn, answer, repo_dir):
    """(ok, detail). Read-only scenarios check the answer; edit scenarios check files and run tests,
    with an optional hidden spec copied in only while the check runs."""
    c = scn.get('check') or {}
    missing = [p for p in c.get('answer_all', []) if not re.search(p, answer or '', re.I)]
    if missing:
        return False, f'answer lacks {missing}'
    if repo_dir is None:
        return True, 'answer ok (no repo: replay)'
    if c.get('changed'):
        changed = sh(['git', 'status', '--porcelain'], cwd=repo_dir).stdout
        absent = [p for p in c['changed'] if p not in changed]
        if absent:
            return False, f'not changed: {absent}'
    if c.get('cmd'):
        dest = None
        if c.get('inject'):
            dest = os.path.join(repo_dir, c['inject']['dest'])
            shutil.copyfile(os.path.join(HERE, c['inject']['src']), dest)
        try:
            r = sh(c['cmd'], cwd=repo_dir, timeout=900)
        finally:
            if dest and os.path.exists(dest):
                os.remove(dest)
        if r.returncode:
            return False, f"check failed: {(r.stdout + r.stderr)[-500:]}"
    return True, 'ok'


# ---- One turn ----

def model_of(arm, overrides):
    return overrides.get(arm, ARMS[arm]['model'])


def acp_argv(arm, model):
    return [a.replace('{model}', model) for a in ARMS[arm]['argv']]


def run_cli_turn(arm, prompt, model, session_id, cwd, extra, budget, network=False):
    tool = ARMS[arm]['tool']
    extra = list(extra)
    if tool == 'claude' and budget:
        extra += ['--max-budget-usd', str(budget)]
    argv = adapters.command(tool, prompt, model, session_id, extra, network)
    t = time.monotonic()
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=1800, env=arm_env(arm))
    return redact(p.stdout), time.monotonic() - t, p.returncode


def record(arm, scn, rep, mode, parsed, wall, ok, detail, model, cfg, raw_file=None):
    price = PRICES.get(ARMS[arm]['price']) if arm in ARMS else None
    tok = parsed['tokens']
    return {
        'schema': SCHEMA, 'config': cfg['name'], 'arm': arm, 'group': ARMS.get(arm, {}).get('group'),
        'model': model, 'scenario': scn['id'], 'title': scn.get('title', ''), 'rep': rep, 'mode': mode,
        'tokens': tok, 'total_tokens': sum(tok[k] for k in ('input', 'cache_read', 'cache_write', 'output')),
        'usage_reported': parsed.get('usage_reported', True),
        'cost_usd': adapters.cost_usd(tok, price), 'reported_cost_usd': parsed.get('reported_cost_usd'),
        'tool_calls': parsed.get('tool_calls'), 'bytes_read': parsed.get('bytes_read'),
        'files_read': None if parsed.get('files_read') is None else len(parsed['files_read']),
        'wall_s': round(wall, 2) if wall is not None else None, 'success': ok, 'success_detail': redact(detail or ''),
        'interventions': parsed.get('interventions', 0), 'raw': raw_file,
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
    }


def parse(arm, raw, prev_usage=None):
    if ARMS[arm]['kind'] == 'acp':
        import acp
        return acp.parse_acp(raw, prev_usage)
    return adapters.PARSERS[ARMS[arm]['tool']](raw)


# ---- Run ----

def run(cfg, arms, reps, out, replay=None, only=None, overrides=None, extra=None, budget=None, work=None):
    overrides, extra = overrides or {}, extra or {}
    os.makedirs(os.path.join(out, 'raw'), exist_ok=True)
    results = os.path.join(out, 'results.jsonl')
    meta = {}
    if replay:
        with open(os.path.join(replay, 'meta.json')) as f:
            meta = json.load(f)
    repos = {}
    if not replay:
        work = work or os.path.join(out, 'work')
        os.makedirs(work, exist_ok=True)
        needed = {s['repo'] for c in chains(runnable(cfg['scenarios']), only) for s in c}
        repos = {n: prepare_repo(n, spec, work) for n, spec in cfg['repos'].items() if n in needed}
    with open(results, 'a') as res:
        for rep in range(1, reps + 1):
            order = arms[(rep - 1) % len(arms):] + arms[:(rep - 1) % len(arms)]  # round-robin start
            for chain in chains(cfg['scenarios'] if replay else runnable(cfg['scenarios']), only):
                for arm in order:
                    for rec in run_chain(cfg, arm, chain, rep, out, repos, replay, meta, model_of(arm, overrides), extra.get(arm, []), budget):
                        res.write(json.dumps(rec) + '\n')
                        res.flush()
                        print(f"{rec['arm']:18} {rec['scenario']} rep{rep} tokens={rec['total_tokens']:>9,} "
                              f"cost=${rec['cost_usd'] or 0:.4f} ok={rec['success']}", flush=True)
    return results


def run_chain(cfg, arm, chain, rep, out, repos, replay, meta, model, extra, budget):
    if replay:
        yield from _chain(cfg, arm, chain, rep, out, None, replay, meta, model, extra, budget)
        return
    with throwaway(repos[chain[0]['repo']]) as repo_dir:
        yield from _chain(cfg, arm, chain, rep, out, repo_dir, replay, meta, model, extra, budget)


def _chain(cfg, arm, chain, rep, out, repo_dir, replay, meta, model, extra, budget):
    spec = ARMS[arm]
    agent, session_id, prev_usage = None, None, None
    ci = bool(os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'))
    try:
        for scn in chain:
            raw_name = f"raw/{arm}.{scn['id']}.rep{rep}.jsonl"
            if replay:
                with open(os.path.join(replay, arm, f"{scn['id']}.jsonl")) as f:
                    raw = f.read()
                m = meta.get(arm, {}).get(scn['id'], {})
                wall, code = m.get('wall_s'), 0
            elif spec['kind'] == 'acp':
                import acp
                if agent is None:
                    env = arm_env(arm)
                    if spec.get('model_env'):
                        env[spec['model_env']] = model
                    # Vanilla like the CLI arms (claude --bare, codex --ignore-user-config): a fresh config
                    # dir, so the user's own plugins, hooks, MCP servers and memory stay out of the count.
                    fresh = os.path.join(out, 'agent-config', arm)
                    os.makedirs(fresh, exist_ok=True)
                    env.update({'claude': {'CLAUDE_CONFIG_DIR': fresh}, 'codex': {'CODEX_HOME': fresh}}.get(arm.split('-')[-1], {}))
                    mcp = json.loads(os.environ['FRIEDLIVER_INDEX_MCP']) if os.environ.get('FRIEDLIVER_INDEX_MCP') else []
                    agent = acp.AcpAgent(acp_argv(arm, model), repo_dir, env, mcp, os.environ.get('FRIEDLIVER_SYSTEM_APPEND'),
                                         deny_kinds=frozenset({'fetch'}) if ci or not scn.get('network') else frozenset())
                raw, wall = agent.prompt(scn['prompt'])
                raw, code = redact(raw), 0
            else:
                raw, wall, code = run_cli_turn(arm, scn['prompt'], model, session_id, repo_dir, extra, budget,
                                               network=bool(scn.get('network')) and not ci)
            with open(os.path.join(out, raw_name), 'w') as f:
                f.write(raw)
            parsed = parse(arm, raw, prev_usage)
            session_id = parsed.get('session_id') or session_id
            prev_usage = parsed.get('cumulative_usage') or prev_usage
            if replay:
                ok, detail = m.get('success', False), m.get('detail', 'replayed')
                ok = ok and check({'check': {'answer_all': (scn.get('check') or {}).get('answer_all', [])}}, parsed['answer'], None)[0]
            elif code:
                ok, detail = False, f'exit {code}'
            else:
                ok, detail = check(scn, parsed['answer'], repo_dir)
            yield record(arm, scn, rep, 'replay' if replay else 'live', parsed, wall, ok, detail, model, cfg, raw_name)
    finally:
        if agent:
            agent.close()


# ---- Manual runs (Antigravity IDE, or any GUI agent) ----

MANUAL_COLUMNS = ['scenario', 'rep', 'input', 'cache_read', 'cache_write', 'output', 'tool_calls', 'wall_s', 'success', 'interventions', 'notes']


def import_manual(cfg, arm, csv_path, out):
    scns = {s['id']: s for s in cfg['scenarios']}
    os.makedirs(out, exist_ok=True)
    n = 0
    with open(csv_path, newline='') as f, open(os.path.join(out, 'results.jsonl'), 'a') as res:
        for row in csv.DictReader(f):
            tok = adapters._tokens(**{k: row.get(k) or 0 for k in adapters.TOKEN_KEYS})
            parsed = {'tokens': tok, 'tool_calls': int(row['tool_calls']) if row.get('tool_calls') else None,
                      'bytes_read': None, 'files_read': None, 'interventions': int(row.get('interventions') or 0),
                      'usage_reported': any(tok.values())}
            ok = str(row.get('success', '')).strip().lower() in ('1', 'true', 'yes', 'y')
            rec = record(arm, scns[row['scenario']], int(row['rep']), 'manual', parsed,
                         float(row['wall_s']) if row.get('wall_s') else None, ok, row.get('notes', ''), ARMS[arm]['model'], cfg)
            res.write(json.dumps(rec) + '\n')
            n += 1
    return n


# ---- Cost estimate (before spending anything) ----

def estimate(cfg, arms, reps, cached=0.85, cache_write=0.08):
    """List-price estimate per arm for `reps` runs of every scenario, from each scenario's `estimate`
    {input (incl. cached), output (incl. reasoning)}. Anthropic splits input into uncached / 5-min
    cache write / cache read; the others into uncached / cached. Low/high = x0.5 / x2."""
    rows = []
    for arm in arms:
        a = ARMS[arm]
        p = PRICES[a['price']]
        total = 0.0
        for s in cfg['scenarios']:
            e = s.get('estimate') or {}
            inp, out = e.get('input', 0), e.get('output', 0)
            cw = cache_write if a['group'] == 'anthropic' else 0
            tok = adapters._tokens(input=inp * (1 - cached - cw), cache_read=inp * cached, cache_write=inp * cw, output=out)
            total += adapters.cost_usd(tok, p)
        rows.append({'arm': arm, 'model': a['model'], 'per_rep': round(total, 2), 'total': round(total * reps, 2),
                     'low': round(total * reps * 0.5, 2), 'high': round(total * reps * 2, 2),
                     'billed_to': {'cursor': 'Cursor plan (CURSOR_API_KEY)', 'antigravity': 'Google AI plan quota',
                                   'antigravity-ide': 'Google AI plan quota',
                                   'friedliver-ui': 'the Claude login FriedLiver uses'}.get(arm, a['key'])})
    return rows


# ---- CLI ----

def kv(pairs):
    out = {}
    for p in pairs or []:
        k, _, v = p.partition('=')
        out[k] = v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--config', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--arms', default='claude,friedliver-claude,codex,friedliver-codex,gemini,friedliver-gemini,cursor')
    r.add_argument('--reps', type=int, default=3)
    r.add_argument('--scenarios', default='', help='comma-separated ids; default all')
    r.add_argument('--replay', help='directory of recorded raw outputs (no tools run)')
    r.add_argument('--model', action='append', help='arm=model override')
    r.add_argument('--budget-usd', type=float, default=3.0, help='per-turn cap where the tool supports one (claude)')
    r.add_argument('--work', help='where checkouts go (default OUT/work)')
    r.add_argument('--skip-missing-keys', action='store_true', help='drop arms whose key env var is unset')
    m = sub.add_parser('import-manual')
    m.add_argument('--config', required=True)
    m.add_argument('--arm', default='antigravity-ide')
    m.add_argument('--csv', required=True)
    m.add_argument('--out', required=True)
    e = sub.add_parser('estimate')
    e.add_argument('--config', required=True)
    e.add_argument('--arms', default=','.join(ARMS))
    e.add_argument('--reps', type=int, default=3)
    c = sub.add_parser('context-replay')
    c.add_argument('--config', required=True)
    c.add_argument('--repo-dir', required=True)
    c.add_argument('--out', required=True)
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    if a.cmd == 'estimate':
        rows = estimate(cfg, [x for x in a.arms.split(',') if x], a.reps)
        print(f"{'arm':18} {'model':24} {'per rep':>8} {'x' + str(a.reps):>8}  range          billed to")
        for x in rows:
            print(f"{x['arm']:18} {x['model']:24} ${x['per_rep']:>7.2f} ${x['total']:>7.2f}  ${x['low']:.2f}-${x['high']:.2f}  {x['billed_to']}")
        print(f"{'all arms':43} ${sum(x['total'] for x in rows):>7.2f}")
        return
    guard_private(cfg, a.out)
    if a.cmd == 'import-manual':
        print(f'imported {import_manual(cfg, a.arm, a.csv, a.out)} rows')
        return
    if a.cmd == 'context-replay':
        import context_replay
        print(json.dumps(context_replay.run(cfg, a.repo_dir, a.out), indent=1))
        return
    only = set(a.scenarios.split(',')) - {''} or None
    unknown = (only or set()) - {s['id'] for s in cfg['scenarios']}
    if unknown:
        sys.exit(f'unknown scenarios: {sorted(unknown)}')
    arms = [x for x in a.arms.split(',') if x]
    bad = [x for x in arms if x not in ARMS or ARMS[x]['kind'] == 'manual']
    if bad:
        sys.exit(f'unknown or manual-only arms: {bad} (manual arms come in through import-manual)')
    if a.skip_missing_keys and not a.replay:
        arms = [x for x in arms if not ARMS[x]['key'] or os.environ.get(ARMS[x]['key'])]
        if not arms:
            print('no arm has its key set: nothing to run')
            return
    if not a.replay:
        exe = lambda x: ARMS[x]['argv'][0] if ARMS[x]['kind'] == 'acp' else adapters.command(ARMS[x]['tool'], '', '')[0]
        gone = [x for x in arms if not shutil.which(exe(x))]
        for x in gone:
            print(f'skipping {x}: `{exe(x)}` is not installed')
        arms = [x for x in arms if x not in gone]
        if not arms:
            return
    with open(os.path.join(os.makedirs(a.out, exist_ok=True) or a.out, 'run.json'), 'w') as f:
        json.dump({'config': cfg['name'], 'private': bool(cfg.get('private')), 'arms': arms, 'reps': a.reps,
                   'mode': 'replay' if a.replay else 'live', 'replay_source': a.replay,
                   'started': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}, f, indent=1)
    run(cfg, arms, a.reps, a.out, a.replay, only, kv(a.model), None, a.budget_usd, a.work)


if __name__ == '__main__':
    main()
