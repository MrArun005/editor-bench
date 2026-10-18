"""IDE-side measure, no LLM: what S3 ("where is X defined and what calls it?") puts into the context
when one fixed trace -- find the definition, find the callers, read the defining file -- goes through
each tool's own search/read output format and caps.

The formats and caps below are emulations of each tool's documented or observed behaviour, versioned
here so they can be checked and corrected; the FriedLiver row is not emulated, it is the real
index_* answers from FriedLiver's own code (ide_side.mjs). Tokens are bytes/4 (an estimate; no
tokenizer runs offline for all four vendors).
"""
import json, math, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

# Claude Code: Grep (ripgrep, content mode: path:line:text) with a result cap; Read: `cat -n` style
# (6-wide line number, tab), first 2000 lines, lines over 2000 chars cut.
CLAUDE_GREP_HEAD_LIMIT = int(os.environ.get('CLAUDE_GREP_HEAD_LIMIT', 250))
CLAUDE_READ_LINES, CLAUDE_LINE_CHARS = 2000, 2000
# Codex: shell commands (`rg -n`, `sed -n`); what goes back to the model is cut to a head+tail of
# 10 KiB / 256 lines (codex-rs exec output formatting; check against your version).
CODEX_MAX_BYTES, CODEX_MAX_LINES = 10 * 1024, 256
CODEX_READ_CHUNK = 250  # lines per `sed -n` read, as Codex usually pages a file
# Gemini CLI: search_file_content ("File: path" / "L<n>: text" blocks), read_file up to 2000 lines.
GEMINI_READ_LINES, GEMINI_LINE_CHARS = 2000, 2000


def est_tokens(nbytes):
    return math.ceil(nbytes / 4)


def git_grep(repo, args):
    r = subprocess.run(['git', 'grep', '--untracked', '-n', '-I', *args], cwd=repo, capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l]


def definition_pattern(symbol):
    # POSIX ERE: git grep -E does not take \s or \b on every platform.
    s, sp = re.escape(symbol), '[[:space:]]'
    return (rf'(function|class|interface|type|const|let|var|def|enum){sp}+{s}([^A-Za-z0-9_$]|$)'
            rf'|^{sp}*(export{sp}+)?(async{sp}+)?{s}{sp}*\([^;]*\)[^;]*\{{')  # a method: `name(...) {`, not a call


def trace(repo, symbol):
    """The fixed S3 trace: the same three operations for every tool."""
    defs = git_grep(repo, ['-E', definition_pattern(symbol)])
    calls = git_grep(repo, ['-w', symbol])
    def_file = defs[0].split(':', 1)[0] if defs else None
    text = ''
    if def_file:
        with open(os.path.join(repo, def_file), encoding='utf-8', errors='replace') as f:
            text = f.read()
    return defs, calls, def_file, text


def def_line(defs):
    return int(defs[0].split(':', 2)[1]) if defs else 1


def claude_read(text):
    lines = text.split('\n')[:CLAUDE_READ_LINES]
    return ''.join(f'{i + 1:>6}\t{l[:CLAUDE_LINE_CHARS]}\n' for i, l in enumerate(lines))


def head_tail(text, max_bytes, max_lines):
    lines = text.split('\n')
    if len(lines) > max_lines:
        h = max_lines // 2
        text = '\n'.join(lines[:h] + [f'[... {len(lines) - max_lines} lines omitted ...]'] + lines[-h:])
    b = text.encode()
    if len(b) > max_bytes:
        h = max_bytes // 2
        text = b[:h].decode(errors='ignore') + '\n[... output truncated ...]\n' + b[-h:].decode(errors='ignore')
    return text


def gemini_grep(pattern, hits):
    by_file = {}
    for h in hits:
        path, line, txt = h.split(':', 2)
        by_file.setdefault(path, []).append(f'L{line}: {txt.strip()}')
    body = ''.join(f'File: {p}\n' + '\n'.join(ls) + '\n---\n' for p, ls in by_file.items())
    return f'Found {len(hits)} matches for pattern "{pattern}" in path ".":\n---\n{body}'


def outputs(repo, symbol, friedliver=None):
    """Per tool, the text of each trace step as that tool would return it."""
    defs, calls, def_file, text = trace(repo, symbol)
    start = max(1, def_line(defs) - 20)
    window = '\n'.join(text.split('\n')[start - 1:start - 1 + CODEX_READ_CHUNK])
    out = {
        'claude-code': {
            'find definition (Grep)': '\n'.join(defs[:CLAUDE_GREP_HEAD_LIMIT]),
            'find callers (Grep)': '\n'.join(calls[:CLAUDE_GREP_HEAD_LIMIT]),
            'read file (Read)': claude_read(text),
        },
        'codex': {
            'find definition (rg -n)': head_tail('\n'.join(defs), CODEX_MAX_BYTES, CODEX_MAX_LINES),
            'find callers (rg -n)': head_tail('\n'.join(calls), CODEX_MAX_BYTES, CODEX_MAX_LINES),
            f'read {CODEX_READ_CHUNK} lines (sed -n)': head_tail(window, CODEX_MAX_BYTES, CODEX_MAX_LINES),
        },
        'gemini-cli': {
            'find definition (search_file_content)': gemini_grep(definition_pattern(symbol), defs),
            'find callers (search_file_content)': gemini_grep(symbol, calls),
            'read file (read_file)': '\n'.join(l[:GEMINI_LINE_CHARS] for l in text.split('\n')[:GEMINI_READ_LINES]),
        },
    }
    if friedliver:
        out['friedliver (index + Read)'] = {
            'find definition (index_symbols)': friedliver['answers']['index_symbols'],
            'find callers (index_search)': friedliver['answers']['index_search'],
            'read file (agent Read)': claude_read(text),
        }
    return {'symbol': symbol, 'definition_file': def_file, 'definition_hits': len(defs), 'caller_hits': len(calls), 'tools': out}


def summarize(o):
    rows = []
    for tool, steps in o['tools'].items():
        b = {k: len(v.encode()) for k, v in steps.items()}
        rows.append({'tool': tool, 'steps': {k: {'bytes': n, 'est_tokens': est_tokens(n)} for k, n in b.items()},
                     'bytes': sum(b.values()), 'est_tokens': est_tokens(sum(b.values()))})
    return rows


def friedliver_answers(repo, symbol, def_file, src):
    """Runs FriedLiver's real index code (ide_side.mjs) when FRIEDLIVER_SRC points at a checkout."""
    if not src:
        return None
    r = subprocess.run(['node', os.path.join(HERE, 'ide_side.mjs'), '--repo', repo, '--src', src, '--symbol', symbol,
                        '--file', def_file or ''], capture_output=True, text=True, timeout=3600)
    if r.returncode:
        raise RuntimeError(f'ide_side.mjs failed: {r.stderr[-2000:]}')
    return json.loads(r.stdout)


def run(cfg, repo_dir, out):
    os.makedirs(out, exist_ok=True)
    results = []
    for s in cfg['scenarios']:
        if not s.get('trace'):
            continue
        sym = s['trace']['symbol']
        _, _, def_file, _ = trace(repo_dir, sym)
        fl = friedliver_answers(repo_dir, sym, def_file, os.environ.get('FRIEDLIVER_SRC'))
        o = outputs(repo_dir, sym, fl)
        results.append({'scenario': s['id'], 'symbol': sym, 'definition_file': o['definition_file'],
                        'definition_hits': o['definition_hits'], 'caller_hits': o['caller_hits'],
                        'tools': summarize(o), 'index': fl and fl.get('index')})
    with open(os.path.join(out, 'context-replay.json'), 'w') as f:
        json.dump(results, f, indent=1)
    return results
