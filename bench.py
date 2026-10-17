#!/usr/bin/env python3
"""Phase-1 desktop editor benchmark (objective, no AI, no accounts).

Safety model (the owner's 8 GB laptop has crashed under load before):
  * exactly one app under test at a time; each run waits until every process of the previous
    run is gone, then sleeps 10 s;
  * every launch gets a throwaway HOME / --user-data-dir / --extensions-dir under PROF, and every
    process we measure or kill is found by that tmp path appearing in its argv or env (ps -E),
    plus its descendants. Nothing without the tag is ever signalled, so the owner's running
    FriedLiver instance is untouchable;
  * a run is aborted (app killed) if free memory drops below 2 GB.

Usage: bench.py preflight | run [--only id,id] | postflight | cleanup
Selection (env, set by the workflow): BENCH_ONLY apps, BENCH_VARIANTS arms like friedliver+settings-perf,
BENCH_SCENARIOS slow-shell,large-repo. The patched FriedLiver build runs whenever fetch_apps.py fetched it.
"""
import glob, json, os, re, signal, stat, subprocess, sys, tempfile, time, datetime, shutil, statistics

import stats

SCRATCH = os.environ.get('BENCH_SCRATCH',
    '/private/tmp/claude-501/-Users-arunmallikarjun-HRMS/607dfe49-a562-4c39-8755-d4057bf35d87/scratchpad/bench')
REPO = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(REPO, 'results')
FIX = os.path.join(SCRATCH, 'fixture')
BIG = os.path.join(FIX, 'big-5mb.txt')
BIGREPO = os.path.join(SCRATCH, 'bigrepo')        # large-repo scenario: pinned shallow microsoft/TypeScript
LOGS = os.path.join(RES, 'logs')
SAMPLES = 3                                       # idle / files20 / scenario repeats per arm
# Profile root: VS Code derives its main IPC socket path from --user-data-dir and unix socket paths
# are capped at 103 chars, so SCRATCH is too long. The root is a fresh mkdtemp dir in /private/tmp
# (atomic, unpredictable name, mode 0700) - never a fixed name another user could pre-create.
# Every root ever created is listed in PROF_LIST so `cleanup` (a separate process) can find it.
PROF = None
PROF_PARENT = '/private/tmp'
PROF_LIST = os.path.join(SCRATCH, 'prof-roots.txt')
ROOT_NAME = re.compile(r'^ebp-[A-Za-z0-9_]+$')
WINWAIT = os.path.join(SCRATCH, 'winwait')
RAW = os.path.join(RES, 'raw-runs.jsonl')
MIN_FREE = 2 * 1024**3
GAP_S = 10
DEAD_PROXY = '--proxy-server=http://127.0.0.1:9'   # blocks Chromium-stack network (see README)

APPS = [
    dict(id='friedliver', label='FriedLiver', path='/Applications/FriedLiver.app', vscode=True,
         bundle='com.friedliver.app'),
    dict(id='cursor', label='Cursor', path='/Applications/Cursor.app', vscode=True,
         bundle='com.todesktop.230313mzl4w4u92'),
    dict(id='antigravity-ide', label='Antigravity IDE', path='/Applications/Antigravity IDE.app', vscode=True,
         bundle='com.google.antigravity-ide'),
    dict(id='vscode', label='VS Code (stock)', path=os.path.join(SCRATCH, 'vscode', 'Visual Studio Code.app'),
         vscode=True, bundle='com.microsoft.VSCode'),
    # Not VS Code forks: Electron "agent manager" shells. Both run an electron-updater that would
    # download (Antigravity: and install-on-quit over /Applications) a newer build, so their
    # Chromium network goes to a dead proxy. Localhost (their own sidecars) is unaffected.
    dict(id='antigravity', label='Antigravity (agent app)', path='/Applications/Antigravity.app', vscode=False,
         bundle='com.google.antigravity', extra=[DEAD_PROXY]),
    # OpenCode pins its own userData path and IGNORES --user-data-dir (seen on the laptop smoke run:
    # it wrote into the real ~/Library/Application Support/ai.opencode.desktop), so it only runs
    # where that profile is throwaway: on a CI runner.
    dict(id='opencode', label='OpenCode Desktop', path='/Applications/OpenCode.app', vscode=False,
         bundle='ai.opencode.desktop', extra=[DEAD_PROXY], ci_only=True),
    # A FriedLiver build from a tag or a workflow-run artifact (workflow input friedliver_ref). Same bundle id
    # as the release is fine: processes are attributed by profile path, never by bundle id.
    dict(id='friedliver-patched', label='FriedLiver patched', path=None, vscode=True, bundle='com.friedliver.app',
         ci_only=True),
]
AB_IDS = {'vscode', 'friedliver', 'friedliver-patched'}   # arms the scenarios run on
# Settings variants: the same binary, with these merged into the throwaway profile's settings.json.
VARIANTS = {
    'settings-perf': {
        'editor.cursorBlinking': 'blink',
        'workbench.startupEditor': 'none',
        'typescript.tsserver.useSyntaxServer': 'never',
        'files.watcherExclude': {g: True for g in (
            '**/.git/objects/**', '**/.git/subtree-cache/**', '**/.hg/store/**',   # upstream defaults, kept
            '**/.venv/**', '**/__pycache__/**', '**/.next/**', '**/.turbo/**', '**/.gradle/**',
            '**/target/**', '**/dist/**', '**/build/**', '**/node_modules/**')},
        # 1.142.0: time-slices onStartupFinished activation into 50 ms budgets
        # (extensions.contribution.ts#L312, extHostExtensionService.ts#L622-L667)
        'extensions.experimental.deferredStartupFinishedActivation': True,
    },
    # single-change diagnostics (bisecting the perf/core defaults, CORE-PERF C5-C8, C10, and patches 0200/0210)
    'caret-smooth': {'editor.cursorBlinking': 'smooth'},          # FriedLiver's release default
    'welcome': {'workbench.startupEditor': 'welcomePage'},        # upstream default
    'blink': {'editor.cursorBlinking': 'blink'},                  # upstream default; perf/core drops 'smooth'
    'deferred-activation': {'extensions.experimental.deferredStartupFinishedActivation': True},
    'one-tsserver': {'typescript.tsserver.useSyntaxServer': 'never'},
    'no-welcome': {'workbench.startupEditor': 'none'},
    'watcher-excludes': {'files.watcherExclude': {g: True for g in (       # perf/core's additions (DEFAULTS.md)
        '**/node_modules/*/**', '**/.venv/**', '**/venv/**', '**/__pycache__/**', '**/.mypy_cache/**',
        '**/.pytest_cache/**', '**/.next/**', '**/.nuxt/**', '**/.turbo/**', '**/.parcel-cache/**', '**/.gradle/**')}},
    'no-fast-shell': {'friedliver.fastShellEnv': False},          # patch 0200 off
    'no-compile-cache': {'_env': {'NODE_DISABLE_COMPILE_CACHE': '1'}},   # patch 0210 off (Node honours it)
}

def make_arms(apps, only, variants):
    """Selected apps (all if `only` is empty; the patched build whenever present) + one arm per variant
    '<base>+<variant>' whose base binary was fetched."""
    by = {a['id']: a for a in apps}
    arms = [a for a in apps if not only or a['id'] in only or a['id'] == 'friedliver-patched']
    for v in variants:
        base, _, name = v.partition('+')
        if name not in VARIANTS:
            raise SystemExit(f'unknown variant {v!r}; known: {", ".join(VARIANTS)}')
        if base in by:
            settings = {k: x for k, x in VARIANTS[name].items() if k != '_env'}
            arms.append(dict(by[base], id=v, base=base, label=f"{by[base]['label']} + {name}", settings=settings,
                             env=VARIANTS[name].get('_env', {})))
    return arms
IN_CI = os.environ.get('GITHUB_ACTIONS') == 'true'
if os.path.exists(os.environ.get('BENCH_APPS', '')):  # CI: {id: path} written by fetch_apps.py; missing ids = skipped
    _paths = json.load(open(os.environ['BENCH_APPS']))
    APPS = [dict(a, path=_paths[a['id']]) for a in APPS if a['id'] in _paths]
APPS = [a for a in APPS if IN_CI or not a.get('ci_only')]
ARMS = make_arms(APPS, set(stats.split_list(os.environ.get('BENCH_ONLY', ''))),
                 stats.split_list(os.environ.get('BENCH_VARIANTS', 'none')))
SCENARIOS = stats.split_list(os.environ.get('BENCH_SCENARIOS', 'none'), ['slow-shell', 'large-repo'])
SUITE = os.environ.get('BENCH_SUITE') or 'full'      # 'idle': warm-up + idle x3 only (bisecting idle CPU)
if SUITE not in ('full', 'idle'):
    raise SystemExit(f'BENCH_SUITE must be full or idle, got {SUITE!r}')
SHELL_SLEEP = float(os.environ.get('BENCH_SHELL_SLEEP') or 1.0)   # seconds the slow .zshrc sleeps
if not 0 < SHELL_SLEEP <= 9:   # VS Code's shell-env timeout is 10 s
    raise SystemExit(f'BENCH_SHELL_SLEEP must be in (0, 9], got {SHELL_SLEEP}')
BY_ID = {a['id']: a for a in ARMS}

# ---------------------------------------------------------------- helpers

def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw).stdout

def log(*a):
    print(datetime.datetime.now().strftime('%H:%M:%S'), *a, flush=True)

def free_bytes():
    level = int(sh('sysctl', '-n', 'kern.memorystatus_level'))   # % of RAM the kernel counts as free
    return int(sh('sysctl', '-n', 'hw.memsize')) * level // 100

def power():
    out = sh('pmset', '-g', 'batt')
    src = 'AC' if "'AC Power'" in out else 'battery'
    pct = out.split('\t')[1].split(';')[0] if '\t' in out else '?'
    return f'{src} {pct}'

def tag_of(app):
    ensure_root()
    return os.path.join(PROF, app.get('prof', app['id'])) + '/'

def procs(tag, exclude=()):
    """Processes carrying `tag` in argv/env, plus all their descendants."""
    out = sh('ps', '-axwwE', '-o', 'pid=,ppid=,rss=,time=,command=')
    rows, tagged = {}, set()
    for line in out.splitlines():
        p = line.split(None, 4)
        if len(p) < 5:
            continue
        pid, ppid = int(p[0]), int(p[1])
        rows[pid] = dict(pid=pid, ppid=ppid, rss_kb=int(p[2]), cpu_s=cpu_s(p[3]), role=stats.role(p[4]),
                         exe=p[4].split(' --')[0].split(' HOME=')[0][:400])
        if tag in p[4] and pid not in exclude and pid != os.getpid():
            tagged.add(pid)
    grew = True
    while grew:
        kids = {r['pid'] for r in rows.values() if r['ppid'] in tagged} - tagged
        grew = bool(kids)
        tagged |= kids
    return [rows[p] for p in sorted(tagged)]

def cpu_s(t):                       # ps "time": [[hh:]mm:]ss.cc
    s = 0.0
    for part in t.split(':'):
        s = s * 60 + float(part)
    return s

def footprint(pids):
    if not pids:
        return None
    out = os.path.join(SCRATCH, 'fp.json')
    subprocess.run(['footprint', '-j', out, *map(str, pids)], capture_output=True)
    try:
        d = json.load(open(out))
        return int(d['total footprint']) * int(d.get('bytes per unit', 1))
    except Exception:
        return None

def snapshot(tag, exclude=()):
    ps = procs(tag, exclude)
    return dict(n_procs=len(ps), rss_mb=round(sum(p['rss_kb'] for p in ps) / 1024, 1),
                footprint_mb=(lambda f: f and round(f / 1024**2, 1))(footprint([p['pid'] for p in ps])),
                cpu_s=sum(p['cpu_s'] for p in ps), procs=[(p['pid'], p['exe'].rsplit('/', 1)[-1]) for p in ps],
                cpu=[(p['pid'], p['role'], p['cpu_s']) for p in ps])

def safe_own_dir(path):
    """True only for a real (non-symlink) directory owned by us, mode 0700, at its realpath."""
    st = os.lstat(path)
    return (stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and stat.S_IMODE(st.st_mode) == 0o700
            and os.path.realpath(path) == path)

def private_file_or_dir(path):
    """Owned by us, not a symlink, not group/other-writable."""
    st = os.lstat(path)
    return not stat.S_ISLNK(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o022

def valid_root_entry(entry):
    """A PROF_LIST line is deletable only if it is exactly PROF_PARENT/ebp-<name> and a private dir of ours."""
    return (os.path.dirname(entry) == os.path.realpath(PROF_PARENT) and bool(ROOT_NAME.match(os.path.basename(entry)))
            and os.path.lexists(entry) and safe_own_dir(entry))

def cleanup():
    if not os.path.lexists(PROF_LIST):
        return
    if not (private_file_or_dir(SCRATCH) and private_file_or_dir(PROF_LIST)):
        raise SystemExit(f'ABORT: {SCRATCH} or {PROF_LIST} is not private to us; not trusting it')
    for entry in open(PROF_LIST).read().split():
        if valid_root_entry(entry):
            shutil.rmtree(entry)
        else:
            log('cleanup: skipped untrusted entry', repr(entry))
    os.remove(PROF_LIST)

def ensure_root():
    global PROF
    if PROF:
        return
    os.makedirs(SCRATCH, exist_ok=True)
    root = tempfile.mkdtemp(prefix='ebp-', dir=PROF_PARENT)
    if not safe_own_dir(root):
        raise SystemExit(f'ABORT: profile root {root} is not a private dir owned by us')
    with open(PROF_LIST, 'a') as f:
        f.write(root + '\n')
    PROF = root

def ensure_profile(app):
    ensure_root()
    base = tag_of(app)
    home, udd, ext = (os.path.join(base, d) for d in ('home', 'udd', 'ext'))
    for d in (home, udd, ext, os.path.join(base, 'runs')):
        os.makedirs(d, exist_ok=True)
    if app['vscode']:
        os.makedirs(os.path.join(udd, 'User'), exist_ok=True)
        st = os.path.join(udd, 'User', 'settings.json')
        if not os.path.exists(st):
            # Only change from defaults: never self-update during (or because of) the benchmark.
            # Variant arms add their settings on top.
            json.dump({'update.mode': 'none', **app.get('settings', {})}, open(st, 'w'), indent=1)
        if app.get('probe'):
            install_probe(ext, os.path.join(home, 'probe.json'))
    return home, udd, ext

PROBE_ID = 'bench.probe-0.0.1'

def install_probe(ext, out):
    """A 10-line extension, activated on '*', that records when it activated and when the first file-search
    result arrived (workspace.findFiles runs through the same extension-host file search as Quick Open).
    Registered through extensions.json, the way an installed extension is."""
    d = os.path.join(ext, PROBE_ID)
    if os.path.exists(d):
        return
    os.makedirs(d)
    json.dump(dict(name='probe', publisher='bench', version='0.0.1', engines=dict(vscode='^1.80.0'),
                   activationEvents=['*'], main='./extension.js'), open(os.path.join(d, 'package.json'), 'w'))
    open(os.path.join(d, 'extension.js'), 'w').write(f"""const vscode = require('vscode'), fs = require('fs');
exports.activate = () => {{
  const t = {{ activated: Date.now() }};
  const done = () => fs.writeFileSync({json.dumps(out)}, JSON.stringify(t));
  vscode.workspace.findFiles('**/*.ts', undefined, 1).then(r => {{ t.found = Date.now(); t.n = r.length; done(); }},
    e => {{ t.error = String(e); done(); }});
}};
""")
    json.dump([dict(identifier=dict(id='bench.probe'), version='0.0.1', relativeLocation=PROBE_ID,
                    location={'$mid': 1, 'scheme': 'file', 'path': d})],
              open(os.path.join(ext, 'extensions.json'), 'w'))

def launch(app, args, run_dir):
    home, udd, ext = ensure_profile(app)
    env = dict(HOME=home, XDG_CONFIG_HOME=f'{home}/.config', XDG_DATA_HOME=f'{home}/.local/share',
               XDG_STATE_HOME=f'{home}/.local/state', XDG_CACHE_HOME=f'{home}/.cache', **app.get('env', {}))
    flags = [f'--user-data-dir={udd}', '--use-mock-keychain', '--password-store=basic', *app.get('extra', [])]
    if app['vscode']:
        flags += [f'--extensions-dir={ext}', '--disable-workspace-trust']
    # `open` forwards the caller's environment. This harness runs inside an editor's extension host
    # (ELECTRON_RUN_AS_NODE, VSCODE_IPC_HOOK of the owner's instance, agent tokens...), so launch from
    # an empty environment with only the basics, identical for every app.
    base = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', USER=os.environ.get('USER', ''), LOGNAME=os.environ.get('USER', ''),
                SHELL='/bin/zsh', LANG='en_US.UTF-8', TMPDIR=sh('getconf', 'DARWIN_USER_TEMP_DIR').strip(), HOME=home)
    cmd = ['env', '-i', *(f'{k}={v}' for k, v in base.items()), 'open', '-n', '-g', '-a', app['path']]
    for k, v in env.items():
        cmd += ['--env', f'{k}={v}']
    cmd += ['--stdout', f'{run_dir}/stdout.log', '--stderr', f'{run_dir}/stderr.log', '--args', *flags, *args]
    subprocess.run(cmd, check=True)

def wait_window(ww, timeout):
    try:
        out, _ = ww.communicate(timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        ww.kill(); return None
    p = out.split()
    return float(p[0]) if len(p) == 3 else None

def quit_app(app, grace=20):
    """SIGTERM the tagged main process, then SIGKILL anything tagged that is left."""
    tag = tag_of(app)
    ps = procs(tag)
    exe = os.path.join(app['path'], 'Contents', 'MacOS')
    for p in ps:
        if p['exe'].startswith(exe) and p['ppid'] == 1:
            os.kill(p['pid'], signal.SIGTERM)
    t = time.time()
    while procs(tag) and time.time() - t < grace:
        time.sleep(0.5)
    left = procs(tag)
    for p in left:
        try:
            os.kill(p['pid'], signal.SIGKILL)
        except ProcessLookupError:
            pass
    t = time.time()
    while procs(tag) and time.time() - t < 10:
        time.sleep(0.5)
    if procs(tag):
        raise SystemExit(f'ABORT: could not stop {app["id"]} processes: {procs(tag)}')
    return len(left)

def guarded_sleep(app, seconds):
    """Sleep, checking free memory every 2 s. Returns False (and kills the app) on low memory."""
    end = time.time() + seconds
    while time.time() < end:
        if free_bytes() < MIN_FREE:
            log(f'LOW MEMORY ({free_bytes() / 1024**3:.2f} GB free) - aborting run')
            quit_app(app, grace=3)
            return False
        time.sleep(min(2, max(0, end - time.time())))
    return True

def pre_run_gate(app):
    if procs(tag_of(app)):
        quit_app(app)
    for _ in range(30):
        if free_bytes() >= MIN_FREE:
            return True
        time.sleep(2)
    return False

def record(rec):
    rec.update(ts=datetime.datetime.now().isoformat(timespec='seconds'), power=power(),
               free_gb_before=rec.get('free_gb_before'))
    with open(RAW, 'a') as f:
        f.write(json.dumps(rec) + '\n')
    log(rec['app'], rec['kind'], {k: v for k, v in rec.items()
                                  if k in ('window_ms', 'workbench_ms', 'ellapsed_ms', 'restore_ms', 'rss_mb',
                                           'footprint_mb', 'n_procs', 'cpu_pct', 'error')})

def run_dir(app, kind, i):
    ensure_profile(app)
    d = os.path.join(tag_of(app), 'runs', f'{kind}-{i}-{int(time.time())}')
    os.makedirs(d)
    return d

def twenty_files():
    files = sorted(sh('git', '-C', FIX, 'ls-files', '*.ts').split())
    return [os.path.join(FIX, files[i * len(files) // 20]) for i in range(20)]

# ---------------------------------------------------------------- run kinds

def cold(app, kind='cold', i=0):
    """Launch -> first window (all apps) and -> workbench ready (VS Code family, via the
    product's own --prof-append-timers machinery, which also makes the app exit by itself)."""
    if not pre_run_gate(app):
        return record(dict(app=app['id'], kind=kind, i=i, error='free memory < 2 GB, skipped'))
    rd = run_dir(app, kind, i)
    rec = dict(app=app['id'], kind=kind, i=i, free_gb_before=round(free_bytes() / 1024**3, 2))
    home = ensure_profile(app)[0]
    if kind.startswith('shell'):              # slow-shell scenario: a login shell that takes SHELL_SLEEP s (nvm/oh-my-zsh)
        zshrc = os.path.join(home, '.zshrc')
        if kind == 'shell-slow':
            open(zshrc, 'w').write(f'sleep {SHELL_SLEEP}\n')
        elif os.path.exists(zshrc):
            os.remove(zshrc)
        if os.path.exists(os.path.join(home, 'probe.json')):
            os.remove(os.path.join(home, 'probe.json'))
    args = []
    if app['vscode']:
        args = [f'--prof-append-timers={rd}/timers.txt',
                '--prof-duration-markers=code/willRestoreEditors-code/didRestoreEditors',
                '--prof-duration-markers=ellapsed', *stats.marker_args(),
                f'--prof-duration-markers-file={rd}/markers.txt', FIX]
        if kind == 'big5mb':
            args += ['--goto', f'{BIG}:1']
    ww = subprocess.Popen([WINWAIT, tag_of(app), '120'], stdout=subprocess.PIPE, text=True)
    time.sleep(0.2)
    t0 = time.time()
    launch(app, args, rd)
    win = wait_window(ww, 120)
    rec['window_ms'] = win and round((win - t0) * 1000)
    if app['vscode']:
        mk = f'{rd}/markers.txt'
        end = time.time() + 120
        while time.time() < end and not os.path.exists(mk):
            if free_bytes() < MIN_FREE:
                rec['error'] = 'low memory'
                break
            time.sleep(0.25)
        if os.path.exists(mk):
            time.sleep(0.5)
            m = stats.parse_markers(open(mk).read())
            rec['marks'] = stats.offsets(m)
            rec['workbench_ms'] = rec['marks'].get('code/didStartWorkbench')
            rec['exthost_ms'] = rec['marks'].get('code/extHost/ready')
            rec['restore_ms'] = m.get('code/willRestoreEditors-code/didRestoreEditors')
            rec['ellapsed_ms'] = m.get('ellapsed')
            if os.path.exists(f'{rd}/timers.txt'):
                rec['timers_line'] = open(f'{rd}/timers.txt').read().strip().split('\n')[-1][:400]
        else:
            rec.setdefault('error', 'no startup markers within 120 s')
        # app exits on its own after writing timers; give it time, then clean up stragglers
        t = time.time()
        while procs(tag_of(app)) and time.time() - t < 30:
            time.sleep(0.5)
        collect_logs(app, kind, i, rec)
        probe = os.path.join(home, 'probe.json')
        if app.get('probe') and os.path.exists(probe):
            p = json.load(open(probe))
            rec['probe_activated_ms'] = round(p['activated'] - t0 * 1000)
            rec['search_ms'] = p.get('found') and round(p['found'] - t0 * 1000)
            rec['search_error'] = p.get('error')
    else:
        guarded_sleep(app, 5)
    rec['killed_stragglers'] = quit_app(app)
    record(rec)
    time.sleep(GAP_S)

def collect_logs(app, kind, i, rec):
    """Keep this run's renderer.log (in results/logs/) and pull out the slow workbench contributions
    and the Node compile-cache status line from main.log."""
    runs = sorted(glob.glob(os.path.join(tag_of(app), 'udd', 'logs', '*')))
    if not runs:
        return
    renderer = sorted(glob.glob(os.path.join(runs[-1], '**', 'renderer.log'), recursive=True))
    if renderer:
        text = open(renderer[0], errors='replace').read()
        rec['slow_contribs'] = stats.slow_contribs(text)
        os.makedirs(LOGS, exist_ok=True)
        shutil.copy(renderer[0], os.path.join(LOGS, f"{app['id']}-{kind}-{i}-renderer.log"))
    cc = []                                   # one status line per process (main, shared, pty host, ext host)
    for f in sorted(glob.glob(os.path.join(runs[-1], '**', '*.log'), recursive=True)):
        cc += [l[:400] for l in stats.cache_lines(open(f, errors='replace').read())]
    if cc:
        rec['compile_cache'] = cc
    rec['node_cache'] = node_cache(app)

def node_cache(app):
    """Files and KB in <udd>/CachedData/<commit>/node (FriedLiver's writable Node compile cache)."""
    files = [f for f in glob.glob(os.path.join(tag_of(app), 'udd', 'CachedData', '*', 'node', '**'), recursive=True)
             if os.path.isfile(f)]
    return dict(files=len(files), kb=sum(os.path.getsize(f) for f in files) // 1024)

def idle(app, kind='idle', i=0):
    """Ready (first window) +60 s: memory snapshot (CPU over those 60 s = cpu_open_pct); then CPU average
    over the next 60 s (cpu_pct)."""
    if not pre_run_gate(app):
        return record(dict(app=app['id'], kind=kind, i=i, error='free memory < 2 GB, skipped'))
    rd = run_dir(app, kind, i)
    rec = dict(app=app['id'], kind=kind, i=i, free_gb_before=round(free_bytes() / 1024**3, 2))
    args = []
    if app['vscode']:
        args = [BIGREPO] if kind == 'bigrepo' else [FIX] + (twenty_files() if kind == 'files20' else [])
    ww = subprocess.Popen([WINWAIT, tag_of(app), '120'], stdout=subprocess.PIPE, text=True)
    time.sleep(0.2)
    t0 = time.time()
    launch(app, args, rd)
    win = wait_window(ww, 120)
    rec['window_ms'] = win and round((win - t0) * 1000)
    s0, t_s0 = snapshot(tag_of(app), exclude={ww.pid}), time.time()
    ok = win is not None and guarded_sleep(app, 60)
    if ok:
        s1 = snapshot(tag_of(app), exclude={ww.pid})
        rec.update(n_procs=s1['n_procs'], rss_mb=s1['rss_mb'], footprint_mb=s1['footprint_mb'], procs=s1['procs'],
                   cpu_open_pct=round((s1['cpu_s'] - s0['cpu_s']) / (time.time() - t_s0) * 100, 2))
        if kind in ('idle', 'bigrepo'):
            t1 = time.time()
            ok = guarded_sleep(app, 60)
            if ok:
                s2 = snapshot(tag_of(app), exclude={ww.pid})
                rec['cpu_pct'] = round((s2['cpu_s'] - s1['cpu_s']) / (time.time() - t1) * 100, 2)
                rec['cpu_by_proc'] = stats.cpu_by_name(s1['cpu'], s2['cpu'], time.time() - t1)
                rec.update(rss_mb_120=s2['rss_mb'], footprint_mb_120=s2['footprint_mb'], n_procs_120=s2['n_procs'])
    if not ok:
        rec['error'] = 'no window' if win is None else 'low memory abort'
    rec['killed_stragglers'] = quit_app(app)
    rec['node_cache'] = node_cache(app)
    record(rec)
    time.sleep(GAP_S)

# ---------------------------------------------------------------- phases

def machine_info():
    hw = sh('system_profiler', 'SPHardwareDataType')
    pick = lambda k: next((l.split(':', 1)[1].strip() for l in hw.splitlines() if l.strip().startswith(k)), '?')
    apps = {}
    for a in ARMS:
        info = sh('/usr/libexec/PlistBuddy', '-c', 'Print CFBundleShortVersionString', f'{a["path"]}/Contents/Info.plist').strip()
        pj = os.path.join(a['path'], 'Contents/Resources/app/product.json')
        extra = {}
        if os.path.exists(pj):
            d = json.load(open(pj))
            extra = dict(vscode_base=d.get('vscodeVersion') or d.get('version'), commit=(d.get('commit') or '')[:10])
        size_mb = int(sh('du', '-sk', a['path']).split()[0]) // 1024
        apps[a['id']] = dict(label=a['label'], path=a['path'], version=info, install_mb=size_mb, base=a.get('base'),
                             settings=a.get('settings'), env=a.get('env') or None, **extra)
    fetch = os.path.join(RES, 'fetch.json')
    return dict(ci=IN_CI, runner=os.environ.get('RUNNER_NAME'), run_url=(
                    f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                    if IN_CI else None),
                fetch=json.load(open(fetch)) if os.path.exists(fetch) else None,
                model=pick('Model Name') + ' / ' + pick('Model Identifier'), chip=pick('Chip'),
                cores=pick('Total Number of Cores'), ram=pick('Memory'),
                macos=sh('sw_vers', '-productVersion').strip() + ' (' + sh('sw_vers', '-buildVersion').strip() + ')',
                power_at_start=power(), date=datetime.date.today().isoformat(), apps=apps,
                fixture=dict(repo='microsoft/vscode-extension-samples',
                             commit=sh('git', '-C', FIX, 'rev-parse', 'HEAD').strip(),
                             big_file_bytes=os.path.getsize(BIG)),
                scenarios=SCENARIOS, shell_sleep=SHELL_SLEEP, suite=SUITE,
                bigrepo=os.path.isdir(BIGREPO) and dict(repo='microsoft/TypeScript',
                             commit=sh('git', '-C', BIGREPO, 'rev-parse', 'HEAD').strip(),
                             files=len(sh('git', '-C', BIGREPO, 'ls-files').splitlines())))

GUARD_DIRS = ['~/Library/Application Support/Cursor', '~/Library/Application Support/Antigravity IDE',
              '~/Library/Application Support/Antigravity', '~/Library/Application Support/Code',
              '~/Library/Application Support/ai.opencode.desktop', '~/.cursor', '~/.vscode', '~/.antigravity',
              '~/.antigravity-ide', '~/.gemini', '~/.config/opencode', '~/.local/share/opencode']

def guard_paths():
    paths = [os.path.expanduser(d) for d in GUARD_DIRS]
    for a in APPS:
        b = a['bundle']
        paths += [os.path.expanduser(p) for p in (f'~/Library/Preferences/{b}.plist', f'~/Library/Caches/{b}',
                  f'~/Library/Saved Application State/{b}.savedState', f'~/Library/HTTPStorages/{b}')]
    return paths

def preflight():
    os.makedirs(RES, exist_ok=True)
    json.dump(machine_info(), open(os.path.join(RES, 'machine.json'), 'w'), indent=2)
    bk = os.path.join(SCRATCH, 'prefs-backup')
    os.makedirs(bk, exist_ok=True)
    for a in APPS:   # backup of the only per-bundle state we cannot redirect away from the real profile
        src = os.path.expanduser(f'~/Library/Preferences/{a["bundle"]}.plist')
        if os.path.exists(src):
            shutil.copy2(src, bk)
    open(os.path.join(SCRATCH, 'start-marker'), 'w').write(str(time.time()))
    log('preflight ok', json.load(open(os.path.join(RES, 'machine.json')))['power_at_start'])

def postflight():
    marker = os.path.join(SCRATCH, 'start-marker')
    touched = []
    for p in guard_paths():
        if os.path.exists(p):
            out = sh('find', p, '-newer', marker, '-print')
            touched += out.split('\n')[:5] if out.strip() else []
    touched = [t for t in touched if t]
    json.dump(dict(touched_real_paths=touched), open(os.path.join(RES, 'isolation-check.json'), 'w'), indent=2)
    log('real-profile paths modified during the benchmark:', touched or 'none')

def run(only=None):
    apps = [a for a in ARMS if not only or a['id'] in only]
    vs = [a for a in apps if a['vscode']]
    ab = [a for a in vs if a.get('base', a['id']) in AB_IDS]
    log('arms:', [a['id'] for a in apps], 'scenarios:', SCENARIOS)
    log('warm-up (discarded) - also the first-ever launch of each fresh profile')
    for a in apps:
        cold(a, 'warmup', 0)
    if SUITE == 'idle':
        for r in range(1, SAMPLES + 1):
            log(f'idle round {r}/{SAMPLES}')
            for a in apps:
                idle(a, 'idle', r)
        log('done (idle suite)')
        return
    for r in range(1, 6):                       # round-robin: thermal/battery drift hits every app equally
        log(f'cold-start round {r}/5')
        for a in apps:
            cold(a, 'cold', r)
    for r in range(1, 4):
        log(f'5 MB file round {r}/3')
        for a in vs:
            cold(a, 'big5mb', r)
    for r in range(1, SAMPLES + 1):
        log(f'idle round {r}/{SAMPLES}')
        for a in apps:
            idle(a, 'idle', r)
        for a in vs:
            idle(a, 'files20', r)
    if 'slow-shell' in SCENARIOS:
        # own profile per arm (HOME with or without a slow .zshrc, plus the file-search probe extension)
        sh_arms = [dict(a, prof=a['id'] + '@shell', probe=True) for a in ab]
        log('slow-shell warm-up (discarded)')
        for a in sh_arms:
            cold(a, 'shell-warmup', 0)
        for r in range(1, SAMPLES + 1):
            log(f'slow-shell round {r}/{SAMPLES}')
            for a in sh_arms:
                cold(a, 'shell-fast', r)
                cold(a, 'shell-slow', r)
    if 'large-repo' in SCENARIOS:
        if not os.path.isdir(BIGREPO):
            log('large-repo: no checkout at', BIGREPO, '- skipped')
        for r in range(1, SAMPLES + 1 if os.path.isdir(BIGREPO) else 1):
            log(f'large-repo round {r}/{SAMPLES}')
            for a in ab:
                idle(a, 'bigrepo', r)
    log('done')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if cmd == 'preflight':
        preflight()
    elif cmd == 'postflight':
        postflight()
    elif cmd == 'run':
        only = sys.argv[3].split(',') if len(sys.argv) > 3 and sys.argv[2] == '--only' else None
        run(only)
    elif cmd == 'one':                          # bench.py one <app> <kind>  (debug a single run)
        a = BY_ID[sys.argv[2]]
        (idle if sys.argv[3] in ('idle', 'files20', 'bigrepo') else cold)(a, sys.argv[3], 0)
    elif cmd == 'selftest':                     # cleanup must reject anything but our own roots
        real = tempfile.mkdtemp(prefix='ebp-', dir=PROF_PARENT)
        try:
            assert valid_root_entry(real)
            for bad in ('/', os.path.expanduser('~'), '/private/tmp', PROF_PARENT + '/ebp-../x', '/tmp/' + os.path.basename(real),
                        PROF_PARENT + '/ebp-x/../..', PROF_PARENT + '/other-dir', PROF_PARENT + '/ebp-does-not-exist',
                        os.path.join(SCRATCH, 'ebp-abc')):
                assert not valid_root_entry(bad), bad
            os.chmod(real, 0o755)
            assert not valid_root_entry(real), 'non-0700 root accepted'
            link = real + '_lnk'
            os.symlink(real, link)
            assert not valid_root_entry(link), 'symlink accepted'
            os.unlink(link)
        finally:
            os.rmdir(real)
        print('selftest ok')
    elif cmd == 'cleanup':
        cleanup()
