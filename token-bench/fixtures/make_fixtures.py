#!/usr/bin/env python3
"""Writes SYNTHETIC raw outputs, one per arm and scenario, in each tool's own output format, so the
whole pipeline (parse -> records -> report) runs with no keys. The numbers are made up: they test
the plumbing, they are not measurements. Re-run after changing a format: python3 fixtures/make_fixtures.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ANSWER = ('SYNTHETIC FIXTURE ANSWER. The repo has compiler, services and server parts; '
          'isTypeAssignableTo lives in src/compiler/checker.ts; the pipeline is scanner, parser, binder, checker, emitter; '
          'Misdirected Request is 421.')
# Per scenario: (input incl. cache, output, tool calls, bytes of tool output, wall s)
BASE = {'S1': (420000, 5200, 14, 18000, 74), 'S2': (90000, 900, 1, 200, 9), 'S3': (210000, 1800, 6, 9000, 31),
        'S4': (380000, 4100, 11, 6000, 95), 'S5': (240000, 2600, 7, 3000, 52), 'S6': (360000, 4800, 10, 15000, 66),
        'S7': (110000, 700, 2, 4000, 21)}
# Arm multipliers on input, made up so the report has something to sort.
ARMS = {'claude': 1.0, 'friedliver-claude': 0.8, 'cursor': 1.1, 'codex': 0.9, 'friedliver-codex': 0.75,
        'gemini': 1.4, 'friedliver-gemini': 1.1, 'antigravity': 1.3}
FAIL = {('cursor', 'S5'), ('gemini', 'S4')}  # a couple of failures so the success column means something


def split(arm, scn):
    inp, out, calls, nbytes, wall = BASE[scn]
    inp = int(inp * ARMS[arm])
    return inp, out, calls, nbytes, wall * ARMS[arm]


def j(lines):
    return '\n'.join(json.dumps(x) for x in lines) + '\n'


def claude(arm, scn, sid):
    inp, out, calls, nbytes, _ = split(arm, scn)
    per = max(1, calls + 1)
    lines = [{'type': 'system', 'subtype': 'init', 'session_id': sid, 'model': 'claude-sonnet-5-5'}]
    for i in range(calls):
        lines.append({'type': 'assistant', 'parent_tool_use_id': None, 'message': {'id': f'msg_{scn}_{i}', 'usage': {
            'input_tokens': 40, 'cache_creation_input_tokens': int(inp * 0.08 / per), 'cache_read_input_tokens': int(inp * 0.9 / per),
            'output_tokens': out // per}, 'content': [{'type': 'tool_use', 'id': f't{i}', 'name': 'Read' if i % 2 else 'Grep',
                                                       'input': {'file_path': f'src/f{i}.ts'} if i % 2 else {'pattern': 'x'}}]}})
        lines.append({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': f't{i}', 'content': 'x' * (nbytes // calls)}]}})
    lines.append({'type': 'assistant', 'parent_tool_use_id': None, 'message': {'id': f'msg_{scn}_end', 'usage': {
        'input_tokens': 40, 'cache_creation_input_tokens': int(inp * 0.08 / per), 'cache_read_input_tokens': int(inp * 0.9 / per),
        'output_tokens': out // per}, 'content': [{'type': 'text', 'text': ANSWER}]}})
    lines.append({'type': 'result', 'subtype': 'success', 'result': ANSWER, 'session_id': sid, 'total_cost_usd': 0.1})
    return j(lines)


def codex(arm, scn, sid):
    inp, out, calls, nbytes, _ = split(arm, scn)
    lines = [{'type': 'thread.started', 'thread_id': sid}, {'type': 'turn.started'}]
    for i in range(calls):
        lines.append({'type': 'item.completed', 'item': {'id': f'item_{i}', 'type': 'command_execution', 'command': 'rg -n x',
                                                          'aggregated_output': 'y' * (nbytes // calls), 'exit_code': 0, 'status': 'completed'}})
    lines.append({'type': 'item.completed', 'item': {'id': 'item_end', 'type': 'agent_message', 'text': ANSWER}})
    lines.append({'type': 'turn.completed', 'usage': {'input_tokens': inp, 'cached_input_tokens': int(inp * 0.8),
                                                      'output_tokens': out, 'reasoning_output_tokens': out // 2}})
    return j(lines)


def gemini(arm, scn, sid):
    inp, out, calls, nbytes, _ = split(arm, scn)
    lines = [{'type': 'init', 'session_id': sid, 'model': 'gemini-3.1-pro-preview'}]
    for i in range(calls):
        lines.append({'type': 'tool_use', 'tool_name': 'read_file', 'tool_id': f't{i}', 'parameters': {'file_path': f'src/f{i}.ts'}})
        lines.append({'type': 'tool_result', 'tool_id': f't{i}', 'status': 'success', 'output': 'z' * (nbytes // calls)})
    lines.append({'type': 'message', 'role': 'assistant', 'content': ANSWER, 'delta': True})
    lines.append({'type': 'result', 'status': 'success', 'stats': {'total_tokens': inp + out * 2, 'input_tokens': inp,
                  'output_tokens': out, 'cached': int(inp * 0.5), 'input': int(inp * 0.5), 'duration_ms': 1000, 'tool_calls': calls}})
    return j(lines)


def cursor(arm, scn, sid):
    inp, out, calls, nbytes, _ = split(arm, scn)
    lines = [{'type': 'system', 'subtype': 'init', 'session_id': sid, 'model': 'sonnet-5.5', 'apiKeySource': 'env'}]
    for i in range(calls):
        lines.append({'type': 'tool_call', 'subtype': 'completed', 'call_id': f'c{i}', 'tool_call': {'readToolCall': {
            'args': {'path': f'src/f{i}.ts'}, 'result': {'success': {'content': 'w' * (nbytes // calls)}}}}})
    lines.append({'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': ANSWER}]}})
    lines.append({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': ANSWER, 'session_id': sid,
                  'usage': {'inputTokens': 60, 'outputTokens': out, 'cacheReadTokens': int(inp * 0.85), 'cacheWriteTokens': int(inp * 0.15)}})
    return j(lines)


def antigravity(arm, scn, sid):
    inp, out, calls, nbytes, _ = split(arm, scn)
    lines = [{'event': 'init', 'conversation_id': sid, 'cwd': '.', 'tools': [], 'permission_mode': 'skip'}]
    for i in range(calls):
        lines.append({'event': 'step_update', 'conversation_id': sid, 'step_index': i, 'state': 'DONE', 'step_type': 'tool',
                      'tool_name': 'view_file', 'tool_info': {'name': 'view_file', 'parameters': {}, 'output': 'v' * (nbytes // calls)}})
    lines.append({'event': 'result', 'conversation_id': sid, 'status': 'SUCCESS', 'response': ANSWER, 'num_turns': 1,
                  'usage': {'input_tokens': inp, 'output_tokens': out, 'thinking_tokens': out // 2,
                            'cache_read_tokens': int(inp * 0.6), 'total_tokens': inp + out}})
    return j(lines)


def acp(arm, scn, sid, cumulative):
    inp, out, calls, nbytes, _ = split(arm, scn)
    for k, v in (('inputTokens', int(inp * 0.05)), ('cachedReadTokens', int(inp * 0.88)),
                 ('cachedWriteTokens', int(inp * 0.07)), ('outputTokens', out)):
        cumulative[k] = cumulative.get(k, 0) + v
    cumulative['totalTokens'] = sum(cumulative[k] for k in ('inputTokens', 'cachedReadTokens', 'cachedWriteTokens', 'outputTokens'))
    upd = lambda u: {'dir': 'in', 'msg': {'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': sid, 'update': u}}}
    lines = [{'dir': 'out', 'msg': {'jsonrpc': '2.0', 'id': 3, 'method': 'session/prompt', 'params': {'sessionId': sid, 'prompt': []}}}]
    for i in range(calls):
        lines.append(upd({'sessionUpdate': 'tool_call', 'toolCallId': f'tc{i}', 'title': 'Read', 'kind': 'read',
                          'locations': [{'path': f'/repo/src/f{i}.ts'}]}))
        lines.append(upd({'sessionUpdate': 'tool_call_update', 'toolCallId': f'tc{i}', 'status': 'completed',
                          'content': [{'type': 'content', 'content': {'type': 'text', 'text': 'q' * (nbytes // calls)}}]}))
    lines.append(upd({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': ANSWER}}))
    lines.append(upd({'sessionUpdate': 'usage_update', 'used': 50000, 'size': 200000}))
    lines.append({'dir': 'in', 'msg': {'jsonrpc': '2.0', 'id': 3, 'result': {'stopReason': 'end_turn', 'usage': dict(cumulative)}}})
    return j(lines)


WRITERS = {'claude': claude, 'codex': codex, 'gemini': gemini, 'cursor': cursor, 'antigravity': antigravity}
CHAINS = [['S1', 'S2'], ['S3'], ['S4', 'S5'], ['S6'], ['S7']]


def main():
    meta = {'_note': 'SYNTHETIC. Not measurements.'}
    for arm in ARMS:
        os.makedirs(os.path.join(HERE, arm), exist_ok=True)
        meta[arm] = {}
        for chain in CHAINS:
            cumulative, sid = {}, f'synthetic-{arm}-{chain[0]}'
            for scn in chain:
                raw = acp(arm, scn, sid, cumulative) if arm.startswith('friedliver-') else WRITERS[arm](arm, scn, sid)
                with open(os.path.join(HERE, arm, f'{scn}.jsonl'), 'w') as f:
                    f.write(raw)
                meta[arm][scn] = {'success': (arm, scn) not in FAIL, 'wall_s': round(split(arm, scn)[4], 1),
                                  'detail': 'synthetic'}
    with open(os.path.join(HERE, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)


if __name__ == '__main__':
    main()
