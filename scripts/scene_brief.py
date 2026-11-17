#!/usr/bin/env python3
"""Everything a scene writer needs for one chapter, in one small file (used by `p2v scenes`; standard library only).

    python3 scripts/scene_brief.py <job> --scenes a,b,c --file scenes_x.js

Writes build/scene_brief_<file stem>.md: the script entries of those scenes (sentences, pauses), the claims they use
(with on-screen labels), the BRIEF.md lines that mention them, the job's shared helper exports and the sentence
timing if `p2v tts` has run. The writer reads this instead of the whole script.json, claims.json and BRIEF.md.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2v_paths import JOBS  # noqa: E402

def helper_exports(src):
    """Names a job helper file exports: its own definitions and re-exports (`export { a, b as c } from '...'`,
    `export * from '...'` shown as `* from ...`)."""
    names = re.findall(r'^export\s+(?:const|let|var|class|function\*?|async\s+function)\s+(\w+)', src, re.M)
    for block in re.findall(r'^export\s*\{([^}]*)\}', src, re.M):
        names += [p.split(' as ')[-1].strip() for p in block.split(',') if p.strip()]
    names += [f'* from {m}' for m in re.findall(r'^export\s*\*\s*from\s*[\'"]([^\'"]+)', src, re.M)]
    return list(dict.fromkeys(names))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job'); ap.add_argument('--scenes', required=True); ap.add_argument('--file', required=True)
    a = ap.parse_args()
    J = os.path.join(JOBS, a.job)
    ids = [x.strip() for x in a.scenes.split(',') if x.strip()]
    script = json.load(open(os.path.join(J, 'script.json'), encoding='utf-8'))
    by_id = {s['id']: s for s in script['scenes']}
    missing = [i for i in ids if i not in by_id]
    if missing: sys.exit(f'scene_brief: no such scene(s) in script.json: {", ".join(missing)}')
    try: claims = json.load(open(os.path.join(J, 'claims.json'), encoding='utf-8')).get('claims', [])
    except FileNotFoundError: claims = []
    timing = {}
    try: timing = {t['id']: t for t in json.load(open(os.path.join(J, 'build', 'timing.json'), encoding='utf-8'))}
    except FileNotFoundError: pass
    out = [f'# Scene brief: {", ".join(ids)} -> {a.file}', '',
           f'Video: {script.get("title", "")} (lang {script.get("lang", "en")}). Write one exported factory per scene id below.', '']
    brief = os.path.join(J, 'BRIEF.md')
    if os.path.exists(brief):
        pat = re.compile(r'\b(' + '|'.join(map(re.escape, ids)) + r')\b')
        lines = [l.rstrip() for l in open(brief, encoding='utf-8') if pat.search(l)]
        if lines: out += ['## BRIEF.md lines for these scenes', *lines, '']
    shared = []
    for f in sorted(os.listdir(J)):
        if f.endswith('.js') and f != a.file and not f.startswith('scenes'):
            names = helper_exports(open(os.path.join(J, f), encoding='utf-8').read())
            if names: shared.append(f'- ./{f}: {", ".join(names)}')
    if shared: out += ['## Job helpers you can import (do not edit these files)', *shared, '']
    for i in ids:
        s = by_id[i]
        out += [f'## {i}' + (f'  (chapter starts: {s["chapter"]})' if s.get('chapter') else '')]
        t = timing.get(i)
        for k, sent in enumerate(s['s']):
            when = f' [{t["sents"][k]["start"]:.1f}s, {t["sents"][k]["dur"]:.1f}s]' if t and k < len(t['sents']) else ''
            out.append(f'- S.P({k}){when}: {sent[0]}')
        if s.get('pauses'): out.append(f'- pauses: {json.dumps(s["pauses"])}')
        if t: out.append(f'- scene length {t["dur"]:.1f}s')
        used = [c for c in claims if any(str(u).split('.')[0] == i for u in c.get('used_in', []) or [])]
        for c in used:
            keep = {k: v for k, v in c.items() if k in ('id', 'kind', 'text', 'values', 'on_screen_label', 'table', 'row', 'page')}
            out.append(f'  - claim {json.dumps(keep, ensure_ascii=False)}')
        out.append('')
    os.makedirs(os.path.join(J, 'build'), exist_ok=True)
    dst = os.path.join(J, 'build', f'scene_brief_{os.path.splitext(a.file)[0]}.md')
    open(dst, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(dst)

if __name__ == '__main__':
    main()
