"""Unit tests: parsers against the documented output shapes, cost math, chains, the private-repo
guard, success checks, and a full replay run. No keys, no network, no agents.
Run: python3 -m unittest discover -s token-bench/tests -v"""
import json, os, subprocess, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import adapters, acp, bench, context_replay, report  # noqa: E402


def jl(*objs):
    return '\n'.join(json.dumps(o) for o in objs)


class ParserTest(unittest.TestCase):
    def test_codex_doc_sample(self):
        # The turn.completed line from the Codex non-interactive docs.
        raw = jl({'type': 'thread.started', 'thread_id': 'th1'},
                 {'type': 'item.completed', 'item': {'type': 'command_execution', 'aggregated_output': 'abc'}},
                 {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'done'}},
                 {'type': 'turn.completed', 'usage': {'input_tokens': 24763, 'cached_input_tokens': 24448, 'output_tokens': 122, 'reasoning_output_tokens': 0}})
        r = adapters.parse_codex(raw)
        self.assertEqual(r['tokens'], {'input': 315, 'cache_read': 24448, 'cache_write': 0, 'output': 122, 'reasoning': 0})
        self.assertEqual((r['session_id'], r['answer'], r['tool_calls'], r['bytes_read']), ('th1', 'done', 1, 3))

    def test_antigravity_doc_envelope(self):
        # Numbers from the Antigravity CLI headless docs: total = input + output, so cache is inside input.
        raw = jl({'event': 'init', 'conversation_id': 'c1'},
                 {'event': 'step_update', 'conversation_id': 'c1', 'step_index': 2, 'state': 'DONE', 'step_type': 'tool', 'tool_info': {'output': 'hello'}},
                 {'event': 'step_update', 'conversation_id': 'c1', 'step_index': 2, 'state': 'DONE', 'step_type': 'tool', 'tool_info': {'output': 'hello'}},
                 {'event': 'result', 'conversation_id': 'c1', 'response': 'ok', 'usage': {'input_tokens': 10415, 'output_tokens': 657, 'thinking_tokens': 616, 'cache_read_tokens': 8113, 'total_tokens': 11072}})
        r = adapters.parse_antigravity(raw)
        self.assertEqual(r['tokens'], {'input': 2302, 'cache_read': 8113, 'cache_write': 0, 'output': 657, 'reasoning': 616})
        self.assertEqual(sum(r['tokens'][k] for k in ('input', 'cache_read', 'output')), 11072)
        self.assertEqual((r['tool_calls'], r['bytes_read'], r['session_id']), (1, 5, 'c1'))

    def test_cursor_forum_usage_and_missing_usage(self):
        raw = jl({'type': 'system', 'subtype': 'init', 'session_id': 's'},
                 {'type': 'tool_call', 'subtype': 'started', 'tool_call': {'readToolCall': {'args': {'path': 'a.ts'}}}},
                 {'type': 'tool_call', 'subtype': 'completed', 'tool_call': {'readToolCall': {'args': {'path': 'a.ts'}, 'result': {'success': {'content': 'x'}}}}},
                 {'type': 'result', 'result': 'ok', 'session_id': 's', 'usage': {'inputTokens': 7, 'outputTokens': 548, 'cacheReadTokens': 147695, 'cacheWriteTokens': 39331}})
        r = adapters.parse_cursor(raw)
        self.assertEqual(r['tokens']['input'] + r['tokens']['cache_read'] + r['tokens']['cache_write'], 187033)  # Cursor staff's total
        self.assertEqual((r['tool_calls'], r['files_read'], r['usage_reported']), (1, ['a.ts'], True))
        self.assertFalse(adapters.parse_cursor(jl({'type': 'result', 'result': 'ok'}))['usage_reported'])

    def test_claude_counts_each_message_once(self):
        u = {'input_tokens': 10, 'cache_creation_input_tokens': 100, 'cache_read_input_tokens': 1000, 'output_tokens': 5}
        raw = jl({'type': 'system', 'subtype': 'init', 'session_id': 'sid'},
                 {'type': 'assistant', 'message': {'id': 'm1', 'usage': u, 'content': [{'type': 'text', 'text': 'x'}]}},
                 {'type': 'assistant', 'message': {'id': 'm1', 'usage': u, 'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': 'a'}}]}},
                 {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': [{'type': 'text', 'text': 'four'}]}]}},
                 {'type': 'assistant', 'message': {'id': 'm2', 'usage': u, 'content': [{'type': 'text', 'text': 'y'}]}},
                 {'type': 'result', 'result': 'final', 'session_id': 'sid', 'total_cost_usd': 9.9})
        r = adapters.parse_claude(raw)
        self.assertEqual(r['tokens'], {'input': 20, 'cache_read': 2000, 'cache_write': 200, 'output': 10, 'reasoning': 0})
        self.assertEqual((r['answer'], r['tool_calls'], r['bytes_read'], r['files_read'], r['reported_cost_usd']), ('final', 1, 4, ['a'], 9.9))

    def test_gemini_thinking_is_output(self):
        raw = jl({'type': 'init', 'session_id': 'g'}, {'type': 'message', 'role': 'assistant', 'content': 'a'},
                 {'type': 'message', 'role': 'assistant', 'content': 'b'},
                 {'type': 'tool_result', 'output': 'xyz'},
                 {'type': 'result', 'stats': {'total_tokens': 1300, 'input_tokens': 1000, 'output_tokens': 100, 'cached': 400, 'tool_calls': 2}})
        r = adapters.parse_gemini(raw)
        self.assertEqual(r['tokens'], {'input': 600, 'cache_read': 400, 'cache_write': 0, 'output': 300, 'reasoning': 200})
        self.assertEqual((r['answer'], r['tool_calls'], r['bytes_read']), ('ab', 2, 3))

    def test_acp_usage_is_a_delta_of_the_cumulative(self):
        def turn(cum):
            return jl({'dir': 'in', 'msg': {'method': 'session/update', 'params': {'sessionId': 's', 'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'hi'}}}}},
                      {'dir': 'in', 'msg': {'method': 'session/update', 'params': {'sessionId': 's', 'update': {'sessionUpdate': 'tool_call', 'toolCallId': 't', 'kind': 'read', 'locations': [{'path': '/r/a'}]}}}},
                      {'dir': 'in', 'msg': {'method': 'session/update', 'params': {'sessionId': 's', 'update': {'sessionUpdate': 'tool_call_update', 'toolCallId': 't', 'status': 'completed', 'content': [{'type': 'content', 'content': {'type': 'text', 'text': 'abcd'}}]}}}},
                      {'dir': 'in', 'msg': {'id': 3, 'result': {'stopReason': 'end_turn', 'usage': cum}}})
        first = acp.parse_acp(turn({'inputTokens': 10, 'outputTokens': 5, 'cachedReadTokens': 100, 'totalTokens': 115}))
        second = acp.parse_acp(turn({'inputTokens': 15, 'outputTokens': 9, 'cachedReadTokens': 300, 'totalTokens': 324}), first['cumulative_usage'])
        self.assertEqual(second['tokens'], {'input': 5, 'cache_read': 200, 'cache_write': 0, 'output': 4, 'reasoning': 0})
        self.assertEqual((second['answer'], second['tool_calls'], second['bytes_read'], second['files_read']), ('hi', 1, 4, ['/r/a']))


class LogicTest(unittest.TestCase):
    def test_cost(self):
        tok = adapters._tokens(input=1_000_000, cache_read=1_000_000, cache_write=1_000_000, output=1_000_000)
        self.assertAlmostEqual(adapters.cost_usd(tok, bench.PRICES['claude-sonnet-5-5']), 2 + 0.10 + 2.5 + 10)
        self.assertIsNone(adapters.cost_usd(tok, None))

    def test_chains(self):
        sc = [{'id': 'S1'}, {'id': 'S2', 'after': 'S1'}, {'id': 'S3'}, {'id': 'S4'}, {'id': 'S5', 'after': 'S4'}]
        self.assertEqual([[s['id'] for s in c] for c in bench.chains(sc)], [['S1', 'S2'], ['S3'], ['S4', 'S5']])
        self.assertEqual([[s['id'] for s in c] for c in bench.chains(sc, {'S2', 'S3'})], [['S2'], ['S3']])

    def test_resume_flags(self):
        self.assertIn('--resume', adapters.command('claude', 'p', 'm', 'sid'))
        self.assertEqual(adapters.command('codex', 'p', 'm', 'sid')[:4], ['codex', 'exec', 'resume', 'sid'])
        self.assertEqual(adapters.command('codex', 'p', 'm')[-1], 'p')
        self.assertIn('--conversation', adapters.command('antigravity', 'p', 'm', 'c'))
        self.assertNotIn('--resume', adapters.command('gemini', 'p', 'm'))

    def test_estimate(self):
        cfg = bench.load_config(os.path.join(HERE, 'repos/public.json'))
        rows = bench.estimate(cfg, ['claude', 'codex'], 3)
        self.assertTrue(all(r['total'] > 0 and r['low'] < r['total'] < r['high'] for r in rows))


class PrivacyTest(unittest.TestCase):
    cfg = {'name': 'x', 'private': True}

    def test_private_refused_in_ci(self):
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), self.assertRaises(SystemExit):
            bench.guard_private(self.cfg, tempfile.gettempdir())

    def test_private_results_never_inside_the_repo(self):
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': '', 'CI': ''}):
            with self.assertRaises(SystemExit):
                bench.guard_private(self.cfg, os.path.join(HERE, 'results-local', 'x'))
            bench.guard_private(self.cfg, tempfile.mkdtemp())  # outside: allowed
            bench.guard_private({'name': 'p'}, os.path.join(HERE, 'x'))  # public config: anywhere

    def test_local_configs_are_gitignored(self):
        for p in ('repos/private.local.json', 'private/results.jsonl', 'results-local/a/report.html'):
            r = subprocess.run(['git', 'check-ignore', '-q', p], cwd=HERE)
            self.assertEqual(r.returncode, 0, f'{p} is not gitignored')


class CheckTest(unittest.TestCase):
    def test_answer_and_command_with_hidden_spec(self):
        d = tempfile.mkdtemp()
        subprocess.run(['git', 'init', '-q'], cwd=d)
        scn = {'check': {'answer_all': ['checker\\.ts'], 'inject': {'src': 'repos/public.json', 'dest': 'hidden.json'},
                         'cmd': 'test -f hidden.json'}}
        self.assertEqual(bench.check(scn, 'no', d)[0], False)
        self.assertEqual(bench.check(scn, 'in src/compiler/checker.ts', d), (True, 'ok'))
        self.assertFalse(os.path.exists(os.path.join(d, 'hidden.json')))  # removed after the check
        self.assertFalse(bench.check({'check': {'changed': ['a.txt']}}, '', d)[0])


class ContextReplayTest(unittest.TestCase):
    def test_trace_and_caps(self):
        d = tempfile.mkdtemp()
        subprocess.run(['git', 'init', '-q'], cwd=d)
        with open(os.path.join(d, 'lib.ts'), 'w') as f:
            f.write('export function findMe(a) {\n  return a;\n}\n' + 'const pad = 1;\n' * 3000)
        with open(os.path.join(d, 'use.ts'), 'w') as f:
            f.write('import { findMe } from "./lib";\nfindMe(1);\n')
        o = context_replay.outputs(d, 'findMe')
        self.assertEqual((o['definition_file'], o['definition_hits'], o['caller_hits']), ('lib.ts', 1, 3))
        steps = {r['tool']: r for r in context_replay.summarize(o)}
        read = o['tools']['claude-code']['read file (Read)']
        self.assertEqual(read.count('\n'), context_replay.CLAUDE_READ_LINES)  # capped at 2000 lines
        self.assertTrue(read.startswith('     1\texport function findMe'))
        self.assertLessEqual(len(o['tools']['codex']['read 250 lines (sed -n)'].encode()), context_replay.CODEX_MAX_BYTES + 64)
        self.assertEqual(set(steps), {'claude-code', 'codex', 'gemini-cli'})


class ReplayEndToEndTest(unittest.TestCase):
    def test_replay_run_and_report(self):
        out = tempfile.mkdtemp()
        arms = ['claude', 'friedliver-claude', 'cursor', 'codex', 'friedliver-codex', 'gemini', 'friedliver-gemini', 'antigravity']
        bench.main(['run', '--config', os.path.join(HERE, 'repos/public.json'), '--out', out,
                    '--replay', os.path.join(HERE, 'fixtures'), '--arms', ','.join(arms), '--reps', '2'])
        with open(os.path.join(out, 'results.jsonl')) as f:
            rows = [json.loads(l) for l in f]
        self.assertEqual(len(rows), len(arms) * 7 * 2)
        self.assertTrue(all(r['total_tokens'] > 0 and r['mode'] == 'replay' for r in rows))
        # ACP usage is cumulative per session: S2 must be the delta, smaller than S1.
        fl = {r['scenario']: r['total_tokens'] for r in rows if r['arm'] == 'friedliver-claude' and r['rep'] == 1}
        self.assertLess(fl['S2'], fl['S1'])
        bench.main(['import-manual', '--config', os.path.join(HERE, 'repos/public.json'), '--csv',
                    os.path.join(HERE, 'fixtures/manual-antigravity-ide.sample.csv'), '--out', out])
        report.main(out)
        with open(os.path.join(out, 'report.html')) as f:
            page = f.read()
        self.assertIn('SYNTHETIC FIXTURES', page)
        self.assertIn('antigravity-ide', page)


if __name__ == '__main__':
    unittest.main()
