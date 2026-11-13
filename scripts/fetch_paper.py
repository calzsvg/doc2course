#!/usr/bin/env python3
"""Bring a source document (arXiv paper, local PDF, or PDF link) into a job folder.

    ./p2v fetch <arxiv id or link>        e.g. 2610.30340, arXiv:2610.30340v2, https://arxiv.org/pdf/2610.30340, hep-th/9901001
    ./p2v fetch <path/to/file.pdf>        lecture slides, handouts, papers, reports: any PDF with a text layer
    ./p2v fetch <https://.../file.pdf>    a PDF link that is not arXiv
        options: --job <job id>           name the job yourself (letters, digits, . _ -)
                 --type slides|paper|document   override the detected document type
                 --figures own|unknown    'own': the user owns the material (or may reuse it), so its page images may appear
    python3 scripts/fetch_paper.py --id <source>   print the job id only

Creates <jobs>/<id>/ (from templates if new) and writes
    paper/meta.json   source, doc_type, title, authors, pages, license + figure_reuse, fetch time
    paper/paper.pdf   the document (the folder keeps the name "paper" for every kind of source)
    paper/paper.txt   text with '=== page N ===' markers (pdftotext -layout, else pypdfium2, else pypdf)
    paper/pages/p-001.jpg ...   one image per page (needs pypdfium2 + Pillow, installed by `p2v setup`),
                      so the agent can look at diagrams, code and equations that the text layer flattens
Job ids: arXiv id (old-style ids use '_' for '/', e.g. hep-th_9901001); local files and links use an ASCII slug of the
file name plus 6 hex digits of the file's hash ("8주차 실습.pdf" -> "8-3fa9c1"), so the same file always maps to the same job.
Respects the arXiv API terms: at most one request every 3 seconds.
"""
import hashlib, json, os, re, shutil, subprocess, sys, time, html, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2v_paths import ROOT, JOBS  # noqa: E402
UA = {'User-Agent': 'doc2video/0.2 (personal explainer videos)'}

LICENSES = {
    'creativecommons.org/licenses/by/4.0': 'CC BY 4.0',
    'creativecommons.org/licenses/by-sa/4.0': 'CC BY-SA 4.0',
    'creativecommons.org/licenses/by-nc-sa/4.0': 'CC BY-NC-SA 4.0',
    'creativecommons.org/licenses/by-nc-nd/4.0': 'CC BY-NC-ND 4.0',
    'creativecommons.org/publicdomain/zero/1.0': 'CC0 1.0',
    'arxiv.org/licenses/nonexclusive-distrib/1.0': 'arXiv non-exclusive (no reuse grant)',
}
FIGURE_REUSE = {
    'CC BY 4.0': 'allowed with attribution (note changes)',
    'CC BY-SA 4.0': 'allowed with attribution; derivatives must be CC BY-SA',
    'CC BY-NC-SA 4.0': 'non-commercial only: avoid if the video earns money',
    'CC BY-NC-ND 4.0': 'non-commercial, no modification: avoid',
    'CC0 1.0': 'allowed',
    'arXiv non-exclusive (no reuse grant)': 'NOT allowed without author permission: draw your own visuals',
}
LOCAL_REUSE = {
    'own': 'allowed: the user owns this material or may reuse it (as stated by the user); credit the source on screen',
    'unknown': 'unknown: draw your own visuals; show page images only if the user confirms they own or may reuse the material',
}
JOB_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$')

def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except Exception as e:  # HTTPError (404: no such paper), URLError (offline), timeout
        sys.exit(f'download failed: {url}: {e}')

def parse_id(s):
    """(arxiv_id, version, job_id) from an id or link, or None."""
    m = re.search(r'(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])', s)                 # 2610.35607, 2610.35607v2
    if not m: m = re.search(r'\b([a-z][a-z-]*(?:\.[A-Z]{2})?/\d{7})(v\d+)?(?![\d])', s)  # hep-th/9901001, math.GT/0309136
    if not m: return None
    return m.group(1), m.group(2) or '', m.group(1).replace('/', '_')

def source_kind(s):
    """'local' (an existing file), 'url' (a non-arXiv http(s) link), 'arxiv', or None."""
    if os.path.isfile(os.path.expanduser(s)): return 'local'
    low = s.lower()
    if low.startswith(('http://', 'https://')):
        host = urllib.parse.urlparse(s).netloc.lower()
        return 'arxiv' if host.endswith('arxiv.org') and parse_id(s) else 'url'
    if low.endswith('.pdf'): return None            # a path that does not exist
    return 'arxiv' if parse_id(s) else None

def slug_id(name, data):
    """ASCII job id from a file name plus a short content hash: stable for the same file, safe in URLs."""
    stem = os.path.splitext(os.path.basename(urllib.parse.unquote(name)))[0]
    ascii_ = unicodedata.normalize('NFKD', stem).encode('ascii', 'ignore').decode()
    slug = '-'.join(re.findall(r'[A-Za-z0-9]+', ascii_)).lower()[:40].strip('-') or 'doc'
    return f'{slug}-{hashlib.sha1(data).hexdigest()[:6]}'

def license_url(page):
    for pat in (r'<a href="([^"]+)"[^>]*class="has_license"', r'<a href="([^"]+)"[^>]*title="Rights to this article"',
                r'href="((?:https?:)?//(?:creativecommons\.org|arxiv\.org/licenses)/[^"]*)"'):
        m = re.search(pat, page)
        if m: return m.group(1)
    return ''

def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 >= len(args): sys.exit(f'{name} needs a value')
        v = args[i + 1]; del args[i:i + 2]; return v
    return default

# ---------- PDF reading (all optional imports: tests and `--id` run with the standard library only) ----------

def extract_text(pdf_path):
    if shutil.which('pdftotext'):
        r = subprocess.run(['pdftotext', '-layout', pdf_path, '-'], capture_output=True)
        if r.returncode == 0: return r.stdout.decode('utf-8', 'replace').split('\f')
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf_path)
        return [doc[i].get_textpage().get_text_range() or '' for i in range(len(doc))]
    except Exception:
        pass
    from pypdf import PdfReader
    return [pg.extract_text() or '' for pg in PdfReader(pdf_path).pages]

def pdf_info(pdf_path):
    """(pages, landscape_fraction, metadata dict) via pypdf."""
    try:
        from pypdf import PdfReader
        r = PdfReader(pdf_path)
        boxes = [p.mediabox for p in r.pages]
        land = sum(1 for b in boxes if float(b.width) > float(b.height) * 1.15) / max(1, len(boxes))
        md = r.metadata or {}
        return len(boxes), land, {'title': str(md.get('/Title') or ''), 'author': str(md.get('/Author') or ''),
                                  'date': str(md.get('/CreationDate') or '')}
    except Exception as e:
        print(f'note: could not read PDF metadata ({e.__class__.__name__})', file=sys.stderr)
        return 0, 0.0, {}

def render_pages(pdf_path, out_dir, width=1280, max_pages=400):
    """paper/pages/p-001.jpg ... Returns the number written (0 if pypdfium2/Pillow are missing)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print('note: pypdfium2 not installed (run p2v setup): no page images; read paper.pdf directly if your agent can', file=sys.stderr)
        return 0
    os.makedirs(out_dir, exist_ok=True)
    doc = pdfium.PdfDocument(pdf_path); n = min(len(doc), max_pages)
    for i in range(n):
        pg = doc[i]
        img = pg.render(scale=width / max(1.0, pg.get_width())).to_pil().convert('RGB')
        img.save(os.path.join(out_dir, f'p-{i + 1:03d}.jpg'), quality=80)
    if len(doc) > max_pages: print(f'note: only the first {max_pages} of {len(doc)} pages were rendered', file=sys.stderr)
    return n

def norm_ws(t):
    return re.sub(r'\s+', ' ', t).strip().lower()

def clean_title(t):
    t = re.sub(r'^(Microsoft (PowerPoint|Word) - )', '', t or '').strip()
    t = re.sub(r'\.(pptx?|docx?|key|pdf)$', '', t, flags=re.I).strip()
    return '' if t.lower() in ('', 'untitled', 'presentation', 'powerpoint presentation', 'slide 1') else t

def detect_type(pages_txt, landscape):
    """slides: mostly landscape pages with little text each; paper: portrait with dense text; else document."""
    n = max(1, len(pages_txt)); per_page = sum(len(t.strip()) for t in pages_txt) / n
    joined = ' '.join(pages_txt[:3]).lower()
    if landscape >= .6: return 'slides'
    if per_page > 2500 and ('abstract' in joined or 'introduction' in joined or 'references' in ' '.join(pages_txt[-4:]).lower()):
        return 'paper'
    return 'document'

def compact(pages):
    """[1, 2, 3, 7] -> '1-3, 7'"""
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1: j += 1
        out.append(str(pages[i]) if i == j else f'{pages[i]}-{pages[j]}'); i = j + 1
    return ', '.join(out)

def finish(J, P, pdf_bytes, meta):
    """Write the PDF, its text, page images and meta.json into a job; copy the job skeleton if new."""
    os.makedirs(P, exist_ok=True)   # only now: a failed download leaves no half-made job behind
    tpl = os.path.join(ROOT, 'templates', 'job')
    for f in os.listdir(tpl):
        if not os.path.exists(os.path.join(J, f)):
            shutil.copy(os.path.join(tpl, f), os.path.join(J, f))
    pdf_path = os.path.join(P, 'paper.pdf')
    with open(pdf_path, 'wb') as f: f.write(pdf_bytes)
    txt = extract_text(pdf_path)
    n_pages, land, md = pdf_info(pdf_path)
    meta['pages'] = n_pages or len(txt)
    if not meta.get('doc_type'): meta['doc_type'] = detect_type(txt, land)
    if not meta.get('title'):
        # PDF metadata titles are often stale (a deck copied from last year's lecture), so trust one only when page 1
        # shows it; otherwise use page 1's leading lines (slides: the title slide; first line is often the course name).
        p1 = [re.sub(r'\s{2,}', ' ', l.strip()) for l in (txt[0] if txt else '').splitlines() if len(l.strip()) > 3]
        mt = clean_title(md.get('title'))
        on_p1 = mt and norm_ws(mt) in norm_ws(' '.join(p1))
        first = ': '.join(p1[:3]) if meta['doc_type'] == 'slides' else (p1[0] if p1 else '')
        meta['title'] = (mt if on_p1 else '') or first[:160] or mt
    if not meta.get('authors') and md.get('author') and md['author'].strip().lower() not in ('anonymous', 'unknown', 'user', 'admin'):
        meta['authors'] = [md['author'].strip()]
    low = [i + 1 for i, t in enumerate(txt) if len(t.strip()) < 40]
    meta['low_text_pages'] = low
    with open(os.path.join(P, 'paper.txt'), 'w', encoding='utf-8') as f:
        for i, t in enumerate(txt):
            if t.strip(): f.write(f'\n=== page {i + 1} ===\n{t}')
    if low:
        print(f'NOTE: {len(low)} of {len(txt)} pages have (almost) no text layer: {compact(low)}.\n'
              f'      Transcribe them from paper/pages/p-NNN.jpg into paper/transcribed.txt ("=== page N ===" markers, '
              f'text exactly as shown). Quotes found only there are checked as REVIEW (the verifier compares them with the image).',
              file=sys.stderr)
    pages_dir = os.path.join(P, 'pages')
    shutil.rmtree(pages_dir, ignore_errors=True)
    meta['page_images'] = render_pages(pdf_path, pages_dir)
    meta['fetched_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with open(os.path.join(P, 'meta.json'), 'w', encoding='utf-8') as f: json.dump(meta, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: meta.get(k) for k in ('job', 'source', 'doc_type', 'title', 'license', 'figure_reuse')}, ensure_ascii=False, indent=1))
    print(f'pages: {meta["pages"]}  page images: {meta["page_images"]}  pdf: {len(pdf_bytes) / 1e6:.1f} MB  -> {P}')

# ---------- sources ----------

def fetch_arxiv(src, job_override=None):
    aid, ver, job = parse_id(src)
    job = job_override or job
    J = os.path.join(JOBS, job); P = os.path.join(J, 'paper')
    abs_url = f'https://arxiv.org/abs/{aid}{ver}'   # a pinned version (v2) stays pinned; otherwise the latest
    page = get(abs_url).decode('utf-8', 'replace')
    meta_tag = lambda n: [html.unescape(m) for m in re.findall(rf'<meta name="{n}" content="([^"]*)"', page)]
    lic_url = license_url(page)
    lic_name = next((v for k, v in LICENSES.items() if k in lic_url),
                    'UNKNOWN: check the abs page' if lic_url else 'none listed (older arXiv papers: default terms, no reuse grant)')
    meta = {
        'source': 'arxiv', 'doc_type': 'paper',
        'id': aid, 'version': ver or 'latest', 'job': job, 'title': (meta_tag('citation_title') or [''])[0], 'authors': meta_tag('citation_author'),
        'date': (meta_tag('citation_date') or [''])[0], 'abs_url': abs_url, 'pdf_url': f'https://arxiv.org/pdf/{aid}{ver}',
        'license_url': lic_url, 'license': lic_name, 'figure_reuse': FIGURE_REUSE.get(lic_name, 'unknown: treat as not allowed'),
    }
    time.sleep(3)
    if not meta['title']: sys.exit(f'{abs_url} has no paper metadata (wrong id?)')
    pdf = get(meta['pdf_url'])
    if not pdf.startswith(b'%PDF'): sys.exit(f'{meta["pdf_url"]} did not return a PDF (rate limit or withdrawn paper?)')
    finish(J, P, pdf, meta)

def fetch_file(src, kind, job_override=None, doc_type=None, figures='unknown'):
    if kind == 'local':
        path = os.path.abspath(os.path.expanduser(src))
        with open(path, 'rb') as f: pdf = f.read()
        name, origin = os.path.basename(path), {'file': path}
    else:
        pdf = get(src); name = urllib.parse.urlparse(src).path or 'document.pdf'; origin = {'pdf_url': src}
    if not pdf.startswith(b'%PDF'):
        sys.exit(f'{src} is not a PDF. Export slides (PowerPoint, Keynote, Google Slides) or documents to PDF first.')
    job = job_override or slug_id(name, pdf)
    J = os.path.join(JOBS, job); P = os.path.join(J, 'paper')
    meta = {'source': kind, 'doc_type': doc_type or '', 'id': job, 'job': job, 'title': '', 'authors': [], 'date': '',
            **origin, 'file_name': os.path.basename(urllib.parse.unquote(name)), 'sha256': hashlib.sha256(pdf).hexdigest(),
            'license': 'user-provided document (license not recorded)', 'figure_reuse': LOCAL_REUSE[figures]}
    finish(J, P, pdf, meta)

def job_id(src, job_override=None):
    kind = source_kind(src)
    if job_override: return job_override
    if kind == 'arxiv': return parse_id(src)[2]
    if kind == 'local':
        with open(os.path.expanduser(src), 'rb') as f: return slug_id(src, f.read())
    if kind == 'url': return None   # needs the download; `p2v run` fetches first and reads the id from the output
    return None

def main():
    args = sys.argv[1:]
    if not args: sys.exit(__doc__)
    job_override = opt(args, '--job'); doc_type = opt(args, '--type'); figures = opt(args, '--figures', 'unknown')
    if args[0] == '--id':                      # print the job id only (used by `p2v run`)
        jid = job_id(args[1], job_override) if len(args) > 1 else None
        print(jid or ''); sys.exit(0 if jid else 1)
    src = args[0]
    if job_override and not JOB_RE.match(job_override): sys.exit(f'--job {job_override!r}: use letters, digits, . _ - only')
    if doc_type and doc_type not in ('slides', 'paper', 'document'): sys.exit('--type must be slides, paper or document')
    if figures not in LOCAL_REUSE: sys.exit('--figures must be own or unknown')
    kind = source_kind(src)
    if kind is None:
        sys.exit(f'not an arXiv id or link, an existing PDF file, or a PDF link: {src}')
    if kind == 'arxiv': fetch_arxiv(src, job_override)
    else: fetch_file(src, kind, job_override, doc_type, figures)

if __name__ == '__main__':
    main()
