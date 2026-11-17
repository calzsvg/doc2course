#!/usr/bin/env python3
"""Read the digits in Korean narration as Korean words before they reach the TTS engine.

Supertonic has no number reader: it gets "500,000" or "3개" as raw characters and guesses ("오백천", "셋개", "염").
spell() rewrites them the way a Korean speaker reads them aloud (standard library only):

    500,000 -> 오십만        3개 -> 세 개         0이면 -> 영이면       1번째 -> 첫 번째
    16비트 -> 십육비트       3.14 -> 삼 점 일사    50% -> 오십 퍼센트    -3 -> 마이너스 삼
    1~3 -> 일에서 삼        2^10 -> 이의 십 제곱  1/4 -> 사 분의 일     0010 -> 영 영 일 영 (leading zero: digit by digit)

Sino-Korean (일, 이, 삼) is the default. Native numbers (한, 두, 세) are used for 1-99 before a native counter
(개, 명, 가지, 번째, 시간, 마리 ...). Numbers glued to a Latin letter on the left (x86, R3, LC3) are left alone:
they are names, and the script writer spells them out ("엘씨 쓰리"). Anything else that should be read differently
(e.g. "세 번 반복" vs "3번 레지스터") can simply be written in Hangul in the spoken text.

    python3 scripts/ko_numbers.py "레지스터 3개, 500,000번 반복"     # prints the spoken form
"""
import re, sys

_D = '영일이삼사오육칠팔구'
_UNITS4 = ['', '만', '억', '조', '경']

def sino(n):
    """Sino-Korean reading of a non-negative integer: 0 -> 영, 10 -> 십, 500000 -> 오십만, 100000000 -> 일억."""
    if n == 0:
        return '영'
    out, g = [], 0
    while n:
        n, part = divmod(n, 10000)
        if part:
            s = ''
            for i, u in ((3, '천'), (2, '백'), (1, '십')):
                d = part // 10 ** i % 10
                if d: s += ('' if d == 1 else _D[d]) + u
            if part % 10: s += _D[part % 10]
            if g == 1 and part == 1: s = ''          # 10000 is 만, not 일만
            out.append(s + _UNITS4[g])
        g += 1
    return ''.join(reversed(out))

_NATIVE_ONES = ['', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉']
_NATIVE_TENS = ['', '열', '스물', '서른', '마흔', '쉰', '예순', '일흔', '여든', '아흔']

def native(n):
    """Native-Korean counting form for 1-99 (the form used before a counter): 3 -> 세, 20 -> 스무, 21 -> 스물한."""
    t, o = divmod(n, 10)
    if n == 20: return '스무'
    return _NATIVE_TENS[t] + _NATIVE_ONES[o]

# Counters read with native numbers. Longest first; "장" (chapter 3 = 삼 장), "권", "대", "번" (register 5 = 오 번)
# are left Sino because lecture and paper text mostly uses them as labels, not counts.
_NATIVE_COUNTERS = sorted([
    '개', '명', '가지', '번째', '시간', '시', '살', '마리', '달', '군데', '차례', '바퀴', '쌍', '자리', '글자', '칸', '줄',
    '사람', '묶음', '걸음', '단어', '문장', '그루', '송이', '켤레', '벌', '잔', '통',
], key=len, reverse=True)
# Words starting with a native counter that are Sino counters themselves (3개월 = 삼 개월, 3시그마 = 삼 시그마).
_SINO_EXCEPT = ('개월', '개국', '개년', '시그마', '시점', '시스템', '시도', '시퀀스', '시프트', '자리수', '통신', '달러', '줄기')
# "번" counts repetitions only in these phrasings: 3번 반복, 2번씩, 한 번 더, 10번 연속, 5번 정도.
_BEON_COUNT = re.compile(r'번\s?(?:반복|더\b|씩|연속|정도|만에|이상|이하|쯤|미만|째)')

_NUM = re.compile(
    r'(?P<neg>-)?'                                      # spell() only lets a minus through at a word start
    r'(?P<int>\d{1,3}(?:,\d{3})+(?!\d)|\d+)'            # 500,000 or 500000
    r'(?:\.(?P<frac>\d+))?'                             # 3.14
)

def _reading(m, after):
    i, frac = m.group('int'), m.group('frac')
    n = int(i.replace(',', ''))
    if len(i) > 1 and i[0] == '0' and ',' not in i and frac is None:
        return ' '.join(_D[int(c)] for c in i)          # 0010, 007: digit by digit
    if frac is not None:
        s = sino(n) + ' 점 ' + ''.join(_D[int(c)] for c in frac)
    elif 1 <= n <= 99 and _native_counter(after, n):
        s = '첫' if n == 1 and after.lstrip().startswith('번째') else native(n)
    else:
        s = sino(n)
    return ('마이너스 ' if m.group('neg') else '') + s

def _native_counter(after, n):
    a = after.lstrip(' ')
    if a.startswith(_SINO_EXCEPT): return False
    if _BEON_COUNT.match(a): return True
    return any(a.startswith(c) for c in _NATIVE_COUNTERS)

# Particles and endings that attach to a number with no space ("0이면", "1을", "4예요"); before anything else Hangul a
# space is added so the number does not fuse into another word ("4장에서" -> "사 장에서", not 사장 "president").
_PARTICLE = re.compile(
    r'(?:이|가|을|를|은|는|의|에|와|과|로|으로|도|만|나|이나|랑|이랑|야|이야|라|이라)(?![\uac00-\ud7a3])'   # a lone particle
    r'|(?:이면|면|이고|고|이에요|예요|이었|였|인|일|이든|든|이지|지|이니|니|에서|에는|에도|에게|으로|로|와|과|부터|까지'
    r'|보다|처럼|만큼|씩|하고|이므로|므로|이라|라|짜리)')   # endings that run on (0이면, 1에서, 4096짜리)

def _space_before(rest):
    return bool(rest) and '\uac00' <= rest[0] <= '\ud7a3' and not _PARTICLE.match(rest)

def _number_at(text, pos):
    """The number token starting at pos and its spoken form, or None."""
    m = _NUM.match(text, pos)
    if not m: return None
    return m, _reading(m, text[m.end():])

def spell(text):
    """Return text with every number read as Korean words (see the module docstring)."""
    out, pos = [], 0
    while pos < len(text):
        c = text[pos]
        starts_num = c.isdigit() or (c == '-' and pos + 1 < len(text) and text[pos + 1].isdigit())
        prev = text[pos - 1] if pos else ''
        if c == '+' and text[pos + 1:pos + 2].isdigit():
            out.append(' 플러스 '); pos += 1; continue                    # 티+1 -> 티 플러스 일
        if not starts_num or (prev.isdigit() or prev == '.'):
            out.append(c); pos += 1; continue
        if re.match(r'[A-Za-z]', prev) or (c == '-' and re.match(r'[\w)\]]', prev)):
            # x86, R3, LC-3: a name; copy the whole digit run unchanged
            m = re.compile(r'-?[\d.,]*\d').match(text, pos)
            out.append(m.group()); pos = m.end(); continue
        hit = _number_at(text, pos)
        if not hit:
            out.append(c); pos += 1; continue
        m, said = hit
        end = m.end()
        # 2^10 -> 이의 십 제곱
        p = re.compile(r'\s?\^\s?(\d+)').match(text, end)
        if p:
            said = f'{said}의 {sino(int(p.group(1)))} 제곱'; end = p.end()
        else:
            # 1/4 -> 사 분의 일 (not dates like 2026/11/17: a third slash skips it)
            p = re.compile(r'/(\d{1,3})(?![\d/])').match(text, end)
            if p and m.group('frac') is None and not m.group('neg') and prev != '/':
                said = f'{sino(int(p.group(1)))} 분의 {said}'; end = p.end()
            else:
                # 1~3 ranges -> 일에서 삼 (the second number is read on the next loop)
                p = re.compile(r'\s?~\s?(?=\d)').match(text, end)
                if p:
                    said += '에서 '; end = p.end()
                elif text.startswith('%', end):
                    said += ' 퍼센트'; end += 1
        if _space_before(text[end:]): said += ' '
        if '\uac00' <= prev <= '\ud7a3': said = ' ' + said      # 2대1 -> 이 대 일, not 대일
        out.append(said); pos = end
    return ''.join(out)

if __name__ == '__main__':
    for arg in sys.argv[1:] or [sys.stdin.read()]:
        print(spell(arg))
