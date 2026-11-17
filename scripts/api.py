#!/usr/bin/env python3
"""Compact reference of the scene engine: every export of engine/core.js, engine/templates.js and engine/kit.js with
its signature and the comment above it. Read this instead of the engine source (~1,500 lines).

    p2v api              # everything
    p2v api quiz chart   # only exports whose name or comment mentions one of the words
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ['core.js', 'templates.js', 'kit.js']
EXPORT = re.compile(r'^export (?:async )?(?:function|const|let) (\w+)\s*(.*)')

def entries(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    for i, l in enumerate(lines):
        m = EXPORT.match(l)
        if not m: continue
        name, rest = m.groups()
        sig = rest.split(' {\n')[0]
        if rest.startswith('('):                      # function: keep the parameter list only
            depth, end = 0, len(rest)
            for j, ch in enumerate(rest):
                depth += ch in '({['; depth -= ch in ')}]'
                if depth == 0: end = j + 1; break
            sig = rest[:end]
        else:
            sig = rest[:110] + (' ...' if len(rest) > 110 else '')
        doc, k = [], i - 1
        while k >= 0 and lines[k].startswith('//') and len(doc) < 4:
            doc.insert(0, lines[k][2:].strip()); k -= 1
        yield name, sig, ' '.join(doc)

def main(words):
    words = [w.lower() for w in words]
    for f in FILES:
        rows = [e for e in entries(os.path.join(ROOT, 'engine', f))
                if not words or any(w in (e[0] + ' ' + e[2]).lower() for w in words)]
        if not rows: continue
        print(f'## /engine/{f}')
        for name, sig, doc in rows:
            print((f'{name}{sig}' if sig.startswith('(') else f'{name} {sig}') + (f'\n    {doc}' if doc else ''))
        print()

if __name__ == '__main__':
    main(sys.argv[1:])
