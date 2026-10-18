"""A headless Agent Client Protocol client, to run FriedLiver's agents the way FriedLiver starts them
(agent-core/main/agents/registry.ts): claude-agent-acp, codex-acp, `gemini --acp`.

It speaks JSON-RPC 2.0 over the agent's stdio, answers the agent's fs/* and permission requests,
and writes every message it sees to a transcript (JSON Lines). `parse_acp` turns a transcript of one
prompt turn into the same normalized dict as adapters.py, so live runs and replays share one parser.

Usage comes from two places (ACP SDK 1.9 schema):
  - PromptResponse.usage (UNSTABLE in ACP): {inputTokens, outputTokens, cachedReadTokens,
    cachedWriteTokens, thoughtTokens, totalTokens}, cumulative "across all turns" of the session,
    so a turn's usage is the difference from the previous turn's.
  - session/update usage_update: {used, size, cost?}, the context window and cumulative cost. This is
    what FriedLiver's UI folds today (shared/session.ts applySessionUpdate); kept as context_used.
Deviation from FriedLiver: this client offers fs read/write but no terminal capability, so agents run
shell commands themselves. Command output still reaches the model the same way.
"""
import json, os, subprocess, threading, queue

from adapters import _result, _tokens

CLIENT_CAPABILITIES = {'fs': {'readTextFile': True, 'writeTextFile': True}, 'terminal': False}


def usage_tokens(u):
    """ACP Usage -> normalized tokens. Which agent counts cache inside inputTokens differs; the ACP
    adapters for Claude report Anthropic's uncached input, so input is taken as uncached."""
    u = u or {}
    return _tokens(input=u.get('inputTokens'), cache_read=u.get('cachedReadTokens'),
                   cache_write=u.get('cachedWriteTokens'),
                   output=(u.get('outputTokens') or 0), reasoning=u.get('thoughtTokens'))


def parse_acp(raw, prev_usage=None):
    """One turn's transcript (JSON Lines of {dir: in|out, msg}) -> normalized dict.
    `prev_usage` is the session's cumulative usage after the previous turn (ACP usage is cumulative)."""
    parts, calls, nbytes, files, usage, ctx, sid = [], set(), 0, set(), None, None, None
    for line in raw.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        m = rec.get('msg') or {}
        params = m.get('params') or {}
        sid = params.get('sessionId', sid)
        if m.get('method') == 'session/update':
            u = params.get('update') or {}
            kind = u.get('sessionUpdate')
            if kind == 'agent_message_chunk' and (u.get('content') or {}).get('type') == 'text':
                parts.append(u['content'].get('text', ''))
            elif kind == 'tool_call':
                calls.add(u.get('toolCallId'))
                if u.get('kind') == 'read':
                    files.update(loc.get('path') for loc in u.get('locations') or [] if loc.get('path'))
            elif kind == 'tool_call_update' and u.get('status') in ('completed', 'failed'):
                # ponytail: the tool's displayed result stands in for what the model got back; a file the
                # agent read through fs/read_text_file is not counted again, it shows up here too.
                for c in u.get('content') or []:
                    inner = c.get('content') if isinstance(c, dict) else None
                    nbytes += len((inner.get('text', '') if isinstance(inner, dict) else '').encode())
            elif kind == 'usage_update':
                ctx = {'used': u.get('used'), 'size': u.get('size'), 'cost': u.get('cost')}
        elif m.get('method') == 'fs/read_text_file':
            files.add(params.get('path'))
        elif isinstance(m.get('result'), dict) and 'stopReason' in m['result']:
            usage = m['result'].get('usage')
    tok = usage_tokens(usage)
    if prev_usage:
        before = usage_tokens(prev_usage)
        tok = {k: max(0, tok[k] - before[k]) for k in tok}
    r = _result(''.join(parts), sid, tok, None, len(calls), nbytes, files)
    r['usage_reported'] = usage is not None
    r['cumulative_usage'] = usage
    r['context'] = ctx
    return r


def pick_permission(params, deny_kinds):
    """Allow a tool call, unless its kind is denied (e.g. `fetch` in CI): then reject it."""
    opts = params.get('options') or []
    kind = (params.get('toolCall') or {}).get('kind')
    want = ('reject_once', 'reject_always') if kind in deny_kinds else ('allow_always', 'allow_once')
    pick = next((o for k in want for o in opts if o.get('kind') == k), None)
    return {'outcome': 'selected', 'optionId': pick['optionId']} if pick else {'outcome': 'cancelled'}


class AcpAgent:
    """One agent process; prompt() runs one turn and returns its transcript (for parse_acp)."""

    def __init__(self, argv, cwd, env, mcp_servers=None, system_append=None, deny_kinds=frozenset()):
        """`env` is the agent's whole environment (bench.arm_env): nothing is inherited."""
        self.cwd, self.next_id, self.pending, self.deny_kinds = cwd, 0, {}, deny_kinds
        self.mcp_servers, self.system_append = mcp_servers or [], system_append
        self.lock, self.turn = threading.Lock(), []
        self.proc = subprocess.Popen(argv, cwd=cwd, env=env, text=True, bufsize=1,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        threading.Thread(target=self._read, daemon=True).start()
        init = self.request('initialize', {'protocolVersion': 1, 'clientCapabilities': CLIENT_CAPABILITIES})
        self.auth_methods = init.get('authMethods') or []
        self.session_id = None

    def _log(self, direction, msg):
        with self.lock:
            self.turn.append(json.dumps({'dir': direction, 'msg': msg}))

    def _send(self, msg):
        self._log('out', msg)
        self.proc.stdin.write(json.dumps(msg) + '\n')
        self.proc.stdin.flush()

    def request(self, method, params, timeout=1800):
        self.next_id += 1
        q = self.pending[self.next_id] = queue.Queue()
        self._send({'jsonrpc': '2.0', 'id': self.next_id, 'method': method, 'params': params})
        msg = q.get(timeout=timeout)
        if 'error' in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg.get('result') or {}

    def _read(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            self._log('in', msg)
            if 'method' in msg and 'id' in msg:
                self._answer(msg)
            elif 'id' in msg and msg['id'] in self.pending:
                self.pending.pop(msg['id']).put(msg)

    def _answer(self, msg):
        p, method = msg.get('params') or {}, msg['method']
        try:
            if method == 'fs/read_text_file':
                with open(p['path'], encoding='utf-8', errors='replace') as f:
                    lines = f.read().split('\n')
                start = max(0, (p.get('line') or 1) - 1)
                end = start + p['limit'] if p.get('limit') else None
                result = {'content': '\n'.join(lines[start:end])}
            elif method == 'fs/write_text_file':
                with open(p['path'], 'w', encoding='utf-8') as f:
                    f.write(p['content'])
                result = None
            elif method == 'session/request_permission':
                result = {'outcome': pick_permission(p, self.deny_kinds)}
            else:
                self._send({'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32601, 'message': 'not supported'}})
                return
            self._send({'jsonrpc': '2.0', 'id': msg['id'], 'result': result})
        except Exception as e:  # the agent gets the error, the run goes on
            self._send({'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32000, 'message': str(e)}})

    def _new_session(self):
        params = {'cwd': self.cwd, 'mcpServers': self.mcp_servers}
        if self.system_append:  # how FriedLiver passes its rules to claude-agent-acp (hub.ts)
            params['_meta'] = {'systemPrompt': {'append': self.system_append}}
        try:
            return self.request('session/new', params)
        except RuntimeError as e:
            key = next((m for m in self.auth_methods if 'api' in (m.get('id', '') + m.get('name', '')).lower()), None)
            if not key:
                raise
            self.request('authenticate', {'methodId': key['id']})
            return self.request('session/new', params)

    def prompt(self, text):
        """Runs one turn; returns (transcript JSONL, wall seconds)."""
        import time
        with self.lock:
            self.turn = []
        if not self.session_id:
            self.session_id = self._new_session()['sessionId']
        t = time.monotonic()
        self.request('session/prompt', {'sessionId': self.session_id, 'prompt': [{'type': 'text', 'text': text}]})
        wall = time.monotonic() - t
        with self.lock:
            return '\n'.join(self.turn), wall

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
