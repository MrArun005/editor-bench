"""Unit tests for the pure logic: URL building, ref parsing, marker parsing, phases, noise verdicts,
variant arms. Run with: python3 -m unittest discover -s tests -v (no macOS tools, no network)."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stats, fetch_apps, bench  # noqa: E402


class UrlTest(unittest.TestCase):
    def test_space_in_path_is_encoded(self):
        url = 'https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/2.5.5-49/darwin-arm/Antigravity IDE.zip'
        self.assertEqual(fetch_apps.quote_url(url),
                         'https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/2.5.5-49/darwin-arm/Antigravity%20IDE.zip')

    def test_already_encoded_is_unchanged(self):
        url = 'https://x.test/a/Antigravity%20IDE.zip?sig=a%2Fb&x=1'
        self.assertEqual(fetch_apps.quote_url(url), url)

    def test_query_untouched_and_plain_url_unchanged(self):
        self.assertEqual(fetch_apps.quote_url('https://x.test/p q/f.zip?a=b c'), 'https://x.test/p%20q/f.zip?a=b c')
        self.assertEqual(fetch_apps.quote_url('https://update.code.visualstudio.com/latest/darwin-arm64/stable'),
                         'https://update.code.visualstudio.com/latest/darwin-arm64/stable')


class RefTest(unittest.TestCase):
    def test_tag(self):
        self.assertEqual(fetch_apps.parse_ref('v1.142.0-5'), ('tag', 'v1.142.0-5', None))

    def test_run_id_only_with_the_fixed_artifact(self):
        self.assertEqual(fetch_apps.parse_ref('39043981497'), ('run', '39043981497', 'friedliver-fork-macos-arm64'))
        self.assertEqual(fetch_apps.parse_ref('39043981497/friedliver-fork-macos-arm64'),
                         ('run', '39043981497', 'friedliver-fork-macos-arm64'))
        with self.assertRaises(ValueError):
            fetch_apps.parse_ref('39043981497/my-art.1')

    def test_rejects_junk(self):
        for bad in ('', 'v1;rm -rf /', '../x', '123/../../x', '--help', 'a b'):
            with self.assertRaises(ValueError, msg=bad):
                fetch_apps.parse_ref(bad)


class RunGateTest(unittest.TestCase):
    """Only artifacts of trusted Build FriedLiver runs on the upstream repo may be benchmarked (and executed)."""
    GOOD = dict(path='.github/workflows/build.yml', name='Build FriedLiver', event='push', head_branch='main',
                head_repository=dict(full_name='MrArun005/FriedLiver-Code'), repository=dict(full_name='MrArun005/FriedLiver-Code'))

    def run_with(self, **kw):
        return fetch_apps.check_run(dict(self.GOOD, **kw))

    def test_accepts_trusted_runs(self):
        for branch in ('main', 'perf/compile-cache', 'release/v1.142.0-5', 'ui/x', 'v1.142.0-5'):
            self.run_with(head_branch=branch)
        self.run_with(event='workflow_dispatch', head_branch='perf/x')

    def test_rejects_fork_runs(self):
        with self.assertRaises(ValueError):
            self.run_with(head_repository=dict(full_name='evil/FriedLiver-Code'))
        with self.assertRaises(ValueError):
            self.run_with(head_repository=None)

    def test_rejects_other_workflows_and_events(self):
        for kw in (dict(path='.github/workflows/ci.yml'), dict(path='.github/workflows/build.yml@refs/pull/1/merge'),
                   dict(name='Build FriedLiver (evil)'), dict(event='pull_request'), dict(event='pull_request_target'),
                   dict(event='workflow_run'), dict(repository=dict(full_name='evil/x'))):
            with self.assertRaises(ValueError, msg=kw):
                self.run_with(**kw)

    def test_rejects_other_branches(self):
        for branch in ('feat/x', 'perf', 'mainx', 'perf/../main', '', None, 'x/main', 'vx', 'release/'):
            with self.assertRaises(ValueError, msg=branch):
                self.run_with(head_branch=branch)


class MarkerTest(unittest.TestCase):
    def test_parse_and_offsets(self):
        text = ('code/willLoadMainBundle-code/didStartMain\t238\tcode/willLoadMainBundle-code/extHost/ready\t2950.6\t'
                'ellapsed\t1476\tcode/willLoadMainBundle-code/didStartWorkbench\t1714\n')
        m = stats.parse_markers(text)
        self.assertEqual(m['ellapsed'], 1476)
        self.assertEqual(m['code/willLoadMainBundle-code/extHost/ready'], 2951)
        off = stats.offsets(m)
        self.assertEqual(off, {'code/willLoadMainBundle': 0, 'code/didStartMain': 238,
                               'code/extHost/ready': 2951, 'code/didStartWorkbench': 1714})

    def test_empty_and_trailing_garbage(self):
        self.assertEqual(stats.parse_markers(''), {})
        self.assertEqual(stats.parse_markers('a\t1\tb\n'), {'a': 1})

    def test_marker_args_cover_phases_and_have_no_dash_in_names(self):
        for mark in stats.MARKS:
            self.assertNotIn('-', mark)
        for _, a, b in stats.PHASES:
            self.assertIn(a, stats.MARKS + [stats.START])
            self.assertIn(b, stats.MARKS)

    def test_phases(self):
        off = {stats.START: 0, 'code/didStartMain': 200, 'code/mainAppReady': 500, 'code/willOpenNewWindow': 600,
               'code/willLoadWorkbenchMain': 900, 'code/didLoadWorkbenchMain': 1300, 'code/willStartWorkbench': 1350,
               'code/didStartWorkbench': 1800}
        ph = stats.phases(off)
        self.assertEqual(ph['Process start → main started'], 200)
        self.assertEqual(ph['Workbench services, contributions, restore'], 450)
        main = [n for n, _, _ in stats.PHASES[:stats.N_MAIN_PHASES]]
        self.assertEqual(sum(ph[n] for n in main), 1800)          # main chain sums to workbench ready
        self.assertNotIn('Extension host ready (from process start)', ph)   # missing mark -> no phase


class LogTest(unittest.TestCase):
    def test_slow_contribs(self):
        log = ("2026-10-17 10:00:00.000 [warning] Creation of workbench contribution 'workbench.contrib.chat' took 45ms.\n"
               "2026-10-17 10:00:00.100 [info] something else\n"
               "2026-10-17 10:00:00.200 [warning] Creation of workbench contribution 'a.b' took 120ms.\n")
        self.assertEqual(stats.slow_contribs(log), [('a.b', 120), ('workbench.contrib.chat', 45)])


class CompileCacheLogTest(unittest.TestCase):
    def test_cache_lines(self):
        log = ("2026-10-18 01:00:00.000 [info] [node-compile-cache] extension-host: packaged cache inactive "
               "(status: enabled, configured: /u/CachedData/abc/node/extension-host, active: /u/CachedData/abc/node/extension-host)\n"
               "2026-10-18 01:00:00.100 [info] unrelated\n")
        self.assertEqual(stats.cache_lines(log), ['[node-compile-cache] extension-host: packaged cache inactive '
                         '(status: enabled, configured: /u/CachedData/abc/node/extension-host, active: /u/CachedData/abc/node/extension-host)'])
        self.assertEqual(stats.cache_lines('nothing here'), [])


class CompareTest(unittest.TestCase):
    def test_beyond_noise(self):
        c = stats.compare([2800, 2820, 2840], [2500, 2510, 2520], 'ms')
        self.assertEqual(c['delta'], -310)
        self.assertEqual(c['verdict'], 'better')

    def test_within_spread_is_noise(self):
        self.assertEqual(stats.compare([2800, 2500, 3100], [2700, 2710, 2720], 'ms')['verdict'], 'noise')

    def test_floor(self):
        self.assertEqual(stats.compare([1000], [1020], 'ms')['verdict'], 'noise')      # 2 % < 3 % floor
        self.assertEqual(stats.compare([500], [508], 'mb')['verdict'], 'noise')        # < 10 MB
        self.assertEqual(stats.compare([500], [520], 'mb')['verdict'], 'worse')
        self.assertEqual(stats.compare([3.0], [3.5], 'pct')['verdict'], 'noise')       # < 1 point
        self.assertEqual(stats.compare([3.0, 3.1], [5.0, 5.2], 'pct')['verdict'], 'worse')

    def test_empty(self):
        self.assertIsNone(stats.compare([], [1], 'ms'))

    def test_p90_nearest_rank(self):
        self.assertEqual(stats.p90([5, 1, 4, 2, 3]), 5)
        self.assertEqual(stats.p90(list(range(1, 11))), 9)


class ArmsTest(unittest.TestCase):
    BASE = [dict(id='friedliver', label='FriedLiver', path='/a', vscode=True),
            dict(id='vscode', label='VS Code', path='/b', vscode=True)]

    def test_variant_arm(self):
        arms = bench.make_arms(self.BASE, {'vscode', 'friedliver'}, ['friedliver+settings-perf'])
        self.assertEqual([a['id'] for a in arms], ['friedliver', 'vscode', 'friedliver+settings-perf'])
        v = arms[-1]
        self.assertEqual((v['path'], v['base'], v['label']), ('/a', 'friedliver', 'FriedLiver + settings-perf'))
        self.assertEqual(v['settings']['workbench.startupEditor'], 'none')
        self.assertTrue(v['settings']['extensions.experimental.deferredStartupFinishedActivation'])

    def test_variant_without_its_base_arm_still_runs_and_bad_names_fail(self):
        arms = bench.make_arms(self.BASE, {'vscode'}, ['friedliver+settings-perf'])
        self.assertEqual([a['id'] for a in arms], ['vscode', 'friedliver+settings-perf'])
        self.assertEqual(bench.make_arms(self.BASE, {'vscode'}, ['cursor+settings-perf']), [self.BASE[1]])  # base not fetched
        with self.assertRaises(SystemExit):
            bench.make_arms(self.BASE, set(), ['friedliver+nope'])

    def test_all_apps_when_selection_empty(self):
        self.assertEqual(len(bench.make_arms(self.BASE, set(), [])), 2)

    def test_split_list(self):
        self.assertEqual(stats.split_list('a, b,,c'), ['a', 'b', 'c'])
        self.assertEqual(stats.split_list('none'), [])
        self.assertEqual(stats.split_list('all', ['x', 'y']), ['x', 'y'])
        self.assertEqual(stats.split_list('', ['x']), ['x'])


if __name__ == '__main__':
    unittest.main()
