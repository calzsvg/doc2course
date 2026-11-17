#!/usr/bin/env python3
"""What a verification round has to look at (used by `p2v verify`; standard library only).

    python3 scripts/verify_scope.py <job> [--scenes a,b,c] [--full] [--out VERIFY.md]

Round 1 (or --full, or when the last round left no finished report) is a full verification. Every later round is a
re-check: the previous report is archived to build/verify_rounds/ and copied to the output file as the starting point,
and build/verify_delta.md lists only what the verifier has to look at again:
  * the previous round's findings that were not `ok` (each must be re-checked)
  * scenes whose script.json entry changed, that are new, that use a changed claim, or whose scene file changed
  * the claims, script sentences and preview sheets of those scenes
Unchanged scenes keep their rows from the previous report. The snapshot of this round is stored in
build/verify_state.json (per scope), so the next round compares against what this verifier saw.
Prints a JSON summary: {round, mode, out, previous, delta, changed_scenes, sheets}.
"""
import argparse, hashlib, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2v_paths import JOBS  # noqa: E402

h = lambda o: hashlib.sha1(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
snap_src = [{}]   # scene source of the current snapshot (not stored in the state file)
DEF = re.compile(r'^export\s+(?:const|let|function|async\s+function)\s+(\w+)', re.M)

def snapshot(J, scope_ids):
    script = json.load(open(os.path.join(J, 'script.json'), encoding='utf-8'))
    try: claims = json.load(open(os.path.join(J, 'claims.json'), encoding='utf-8'))
    except FileNotFoundError: claims = {}
    scenes = {s['id']: h(s) for s in script['scenes'] if not scope_ids or s['id'] in scope_ids}
    cl = claims.get('claims', claims if isinstance(claims, list) else [])
    claim_h = {c.get('id', str(i)): h(c) for i, c in enumerate(cl)}
    used = {}
    for i, c in enumerate(cl):
        for u in c.get('used_in', []) or []:
            used.setdefault(str(u).split('.')[0], []).append(c.get('id', str(i)))
    # Each scene factory's source (from its `export` to the next one) is hashed on its own, so editing one scene does
    # not mark the whole file as changed. Everything else in a file (imports, helpers) is that file's shared part.
    files, defines, blocks, helpers, srcs, imports = {}, {}, {}, {}, {}, {}
    for f in sorted(os.listdir(J)):
        if f.endswith(('.js', '.mjs')):
            src = open(os.path.join(J, f), encoding='utf-8').read()
            ms = list(DEF.finditer(src))
            defines[f] = [m.group(1) for m in ms]
            imports[f] = re.findall(r"from\s+['\"]\./([\w.-]+)['\"]", src)
            for i, m in enumerate(ms):
                body = src[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(src)]
                if m.group(1) in scenes: blocks[m.group(1)] = h(body); srcs[m.group(1)] = body
                else: helpers[m.group(1)] = h(body)              # exported helper (box, chap, CH ...)
            files[f] = h(src[:ms[0].start()] if ms else src)     # imports and private code before the first export
    snap_src[0] = srcs
    return {'scenes': scenes, 'claims': claim_h, 'used': used, 'files': files, 'defines': defines, 'blocks': blocks, 'helpers': helpers, 'imports': imports,
            'allow': h(claims.get('allow_numbers', {})) if isinstance(claims, dict) else ''}, script, cl

def open_findings(report):
    """Table rows of a VERIFY.md whose verdict is not ok (the rows the next round must re-check)."""
    rows = []
    for line in open(report, encoding='utf-8'):
        if line.startswith('|') and not re.match(r'^\|\s*-', line):
            cells = [c.strip().lower() for c in line.strip().strip('|').split('|')]
            if 'verdict' in cells: continue                  # header row
            if len(cells) >= 3 and not any(c in ('ok', 'pass', 'carried over') or c.startswith('ok ') for c in cells[1:4]):
                rows.append(line.rstrip())
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job'); ap.add_argument('--scenes', default=''); ap.add_argument('--full', action='store_true')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    J = os.path.join(JOBS, a.job); B = os.path.join(J, 'build'); os.makedirs(B, exist_ok=True)
    ids = [x.strip() for x in a.scenes.split(',') if x.strip()]
    key = ids[0] if ids else 'all'
    out = a.out or (f'VERIFY_{key}.md' if ids else 'VERIFY.md')
    state_f = os.path.join(B, 'verify_state.json')
    try: state = json.load(open(state_f, encoding='utf-8'))
    except (FileNotFoundError, ValueError): state = {}
    prev = state.get(key)
    snap, script, claims = snapshot(J, ids)
    rnd = (prev or {}).get('round', 0) + 1
    report = os.path.join(J, out)
    finished = os.path.exists(report) and re.search(r'overall:\s*(PASS|FIX-AND-RERUN|BLOCKED)', open(report, encoding='utf-8').read())
    mode = 'full' if a.full or not prev or not finished else 'recheck'
    summary = {'round': rnd, 'mode': mode, 'out': out, 'previous': None, 'delta': None, 'changed_scenes': [], 'sheets': []}

    if mode == 'recheck':
        arch = os.path.join(B, 'verify_rounds'); os.makedirs(arch, exist_ok=True)
        previous = os.path.join(arch, f'{out[:-3]}_round{rnd - 1}.md')
        shutil.copyfile(report, previous)                    # the report stays in place as the starting point
        old = prev['snap']
        changed_claims = {c for c, v in snap['claims'].items() if old['claims'].get(c) != v}
        changed_files = {f for f, v in snap['files'].items() if old['files'].get(f) != v}
        scene_file = {n: f for f, names in snap['defines'].items() for n in names if n in snap['scenes']}
        # a changed preamble reaches every file that imports it (directly or through re-exports)
        reach, grew = set(changed_files), True
        while grew:
            grew = False
            for f, imps in snap['imports'].items():
                if f not in reach and reach & set(imps): reach.add(f); grew = True
        shared = sorted(changed_files)
        changed_helpers = [n for n, v in snap['helpers'].items() if old.get('helpers', {}).get(n) != v]
        uses = lambda s: any(re.search(r'\b%s\b' % re.escape(n), snap_src[0].get(s, '')) for n in changed_helpers)
        changed = [s for s in snap['scenes'] if old['scenes'].get(s) != snap['scenes'][s]
                   or changed_claims & set(snap['used'].get(s, []))
                   or old.get('blocks', {}).get(s) != snap['blocks'].get(s)
                   or scene_file.get(s) in reach or uses(s)]
        findings = open_findings(previous)
        idx = {}
        try: idx = json.load(open(os.path.join(B, 'preview_index.json'), encoding='utf-8'))
        except (FileNotFoundError, ValueError): pass
        look = set(changed)
        sheets = sorted(f for f, sc in idx.items() if look & set(sc))
        by_id = {s['id']: s for s in script['scenes']}
        cl_by = {c.get('id', str(i)): c for i, c in enumerate(claims)}
        lines = [f'# Re-check, round {rnd} (previous report: build/verify_rounds/{os.path.basename(previous)})', '',
                 f'Open findings from round {rnd - 1} (re-check every one; fixed -> `ok (fixed in round {rnd})`):', '']
        lines += findings or ['(none)']
        lines += ['', f'Changed scenes ({len(changed)}): ' + (', '.join(changed) or 'none')]
        if shared: lines += [f'Imports or private code changed in: {", ".join(shared)} (scenes in files that use it are listed as changed).']
        if changed_helpers: lines += [f'Changed helpers: {", ".join(changed_helpers)} (scenes that call them are listed as changed).']
        if snap['allow'] != old.get('allow'): lines += ['claims.json allow_numbers changed: check every new entry\'s reason.']
        lines += [f'Preview sheets to open: {", ".join(sheets) or "none (no build/preview_index.json: open the sheets of the changed scenes)"}', '']
        for s in changed:
            lines += [f'## scene {s}' + (f' ({scene_file[s]})' if s in scene_file else ''), '```json',
                      json.dumps(by_id[s], ensure_ascii=False, indent=1), '```']
            cs = [cl_by[c] for c in snap['used'].get(s, []) if c in cl_by]
            if cs: lines += ['claims used here:', '```json', json.dumps(cs, ensure_ascii=False, indent=1), '```']
        delta = os.path.join(B, 'verify_delta.md')
        open(delta, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
        summary.update(previous=os.path.relpath(previous, J), delta=os.path.relpath(delta, J), changed_scenes=changed, sheets=sheets)

    state[key] = {'round': rnd, 'snap': snap}
    json.dump(state, open(state_f, 'w', encoding='utf-8'), ensure_ascii=False)
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == '__main__':
    main()
