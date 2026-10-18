"""Per-tool command lines and output parsers. Pure functions: no subprocess, no network.

Every parser takes the tool's raw stdout and returns one normalized dict:

    answer        final assistant text
    session_id    id to resume the same conversation (S2 after S1, S5 after S4)
    tokens        {input, cache_read, cache_write, output, reasoning}
                  input  = uncached input tokens (billed at the base input price)
                  output = all billed output tokens, reasoning/thinking included
                  reasoning = the reasoning part of output (informational)
    reported_cost_usd  what the tool itself says it cost, if it says (else None)
    tool_calls    number of tool calls the agent made
    bytes_read    bytes of tool output that went back into the context (None = not observable)
    files_read    sorted list of paths the agent read (None = not observable)

Field names come from each tool's docs (README, "How each tool reports usage").
"""
import json

TOKEN_KEYS = ('input', 'cache_read', 'cache_write', 'output', 'reasoning')


def _tokens(**kw):
    return {k: int(kw.get(k) or 0) for k in TOKEN_KEYS}


def _lines(raw):
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith('{'):
            try:
                yield json.loads(line)
            except ValueError:
                pass  # a non-JSON log line on stdout


def _text(content):
    """Tool-result content as text: a string, or a list of {type: text, text} blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(c.get('text', '') if isinstance(c, dict) else str(c) for c in content)
    return '' if content is None else json.dumps(content)


def _result(answer='', session_id=None, tokens=None, cost=None, calls=0, nbytes=None, files=None):
    return {'answer': answer, 'session_id': session_id, 'tokens': tokens or _tokens(),
            'reported_cost_usd': cost, 'tool_calls': calls, 'bytes_read': nbytes,
            'files_read': None if files is None else sorted(files)}


# ---- Claude Code: claude -p --output-format stream-json --verbose ----

def parse_claude(raw):
    """Usage per API call is on each `assistant` message (message.usage); a message with several
    content blocks is streamed once per block with the same id, so count each id once. The final
    `result` line has the answer, session_id and total_cost_usd (which, after --resume, includes
    earlier runs, so the runner does not use it as this scenario's cost)."""
    usage, calls, nbytes, files = {}, 0, 0, set()
    answer, sid, cost = '', None, None
    for ev in _lines(raw):
        t = ev.get('type')
        if t == 'system' and ev.get('subtype') == 'init':
            sid = ev.get('session_id', sid)
        elif t == 'assistant':
            msg = ev.get('message') or {}
            if msg.get('usage'):  # subagent messages count too: they are API calls of this run
                usage[msg.get('id') or len(usage)] = msg['usage']
            for b in msg.get('content') or []:
                if b.get('type') == 'tool_use':
                    calls += 1
                    p = (b.get('input') or {}).get('file_path')
                    if b.get('name') == 'Read' and p:
                        files.add(p)
        elif t == 'user':
            for b in (ev.get('message') or {}).get('content') or []:
                if isinstance(b, dict) and b.get('type') == 'tool_result':
                    nbytes += len(_text(b.get('content')).encode())
        elif t == 'result':
            answer, sid, cost = ev.get('result', ''), ev.get('session_id', sid), ev.get('total_cost_usd')
            if not usage and ev.get('usage'):
                usage['result'] = ev['usage']
    tok = _tokens(
        input=sum(u.get('input_tokens', 0) for u in usage.values()),
        cache_read=sum(u.get('cache_read_input_tokens', 0) for u in usage.values()),
        cache_write=sum(u.get('cache_creation_input_tokens', 0) for u in usage.values()),
        output=sum(u.get('output_tokens', 0) for u in usage.values()))
    return _result(answer, sid, tok, cost, calls, nbytes, files)


# ---- Codex CLI: codex exec --json (JSON Lines) ----

CODEX_TOOL_ITEMS = {'command_execution', 'mcp_tool_call', 'web_search', 'file_change'}


def parse_codex(raw):
    """thread.started carries thread_id (resume with `codex exec resume <id>`); turn.completed
    carries usage {input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}.
    input_tokens includes the cached part (OpenAI convention), so uncached = input - cached."""
    sid, answer, calls, nbytes = None, '', 0, 0
    inp = cached = out = reasoning = 0
    for ev in _lines(raw):
        t = ev.get('type')
        if t == 'thread.started':
            sid = ev.get('thread_id')
        elif t == 'item.completed':
            item = ev.get('item') or {}
            it = item.get('type')
            if it == 'agent_message':
                answer = item.get('text', answer)
            elif it in CODEX_TOOL_ITEMS:
                calls += 1
                out_text = item.get('aggregated_output')
                if out_text is None and it == 'mcp_tool_call':
                    out_text = _text((item.get('result') or {}).get('content'))
                nbytes += len((out_text or '').encode())
        elif t == 'turn.completed':
            u = ev.get('usage') or {}
            inp += u.get('input_tokens', 0)
            cached += u.get('cached_input_tokens', 0)
            out += u.get('output_tokens', 0)
            reasoning += u.get('reasoning_output_tokens', 0)
    tok = _tokens(input=max(0, inp - cached), cache_read=cached, output=out, reasoning=reasoning)
    return _result(answer, sid, tok, None, calls, nbytes, None)


# ---- Gemini CLI: gemini -p --output-format stream-json ----

def parse_gemini(raw):
    """The final `result` event's stats come from the CLI's own metrics (convertToStreamStats):
    input_tokens = promptTokenCount (cached part included), cached = cachedContentTokenCount,
    total_tokens = totalTokenCount. output_tokens there is candidates only, so thinking is
    billed output = total - input. tool_result.output is the CLI's display text of each result."""
    sid, parts, calls, nbytes, files = None, [], 0, 0, set()
    stats = {}
    for ev in _lines(raw):
        t = ev.get('type')
        if t == 'init':
            sid = ev.get('session_id', sid)
        elif t == 'message' and ev.get('role') == 'assistant':
            parts.append(ev.get('content', ''))
        elif t == 'tool_use':
            calls += 1
            p = (ev.get('parameters') or {}).get('file_path') or (ev.get('parameters') or {}).get('absolute_path')
            if p and 'read' in (ev.get('tool_name') or ''):
                files.add(p)
        elif t == 'tool_result':
            nbytes += len(_text(ev.get('output')).encode())
        elif t == 'result':
            stats = ev.get('stats') or {}
            sid = ev.get('session_id', sid)
    inp, cached, total = stats.get('input_tokens', 0), stats.get('cached', 0), stats.get('total_tokens', 0)
    out = max(stats.get('output_tokens', 0), total - inp)
    tok = _tokens(input=max(0, inp - cached), cache_read=cached, output=out,
                  reasoning=max(0, out - stats.get('output_tokens', 0)))
    return _result(''.join(parts), sid, tok, None, stats.get('tool_calls', calls), nbytes, files)


# ---- Cursor: cursor-agent -p --output-format stream-json ----

def parse_cursor(raw):
    """The documented result event has no usage; newer CLIs add usage {inputTokens (uncached),
    outputTokens, cacheReadTokens, cacheWriteTokens} (Cursor staff, forum thread in README).
    No usage on the result -> tokens stay 0 and the runner marks the row `tokens: not reported`."""
    sid, answer, calls, nbytes, files, usage = None, '', 0, 0, set(), None
    for ev in _lines(raw):
        t = ev.get('type')
        if t == 'system':
            sid = ev.get('session_id', sid)
        elif t == 'tool_call' and ev.get('subtype') == 'completed':
            calls += 1
            for name, call in (ev.get('tool_call') or {}).items():
                res = (call or {}).get('result')
                nbytes += len(json.dumps(res).encode()) if res is not None else 0
                p = ((call or {}).get('args') or {}).get('path')
                if name == 'readToolCall' and p:
                    files.add(p)
        elif t == 'result':
            answer, sid, usage = ev.get('result', ''), ev.get('session_id', sid), ev.get('usage')
    u = usage or {}
    tok = _tokens(input=u.get('inputTokens'), cache_read=u.get('cacheReadTokens'),
                  cache_write=u.get('cacheWriteTokens'), output=u.get('outputTokens'))
    r = _result(answer, sid, tok, None, calls, nbytes, files)
    r['usage_reported'] = usage is not None
    return r


# ---- Antigravity CLI: agy -p --output-format stream-json ----

def parse_antigravity(raw):
    """Events are {"event": init|step_update|result}. result.usage = {input_tokens, output_tokens,
    thinking_tokens, cache_read_tokens, total_tokens}. In the docs' examples total = input + output,
    so cache reads are inside input_tokens and thinking inside output_tokens (an inference, see README)."""
    sid, answer, calls, nbytes, usage = None, '', 0, 0, {}
    seen = set()
    for ev in _lines(raw):
        e = ev.get('event') or ev.get('type')
        sid = ev.get('conversation_id', sid)
        if e == 'step_update' and ev.get('step_type') == 'tool' and ev.get('state') == 'DONE':
            key = ev.get('step_index')
            if key not in seen:
                seen.add(key)
                calls += 1
                nbytes += len(_text((ev.get('tool_info') or {}).get('output')).encode())
        elif e == 'result' or ('usage' in ev and 'response' in ev):
            answer, usage = ev.get('response', ''), ev.get('usage') or {}
    inp, cr = usage.get('input_tokens', 0), usage.get('cache_read_tokens', 0)
    tok = _tokens(input=max(0, inp - cr), cache_read=cr, output=usage.get('output_tokens'),
                  reasoning=usage.get('thinking_tokens'))
    return _result(answer, sid, tok, None, calls, nbytes, None)


# ---- Command lines ----

def command(tool, prompt, model, session_id=None, extra=()):
    """argv for one headless turn. `session_id` continues an earlier conversation."""
    if tool == 'claude':
        # --bare: no CLAUDE.md, hooks, plugins, MCP servers or memory from the machine; needs ANTHROPIC_API_KEY.
        argv = ['claude', '--bare', '-p', prompt, '--output-format', 'stream-json', '--verbose', '--model', model,
                '--permission-mode', 'acceptEdits', '--permission-prompts', 'none',
                '--allowedTools', 'Read,Grep,Glob,Edit,Write,Bash,WebFetch,WebSearch']
        return argv + (['--resume', session_id] if session_id else []) + list(extra)
    if tool == 'codex':
        flags = ['--json', '--model', model, '--sandbox', 'workspace-write', '--skip-git-repo-check', '--ignore-user-config']
        if session_id:
            return ['codex', 'exec', 'resume', session_id, *flags, *extra, prompt]
        return ['codex', 'exec', *flags, *extra, prompt]
    if tool == 'gemini':
        argv = ['gemini', '-p', prompt, '--output-format', 'stream-json', '--model', model,
                '--approval-mode', 'yolo', '--skip-trust']
        # ponytail: --resume takes "latest" or an index, not an id; each chain runs in its own fresh checkout, so latest is ours.
        return argv + (['--resume', 'latest'] if session_id else []) + list(extra)
    if tool == 'cursor':
        argv = ['cursor-agent', '-p', prompt, '--output-format', 'stream-json', '--model', model, '--force']
        return argv + (['--resume', session_id] if session_id else []) + list(extra)
    if tool == 'antigravity':
        argv = ['agy', '-p', prompt, '--output-format', 'stream-json', '--model', model, '--dangerously-skip-permissions']
        return argv + (['--conversation', session_id] if session_id else []) + list(extra)
    raise ValueError(f'no headless command for {tool}')


PARSERS = {'claude': parse_claude, 'codex': parse_codex, 'gemini': parse_gemini,
           'cursor': parse_cursor, 'antigravity': parse_antigravity}


def cost_usd(tokens, price):
    """List-price cost of one run's tokens. `price` is a prices.json row (USD per 1M tokens)."""
    if not price:
        return None
    return round((tokens['input'] * price['input'] + tokens['cache_read'] * price['cache_read']
                  + tokens['cache_write'] * price.get('cache_write', 0) + tokens['output'] * price['output']) / 1e6, 6)
