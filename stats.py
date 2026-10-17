"""Pure helpers shared by bench.py and report.py: perf-mark names and phases, marker-file and log
parsing, medians and the noise verdict. No I/O; unit-tested in tests/."""
import math, re, statistics

START = 'code/willLoadMainBundle'   # = the main process's Node timeOrigin, i.e. process start
# Every fixed-name perf mark VS Code 1.142.0 writes (`grep -rhoE "mark\('code/[^']+" src`, tag 1.142.0),
# plus the numbered/named instances of its templated ones. Each is recorded as its offset from START via
# --prof-duration-markers=START-<mark>; the CLI splits on '-', so marks with a dash in the name can't be
# used (e.g. per-extension marks for vscode.git-base). A mark the product never wrote is simply absent.
_MAIN = """didStartMain willConfigureCommandlineSwitches didConfigureCommandlineSwitches willGetUserDataPath
didGetUserDataPath willGetPreferredSystemLanguages didGetPreferredSystemLanguages willResolveNlsConfiguration
didResolveNlsConfiguration willGenerateNls didGenerateNls willLoadNls didLoadNls willStartCrashReporter
didStartCrashReporter willLoadMainBundle didLoadMainBundle willRunMainBundle didRunMainBundle
willWaitForAppReady didWaitForAppReady mainAppReady willStartCodeApplication willStartMainServer
didStartMainServer willCreateMainServices didCreateMainServices willInitMainServices didInitMainServices
willInitAppServices didInitAppServices willResolveMachineId didResolveMachineId willInitChannels didInitChannels
willSetupProtocolUrlHandlers didSetupProtocolUrlHandlers willOpenFirstWindow didOpenFirstWindow
willRegisterSchemesAsPrivileged didRegisterSchemesAsPrivileged willCreateCodeWindow didCreateCodeWindow
willRestoreCodeWindowState didRestoreCodeWindowState willCreateCodeBrowserWindow didCreateCodeBrowserWindow
willOpenNewWindow fork/start"""
_RENDERER = """didStartRenderer willShowPartsSplash didShowPartsSplash willAddCssLoader didAddCssLoader willBootstrapESM
didBootstrapESM willLoadWorkbenchMain didLoadWorkbenchMain willWaitForWindowConfig didWaitForWindowConfig
willInitWorkspaceService didInitWorkspaceService willInitUserConfiguration didInitUserConfiguration
willInitWorkspaceConfiguration didInitWorkspaceConfiguration willInitStorage didInitStorage
willConnectSharedProcess didConnectSharedProcess willInitRequiredUserData didInitRequiredUserData
willInitOtherUserData didInitOtherUserData willStartWorkbench didRemovePartsSplash willRegisterListeners
didRegisterListeners willLoadExtensions didLoadExtensions willRestoreEditors didRestoreEditors
willRestoreViewlet didRestoreViewlet willRestorePanel didRestorePanel willRestoreAuxiliaryBar
didRestoreAuxiliaryBar willOpenDefaultViews didOpenDefaultViews willRegisterExplorerViews
didRegisterExplorerViews willResolveExplorer didResolveExplorer willCreateTextFileEditorControl
didCreateTextFileEditorControl willSetInputToTextFileEditor didSetInputToTextFileEditor
willResolveTextFileEditorModel didResolveTextFileEditorModel restoreEditors/editorGroupsReady
restoreEditors/editorsToOpenResolved restoreEditors/editorsOpened restoreEditors/editorGroupsRestored
didStartWorkbench LifecyclePhase/Starting LifecyclePhase/Ready LifecyclePhase/Restored LifecyclePhase/Eventually
willCreateWorkbenchContributions/1 didCreateWorkbenchContributions/1 willCreateWorkbenchContributions/2
didCreateWorkbenchContributions/2 willCreateWorkbenchContributions/3 didCreateWorkbenchContributions/3
willCreateWorkbenchContributions/4 didCreateWorkbenchContributions/4 willGetTerminalLayoutInfo
didGetTerminalLayoutInfo terminal/willConnectPtyHost terminal/didConnectPtyHost
terminal/willGetTerminalBackend terminal/didGetTerminalBackend"""
_EXTHOST = """extHost/willConnectToRenderer extHost/didConnectToRenderer extHost/didWaitForInitData
extHost/willWaitForConfig extHost/didWaitForConfig extHost/didCreateServices extHost/didInitAPI
extHost/didInitProxyResolver extHost/ready extHost/willActivateExtension/vscode.git
extHost/didActivateExtension/vscode.git extHost/willActivateExtension/vscode.github
extHost/didActivateExtension/vscode.github"""
MARKS = ['code/' + m for m in (_MAIN + ' ' + _RENDERER + ' ' + _EXTHOST).split() if 'code/' + m != START]

# (label, from, to). The first N_MAIN_PHASES are consecutive and sum to process start -> workbench ready.
PHASES = [
    ('Process start → main started', START, 'code/didStartMain'),
    ('Main: switches, locale, app ready', 'code/didStartMain', 'code/mainAppReady'),
    ('Main services → window opened', 'code/mainAppReady', 'code/willOpenNewWindow'),
    ('Renderer start → workbench JS load', 'code/willOpenNewWindow', 'code/willLoadWorkbenchMain'),
    ('Workbench JS load + evaluate', 'code/willLoadWorkbenchMain', 'code/didLoadWorkbenchMain'),
    ('Workbench main → services start', 'code/didLoadWorkbenchMain', 'code/willStartWorkbench'),
    ('Workbench services, contributions, restore', 'code/willStartWorkbench', 'code/didStartWorkbench'),
    # breakdowns and the extension host (not additive)
    ('· BlockStartup contributions', 'code/willCreateWorkbenchContributions/1', 'code/didCreateWorkbenchContributions/1'),
    ('· BlockRestore contributions', 'code/willCreateWorkbenchContributions/2', 'code/didCreateWorkbenchContributions/2'),
    ('· Editor restore', 'code/willRestoreEditors', 'code/didRestoreEditors'),
    ('Extension scan + registration (renderer)', 'code/willLoadExtensions', 'code/didLoadExtensions'),
    ('Extension host: connect to renderer', 'code/extHost/willConnectToRenderer', 'code/extHost/didConnectToRenderer'),
    ('Workbench ready → extension host ready', 'code/didStartWorkbench', 'code/extHost/ready'),
    ('Extension host ready (from process start)', START, 'code/extHost/ready'),
]
N_MAIN_PHASES = 7

CONTRIB = re.compile(r"Creation of workbench contribution '([^']+)' took (\d+)ms")


def marker_args():
    return [f'--prof-duration-markers={START}-{m}' for m in MARKS]


def parse_markers(text):
    """--prof-duration-markers-file content ("name\\tms\\tname\\tms...") -> {name: ms}."""
    out = {}
    for line in text.splitlines():
        p = line.strip().split('\t')
        out.update((k, round(float(v))) for k, v in zip(p[0::2], p[1::2]))
    return out


def offsets(markers):
    """{START-<mark>: ms} -> {<mark>: ms since process start}, START itself at 0."""
    off = {k.split('-', 1)[1]: v for k, v in markers.items() if k.startswith(START + '-')}
    return {START: 0, **off} if off else {}


def phases(off):
    return {name: off[b] - off[a] for name, a, b in PHASES if a in off and b in off}


def slow_contribs(log_text):
    """renderer.log -> [(contribution id, ms)], slowest first. VS Code logs these at warn level, only above
    20 ms (BlockStartup/BlockRestore) or 100 ms (later phases): src/vs/workbench/common/contributions.ts."""
    return sorted(((m[1], int(m[2])) for m in CONTRIB.finditer(log_text)), key=lambda x: (-x[1], x[0]))


def p90(xs):                                   # nearest-rank; with n=5 this is the slowest run
    xs = sorted(xs)
    return xs[max(0, math.ceil(0.9 * len(xs)) - 1)]


FLOORS = {'ms': lambda base: 0.03 * abs(base), 'mb': lambda base: 10, 'pct': lambda base: 1.0}


def compare(base, arm, unit):
    """Arm vs base (lower is better). Beyond noise only if |Δ median| exceeds either arm's min–max spread
    AND the floor (3 % for times, 10 MB, 1 point of CPU) - the keep rule of CORE-PERF-PLAN.md §4.4."""
    if not base or not arm:
        return None
    mb, ma = statistics.median(base), statistics.median(arm)
    d = ma - mb
    spread = max(max(base) - min(base), max(arm) - min(arm))
    sig = abs(d) > spread and abs(d) >= FLOORS[unit](mb)
    return dict(base=mb, arm=ma, delta=d, pct=(d / mb * 100) if mb else None, spread=spread,
                n=(len(base), len(arm)), verdict=('worse' if d > 0 else 'better') if sig else 'noise')


def split_list(text, all_items=()):
    """Workflow input -> list. '' or 'all' -> all_items, 'none' -> []."""
    text = (text or '').strip()
    if text in ('', 'all'):
        return list(all_items)
    if text == 'none':
        return []
    return [t.strip() for t in text.split(',') if t.strip()]


def cache_lines(log_text):
    """'[node-compile-cache] <kind>: ... (status: ..., configured: ..., active: ...)' lines, one per process log."""
    return [l[l.index('[node-compile-cache]'):].strip() for l in log_text.splitlines() if '[node-compile-cache]' in l]
