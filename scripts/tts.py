#!/usr/bin/env python3
"""Narration + timing for a job.

    ./p2v tts <job> [--engine kokoro|supertonic|silent] [--voice af_heart] [--speed 1.0] [--no-cache]
    python scripts/tts.py --download-models     (used by ./p2v setup)

Reads <jobs>/<job>/script.json and writes
    <jobs>/<job>/build/narration.wav, build/timing.json

For "lang": "ko", numbers in the spoken text are spelled out in Korean first (scripts/ko_numbers.py).

Each synthesized sentence is cached in build/tts_cache/ (keyed by engine, voice, speed, language and text), so after
editing a few sentences of a long script only those are synthesized again. --no-cache ignores the cache.

timing.json drives the video: one entry per scene with sentence start/dur, so scene
animations can key off sentence boundaries (S.P(k) in scenes.js).

Engines (picked from script.json "lang" unless tts.engine is set)
  kokoro      English (default for lang "en"). Local, Apache-2.0 weights. Voices: af_heart, am_michael, bf_emma, ...
              Models auto-download to <tools>/models/ (see scripts/p2v_paths.py).
  supertonic  Korean and 30 other languages (default for any lang other than "en"). Local ONNX, Supertonic 3,
              OpenRAIL-M weights. Voices: F1-F5, M1-M5. Model auto-downloads on first use (Hugging Face cache).
  silent      no audio; durations estimated from word count. For layout previews only.
"""
import argparse, hashlib, json, os, sys, wave, urllib.request
np = None  # imported in main(): `--download-models` must work before the venv is proven importable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2v_paths import JOBS, MODELS  # noqa: E402
from ko_numbers import spell as ko_spell  # noqa: E402
SR = 24000  # set per engine in main()
REL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
KOKORO_FILES = {  # name: (size, sha256) of the model-files-v1.0 release assets
    'kokoro-v1.0.onnx': (325532387, '7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5'),
    'voices-v1.0.bin': (28214398, 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'),
}

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def ensure_models(full_check=False):
    """Download the Kokoro files once and verify size + SHA-256. Every run checks the size; setup
    (full_check) also re-hashes existing files, so a corrupt or replaced file is downloaded again."""
    os.makedirs(MODELS, exist_ok=True)
    for name, (size, digest) in KOKORO_FILES.items():
        p = os.path.join(MODELS, name)
        if os.path.exists(p) and os.path.getsize(p) == size and (not full_check or sha256(p) == digest):
            continue
        print(f'downloading {name} ({size / 1e6:.0f} MB) ...', flush=True)
        urllib.request.urlretrieve(REL + name, p + '.part')
        if os.path.getsize(p + '.part') != size or sha256(p + '.part') != digest:
            os.remove(p + '.part'); sys.exit(f'{name}: download does not match the expected size/SHA-256; not installed')
        os.replace(p + '.part', p)

def load_kokoro():
    # phonemizer copies libespeak-ng into a temp dir before dlopen; on hardened/sandboxed macOS
    # the copy can fail library validation. Symlink to the original instead.
    try:
        import phonemizer.backend.espeak.api as _api
        _orig_copy = _api.shutil.copy
        def _copy(src, dst, follow_symlinks=True):
            try: os.symlink(os.path.abspath(src), dst); return dst
            except OSError: return _orig_copy(src, dst, follow_symlinks=follow_symlinks)
        _api.shutil.copy = _copy
    except (ImportError, AttributeError):
        pass  # phonemizer internals changed: keep its default behaviour
    from kokoro_onnx import Kokoro
    ensure_models()
    return Kokoro(os.path.join(MODELS, 'kokoro-v1.0.onnx'), os.path.join(MODELS, 'voices-v1.0.bin'))

def load_supertonic():
    from supertonic import TTS
    return TTS(auto_download=True)

def trim(x, thr=10 ** (-45 / 20)):
    idx = np.where(np.abs(x) > thr)[0]
    return x[idx[0]: idx[-1] + 1] if len(idx) else x

def main():
    if sys.argv[1:] == ['--download-models']:
        ensure_models(full_check=True); print('kokoro models ok (SHA-256 verified)'); return
    global np
    try:
        import numpy as np
    except Exception as e:
        sys.exit(f'numpy cannot be imported ({e.__class__.__name__}): run ./p2v setup, then ./p2v tts <job>')
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    ap.add_argument('--engine'); ap.add_argument('--voice'); ap.add_argument('--speed', type=float)
    ap.add_argument('--no-cache', action='store_true')
    a = ap.parse_args()
    J = os.path.join(JOBS, a.job)
    with open(os.path.join(J, 'script.json'), encoding='utf-8') as f: script = json.load(f)
    cfg = script.get('tts', {})
    global SR
    slang = (script.get('lang') or 'en').lower()
    engine = a.engine or cfg.get('engine') or ('kokoro' if slang == 'en' else 'supertonic')
    if engine == 'kokoro' and slang != 'en':
        sys.exit(f'kokoro has no "{slang}" voice; use --engine supertonic (or remove tts.engine from script.json)')
    voice = a.voice or cfg.get('voice') or ('af_heart' if engine == 'kokoro' else 'F1')
    speed = a.speed or cfg.get('speed') or (1.0 if engine == 'kokoro' else 1.05)
    lang = ('en-gb' if voice.startswith('b') else 'en-us') if engine == 'kokoro' else slang
    B = os.path.join(J, 'build'); os.makedirs(B, exist_ok=True)
    for f in ('timing.json', 'narration.wav'):
        if os.path.exists(os.path.join(B, f)): os.remove(os.path.join(B, f))
    cache_dir = os.path.join(B, 'tts_cache'); os.makedirs(cache_dir, exist_ok=True)
    # Korean: digits are read as Korean words here (500,000 -> 오십만, 3개 -> 세 개, 0 -> 영), because Supertonic
    # has no number reader of its own. script.json keeps the digits, so `p2v check` still sees the numbers.
    spoken = ko_spell if slang == 'ko' else (lambda t: t)
    texts = [spoken(t) for sc in script['scenes'] for _, t in sc['s']]
    key = lambda text: hashlib.sha1(f'{engine}|{voice}|{speed}|{lang}|{text}'.encode()).hexdigest()
    cached = lambda text: os.path.join(cache_dir, key(text) + '.npz')
    need_engine = engine != 'silent' and (a.no_cache or not all(os.path.exists(cached(t)) for t in texts))
    k = None
    if need_engine:
        k = load_kokoro() if engine == 'kokoro' else load_supertonic() if engine == 'supertonic' else None
    if engine == 'supertonic' and k is not None:
        SR = int(k.sample_rate); style = k.get_voice_style(voice_name=voice)
    if engine != 'silent' and k is None and texts:        # everything cached: the sample rate comes from the cache
        SR = int(np.load(cached(texts[0]))['sr'])
    stats = {'hit': 0, 'new': 0}

    def synth(text):
        if engine == 'silent': return synth_raw(text)
        f = cached(text)
        if not a.no_cache and os.path.exists(f):
            z = np.load(f)
            if int(z['sr']) == SR:
                stats['hit'] += 1; return z['pcm']
        x = synth_raw(text); stats['new'] += 1
        np.savez(f, pcm=x, sr=np.int32(SR))
        return x

    def synth_raw(text):
        if engine == 'kokoro':
            s, sr = k.create(text, voice=voice, speed=speed, lang=lang)
            assert sr == SR, sr
            return trim(np.asarray(s, dtype=np.float32))
        if engine == 'supertonic':
            w, _ = k.synthesize(text, voice_style=style, lang=lang, speed=speed)
            return trim(np.asarray(w, dtype=np.float32).reshape(-1))
        if engine == 'silent':
            return np.zeros(int(SR * max(1.2, len(text.split()) / 2.6 / speed)), dtype=np.float32)
        sys.exit(f'unknown engine {engine}')

    pcm = []; T = 0.0; timeline = []
    def add(x):
        nonlocal T; pcm.append(x); T += len(x) / SR
    def silence(sec): add(np.zeros(int(round(sec * SR)), dtype=np.float32))
    scenes = script['scenes']
    for si, sc in enumerate(scenes):
        lead = 1.4 if si == 0 else 0.6
        tail = 1.6 if si == 0 else (3.5 if si == len(scenes) - 1 else 0.9)
        start = T; silence(lead); sents = []
        for kk, (sub, tts) in enumerate(sc['s']):
            x = synth(spoken(tts))
            s0 = T - start; add(x)
            sents.append({'start': round(s0, 3), 'dur': round(T - start - s0, 3), 'sub': sub})
            # "pauses": {"0": 4} adds 4 s of silence after sentence 0 (thinking time for a quiz, a pause before a reveal);
            # the pause belongs to that sentence's window, so S.P(0) spans it
            extra = float((sc.get('pauses') or {}).get(str(kk), 0))
            if kk < len(sc['s']) - 1: silence(0.45 + extra)
            elif extra: silence(extra)
            print(f'  {sc["id"]}.{kk}  {len(x) / SR:5.2f}s', flush=True)
        silence(tail)
        timeline.append({'id': sc['id'], 'start': round(start, 3), 'dur': round(T - start, 3), 'sents': sents})
    audio = np.clip(np.concatenate(pcm), -1, 1)
    with wave.open(os.path.join(B, 'narration.wav'), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((audio * 32767).astype('<i2').tobytes())
    with open(os.path.join(B, 'timing.json'), 'w', encoding='utf-8') as f: json.dump(timeline, f, ensure_ascii=False, indent=1)
    if engine != 'silent': print(f'sentences: {stats["new"]} synthesized, {stats["hit"]} from cache')
    print(f'total {T:.1f}s  engine={engine}' + (f' voice={voice}' if engine != 'silent' else '') + f' lang={slang}  -> {B}/timing.json')

if __name__ == '__main__':
    main()
    # The Supertonic/onnxruntime worker threads can keep the interpreter from exiting after everything is written
    # (seen as a process spinning at 100% CPU for minutes). All output is flushed and closed here, so leave now.
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(0)
