#!/usr/bin/env python3
"""Proves the edit scenarios' success checks can fail and can pass, with no LLM: on a fresh nest
checkout S4's check must fail, then pass after a hand-written correct edit; same for S5.
    python3 checks/selfcheck.py NEST_CHECKOUT   (needs its node_modules; CI runs this for free)"""
import json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import bench  # noqa: E402

UTILS = 'packages/common/utils/shared.utils.ts'
SPEC = 'packages/common/test/utils/shared.utils.spec.ts'
S4_IMPL = "export const stripEndSlash = (path: string) => path.replace(/\\/+$/, '');"
S5_IMPL = "export const stripEndSlash = (path: string) =>\n  /^\\/+$/.test(path) ? '/' : path.replace(/\\/+$/, '');"


def edit(repo, rel, fn):
    p = os.path.join(repo, rel)
    with open(p) as f:
        text = f.read()
    new = fn(text)
    assert new != text, f'{rel}: oracle edit did not apply'
    with open(p, 'w') as f:
        f.write(new)


def impl(code):
    return lambda t: re.sub(r'export const stripEndSlash = \(path: string\) =>[\s\S]*?;\n', code + '\n', t, count=1)


def main(repo):
    cfg = bench.load_config(os.path.join(HERE, 'repos/public.json'))
    s4, s5 = (next(s for s in cfg['scenarios'] if s['id'] == i) for i in ('S4', 'S5'))
    bench.reset_repo(repo, cfg['repos']['nest'])
    results = {'S4 before edit': bench.check(s4, '', repo)}
    edit(repo, UTILS, impl(S4_IMPL))
    edit(repo, SPEC, lambda t: t.replace("expect(stripEndSlash('/cats')).to.equal('/cats');",
                                         "expect(stripEndSlash('/cats')).to.equal('/cats');\n      expect(stripEndSlash('/cats///')).to.equal('/cats');"))
    results['S4 after oracle'] = bench.check(s4, '', repo)
    results['S5 before edit'] = bench.check(s5, '', repo)
    edit(repo, UTILS, impl(S5_IMPL))
    results['S5 after oracle'] = bench.check(s5, '', repo)
    bench.reset_repo(repo, cfg['repos']['nest'])
    print(json.dumps({k: {'ok': v[0], 'detail': v[1][-300:]} for k, v in results.items()}, indent=1))
    want = {'S4 before edit': False, 'S4 after oracle': True, 'S5 before edit': False, 'S5 after oracle': True}
    if {k: v[0] for k, v in results.items()} != want:
        sys.exit('selfcheck failed: a check does not separate a wrong edit from a right one')


if __name__ == '__main__':
    main(sys.argv[1])
