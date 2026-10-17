#!/usr/bin/env python3
"""Download every app under test from its official source into <scratch>/apps, verify it, and
write <scratch>/apps.json ({id: app path}) for bench.py plus results/fetch.json (provenance).

Verification policy: a published hash is checked when the vendor publishes one; codesign -v must
pass; spctl (Gatekeeper/notarization) must pass for vendor builds. FriedLiver release builds are
ad-hoc signed, so for it the release's SHA256SUMS.txt is the integrity check and the spctl
rejection is recorded, not fatal. An app that fails verification is skipped, never run.
"""
import base64, glob, hashlib, json, os, re, shutil, subprocess, sys, urllib.parse, urllib.request

import stats

SCRATCH = APPS = DL = None   # set in main()
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
FL_REPO = 'MrArun005/FriedLiver-Code'
FL_ARTIFACT = 'friedliver-fork-macos-arm64'

def quote_url(url):
    """Percent-encode the path (vendors hand out paths with spaces, e.g. "Antigravity IDE.zip").
    Unquote first so an already-encoded URL is unchanged; the query is left as given."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(p._replace(path=urllib.parse.quote(urllib.parse.unquote(p.path))))

def parse_ref(ref):
    """friedliver_ref input -> ('tag', tag, None) | ('run', run_id, artifact name). Validated: it reaches gh."""
    m = re.fullmatch(r'(\d+)(?:/([A-Za-z0-9][\w.-]*))?', ref)
    if m:
        return 'run', m[1], m[2] or FL_ARTIFACT
    if re.fullmatch(r'[A-Za-z0-9][\w.+-]*', ref):
        return 'tag', ref, None
    raise ValueError(f'friedliver_ref must be a release tag or <run id>[/<artifact>], got {ref!r}')

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'editor-bench'})
    return urllib.request.urlopen(req, timeout=60).read()

def download(url, name):
    path = os.path.join(DL, name)
    subprocess.run(['curl', '-fsSL', '--retry', '3', '-o', path, quote_url(url)], check=True)
    return path

def digest(path, algo):
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h

def extract(archive, dest_id):
    dest = os.path.join(APPS, dest_id)
    os.makedirs(dest, exist_ok=True)
    if archive.endswith('.dmg'):
        mnt = os.path.join(DL, dest_id + '-mnt')
        subprocess.run(['hdiutil', 'attach', '-nobrowse', '-readonly', '-noautoopen', '-mountpoint', mnt, archive],
                       check=True, capture_output=True)
        try:
            app = glob.glob(os.path.join(mnt, '*.app'))[0]
            subprocess.run(['ditto', app, os.path.join(dest, os.path.basename(app))], check=True)
        finally:
            subprocess.run(['hdiutil', 'detach', mnt, '-force'], capture_output=True)
    else:
        subprocess.run(['ditto', '-x', '-k', archive, dest], check=True)
    os.remove(archive)
    return glob.glob(os.path.join(dest, '*.app'))[0]

def yml_field(text, key):
    m = re.search(rf'^\s*-?\s*{key}:\s*(\S+)', text, re.M)
    return m and m.group(1).strip('\'"')

# --- per-vendor resolvers: return (url, archive name, expected hash or None, version) -------------

def vscode():
    return 'https://update.code.visualstudio.com/latest/darwin-arm64/stable', 'vscode.zip', None, None

def cursor():
    return ('https://api2.cursor.sh/updates/download/golden/darwin-arm64/cursor/latest', 'cursor.dmg', None, None)

def antigravity_ide():
    d = json.loads(get('https://antigravity-ide-auto-updater-974169037036.us-central1.run.app/api/update/darwin-arm64/stable/latest'))
    return d['url'], 'antigravity-ide.zip', ('sha256', d['sha256hash']), d.get('productVersion')

def antigravity():
    y = get('https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/manifest/latest-arm64-mac.yml').decode()
    sha = base64.b64decode(yml_field(y, 'sha512')).hex()
    return yml_field(y, 'url'), 'antigravity.zip', ('sha512', sha), yml_field(y, 'version')

def opencode():
    base = 'https://github.com/anomalyco/opencode/releases/latest/download/'
    y = get(base + 'latest-mac.yml').decode()
    files = re.findall(r'- url:\s*(\S+)\s*\n\s*sha512:\s*(\S+)', y)
    url, sha = next((u, s) for u, s in files if u.endswith('arm64.zip'))
    return base + url, 'opencode.zip', ('sha512', base64.b64decode(sha).hex()), yml_field(y, 'version')

def friedliver(tag=None, sub='fl'):
    """A FriedLiver release (latest, or `tag`): the DMG, checked against the release's SHA256SUMS.txt."""
    out = os.path.join(DL, sub)
    os.makedirs(out, exist_ok=True)
    subprocess.run(['gh', 'release', 'download', *([tag] if tag else []), '-R', FL_REPO, '--clobber', '-D', out,
                    '-p', 'FriedLiver-darwin-arm64-*.dmg', '-p', 'SHA256SUMS.txt'], check=True)
    dmg = glob.glob(os.path.join(out, '*.dmg'))[0]
    sums = open(os.path.join(out, 'SHA256SUMS.txt')).read()
    want = next(l.split()[0] for l in sums.splitlines() if l.strip().endswith(os.path.basename(dmg)))
    tag = json.loads(subprocess.run(['gh', 'release', 'view', *([tag] if tag else []), '-R', FL_REPO, '--json', 'tagName'],
                                    capture_output=True, text=True, check=True).stdout)['tagName']
    return 'file://' + dmg, 'friedliver.dmg', ('sha256', want), tag

def friedliver_patched():
    """FRIEDLIVER_REF: a release tag, or a Build FriedLiver run id (+ artifact name). A run artifact is
    checked against the artifact digest GitHub records at upload; its inner zip holds the .app."""
    kind, ref, artifact = parse_ref(os.environ['FRIEDLIVER_REF'])
    if kind == 'tag':
        url, name, want, version = friedliver(ref, 'flp')
        return url, 'friedliver-patched.dmg', want, version
    arts = json.loads(subprocess.run(['gh', 'api', f'repos/{FL_REPO}/actions/runs/{ref}/artifacts?per_page=100'],
                                     capture_output=True, text=True, check=True).stdout)['artifacts']
    art = next(a for a in arts if a['name'] == artifact)
    if art.get('expired') or not (art.get('digest') or '').startswith('sha256:'):
        raise RuntimeError(f'artifact {artifact} of run {ref} is expired or has no digest')
    outer = os.path.join(DL, 'flp-artifact.zip')
    with open(outer, 'wb') as f:
        subprocess.run(['gh', 'api', f'repos/{FL_REPO}/actions/artifacts/{art["id"]}/zip'], stdout=f, check=True)
    got = digest(outer, 'sha256').hexdigest()
    if got != art['digest'][7:]:
        raise RuntimeError(f'artifact digest MISMATCH {got} != {art["digest"]}')
    inner_dir = os.path.join(DL, 'flp-inner')
    subprocess.run(['ditto', '-x', '-k', outer, inner_dir], check=True)
    inner = glob.glob(os.path.join(inner_dir, '*.zip'))[0]
    run = json.loads(subprocess.run(['gh', 'api', f'repos/{FL_REPO}/actions/runs/{ref}', '--jq', '{sha: .head_sha, branch: .head_branch}'],
                                    capture_output=True, text=True, check=True).stdout)
    return ('file://' + inner, 'friedliver-patched.zip', ('verified', 'artifact sha256 digest verified'),
            f"run {ref}: {run['branch']}@{run['sha'][:10]}")

RESOLVERS = [('friedliver', friedliver, False), ('cursor', cursor, True), ('antigravity-ide', antigravity_ide, True),
             ('vscode', vscode, True), ('antigravity', antigravity, True), ('opencode', opencode, True)]

def wanted():
    """App ids to fetch: the selected apps (all if none), the bases of selected variants, and the patched
    build when FRIEDLIVER_REF is set."""
    ids = set(stats.split_list(os.environ.get('BENCH_ONLY', ''), [r[0] for r in RESOLVERS]))
    ids |= {v.split('+')[0] for v in stats.split_list(os.environ.get('BENCH_VARIANTS', 'none'))}
    if os.environ.get('FRIEDLIVER_REF'):
        ids.add('friedliver-patched')
    return ids

def main():
    global SCRATCH, APPS, DL
    SCRATCH = sys.argv[1]
    APPS, DL = os.path.join(SCRATCH, 'apps'), os.path.join(SCRATCH, 'dl')
    for d in (APPS, DL, RES):
        os.makedirs(d, exist_ok=True)
    apps, report, want_ids = {}, {}, wanted()
    for app_id, resolve, need_notarized in RESOLVERS + [('friedliver-patched', friedliver_patched, False)]:
        if app_id not in want_ids:
            continue
        rec = report[app_id] = {}
        try:
            url, name, want, version = resolve()
            local = url.startswith('file://')
            rec.update(source=f'gh {FL_REPO} ' + (os.environ.get('FRIEDLIVER_REF') or 'latest release')
                       if local and app_id == 'friedliver-patched' else f'gh release {FL_REPO}' if local else url,
                       version=version)
            archive = url[7:] if local else download(url, name)
            if want and want[0] == 'verified':          # the resolver checked it (run artifact digest)
                rec['hash'] = want[1]
            elif want:
                got = digest(archive, want[0]).hexdigest()
                rec['hash'] = f'{want[0]} ' + ('verified' if got == want[1] else f'MISMATCH {got} != {want[1]}')
                if got != want[1]:
                    raise RuntimeError('hash mismatch')
            else:
                rec['hash'] = 'vendor publishes no hash'
            app = extract(archive, app_id)
            cs = subprocess.run(['codesign', '-v', '--deep', '--strict', app], capture_output=True, text=True)
            sp = subprocess.run(['spctl', '-a', '-vv', app], capture_output=True, text=True)
            rec['codesign'] = 'valid' if cs.returncode == 0 else 'INVALID: ' + cs.stderr.strip()[:200]
            rec['spctl'] = sp.stderr.strip().replace(app, '<app>')[:200]
            if cs.returncode != 0 or (need_notarized and sp.returncode != 0):
                raise RuntimeError('signature verification failed')
            apps[app_id] = app
            rec['status'] = 'ok'
        except Exception as e:  # one vendor being down must not sink the whole run
            rec['status'] = f'skipped: {e}'
        print(app_id, rec, flush=True)

    shutil.rmtree(DL, ignore_errors=True)
    json.dump(apps, open(os.path.join(SCRATCH, 'apps.json'), 'w'), indent=2)
    json.dump(report, open(os.path.join(RES, 'fetch.json'), 'w'), indent=2)
    if not apps:
        sys.exit('no app could be fetched and verified')

if __name__ == '__main__':
    main()
