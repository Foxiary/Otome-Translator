# -*- coding: utf-8 -*-
"""tags.py - control tags in message strings, and putting #P back.

Library for patch.py, audit.py and sheetfix.py; not a command.

Tags the scripts use inside a message string:

    #P(x,y)          draw from (x, y) on a 1920x1080 screen
    #T1.. #T2.. #T0  text for the default heroine name / for ${FirstName} / both
    #KW              wait for a click inside the message
    #C(TR,0xRRGGBBAA) ... #C(TR,prev)   colour
    #R(reading,...)base                 ruby (furigana) - not needed in VI

Restoring #P is not "copy the JP tag in front":

  - A JP string with several #P is often one paragraph wrapped by hand (same x,
    one line further down each time), text carried on along one line (same y),
    or #T1/#T2 variants at one spot (same x and y). Those fold into one block
    and the VI text wraps itself.
  - What remains is split at the boundaries closest to the JP proportions,
    sentence ends preferred over commas over plain spaces.
  - VI runs longer than JP, so on a screen (messages between WinClear calls)
    each block is pushed down until it clears the one above, and the screen is
    pulled up if it then runs past the bottom. If it still does not fit, the
    screen is rewrapped to the right edge instead of the message-box width.
  - A JP string drawn entirely off-screen (y = 1200) is hidden on purpose: the
    art already shows the text (poems on scrolls). A translation must be seen,
    so such a string is left untagged, and a kept off-screen tag is removed.

Numbers, measured on the game (docs in ../CLAUDE.md):
"""
import re

import kuv

LH_MIN, LH_MAX, LH_DEFAULT = 60, 80, 76   # line pitch: 60 on most screens, ~75 on some
WRAP = 62          # visible characters per line the VI builder wraps at
CW = 18.4          # average px per VI character at 1080p
RIGHT = 1800       # rightmost x a positioned line may reach
SCREEN_W, SCREEN_H = 1920, 1080
BOTTOM = 1000      # lowest a screen's last line may end, unless JP itself goes lower

P = re.compile(r'#P\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)')
HIDDEN = re.compile(r'#C\([^)]*\)|#R\([^)]*\)|#T\d|#KW|#P\([^)]*\)')
SENT_END = set('.!?…」）)』')
MESSAGE_CALLS = ('GuideMess', 'NameMess')


def vis(t):
    """Visible length: tags drawn as nothing, the name as a typical name."""
    return len(HIDDEN.sub('', t).replace('${FirstName}', 'Naya'))


def nlines(t):
    return re.sub(r'\r\n', '\n', t).rstrip('\n').count('\n') + 1


def segments(jp):
    """[(x, y, text)] split on #P; text before the first tag joins the first."""
    parts = P.split(jp)
    out = []
    for k in range(1, len(parts), 3):
        out.append((int(parts[k]), int(parts[k + 1]), parts[k + 2]))
    if out and parts[0].strip():
        x, y, t = out[0]; out[0] = (x, y, parts[0] + t)
    return out


def merged(jp):
    """JP segments with continuations folded: [(x, y, text, jp line count)]."""
    out = []
    for x, y, t in segments(jp):
        n = nlines(t)
        if out:
            px, py, pt, pn = out[-1]
            if y == py or (x == px and 0 < y - py <= pn * LH_MAX):
                lines = max(pn, (y - py) // LH_MIN + n) if y != py else max(pn, n)
                out[-1] = (px, py, pt + ' ' + t, lines)
                continue
        out.append((x, y, t, n))
    return out


def offscreen(x, y):
    return y >= SCREEN_H or x >= SCREEN_W or x < 0 or y < 0


def all_offscreen(positions):
    return bool(positions) and all(offscreen(x, y) for x, y in positions)


def limit(x, wide=False):
    w = int((RIGHT - x) / CW)
    return max(20, w if wide else min(WRAP, w))


def wrap(text, lim):
    lines = []; cur = ''
    for w in text.split(' '):
        if cur and vis(cur) + 1 + vis(w) > lim:
            lines.append(cur); cur = w
        else:
            cur = (cur + ' ' + w) if cur else w
    if cur:
        lines.append(cur)
    return lines


def builder_wrap(t):
    """How the VI builder wraps a sheet cell: each paragraph at WRAP."""
    out = []
    for para in t.split('\n'):
        out += wrap(para.strip(), WRAP) if para.strip() else ['']
    return '\n'.join(out)


def split_parts(vi, jp_segs):
    """Split vi (one paragraph) into len(jp_segs) parts -> (parts, cost) or None."""
    n = len(jp_segs)
    t = re.sub(r'\s*\n\s*', ' ', vi).strip()
    jl = [max(1, vis(re.sub(r'\r?\n', '', s))) for _, _, s in jp_segs]
    tot = float(sum(jl)); target = []; acc = 0
    for l in jl[:-1]:
        acc += l; target.append(acc / tot)
    cands = []
    for i, ch in enumerate(t):
        if ch != ' ' or i == 0:
            continue
        prev = t[i - 1]
        cost = 0.0 if (prev in SENT_END or t[i - 2:i] == '――') else 0.15 if prev in ',;:' else 0.45
        cands.append((i, cost))
    if len(cands) < n - 1:
        return None
    L = float(len(t)); INF = float('inf')
    dp = [[INF] * len(cands) for _ in range(n - 1)]
    back = [[-1] * len(cands) for _ in range(n - 1)]
    for j, (p, c) in enumerate(cands):
        dp[0][j] = abs(p / L - target[0]) + c
    for k in range(1, n - 1):
        best, bj = INF, -1
        for j, (p, c) in enumerate(cands):
            if j >= 1 and dp[k - 1][j - 1] < best:
                best, bj = dp[k - 1][j - 1], j - 1
            if best < INF:
                dp[k][j] = best + abs(p / L - target[k]) + c
                back[k][j] = bj
    j = min(range(len(cands)), key=lambda q: dp[n - 2][q])
    cost = dp[n - 2][j]; cut = []
    for k in range(n - 2, -1, -1):
        cut.append(cands[j][0]); j = back[k][j]
    parts = []; a = 0
    for p in sorted(cut):
        parts.append(t[a:p].strip()); a = p + 1
    parts.append(t[a:].strip())
    return parts, cost


def blocks_for(jp, vi, wide=False):
    """[(x, y, lines)] for a VI string, with 'single'/'multi' and split cost."""
    segs = [(x, y, t) for x, y, t, _ in merged(jp)]
    if len(segs) == 1:
        x, y, _ = segs[0]
        lines = vi.split('\n')
        if wide or max(vis(l) for l in lines) > limit(x):
            lines = wrap(' '.join(l.strip() for l in lines), limit(x, wide))
        return [(x, y, lines)], 'single', 0.0
    r = split_parts(vi, segs)
    if r is None:
        return None, 'unsplittable', 0.0
    parts, cost = r
    return [(x, y, wrap(p, limit(x, wide))) for (x, y, _), p in zip(segs, parts)], 'multi', cost


def restore(jp_raw, vstrs, only=None):
    """Put #P back into vstrs (list, same indices as the JP script jp_raw).

    -> (new list, report). Each report row: idx, how ('single', 'multi',
    'offscreen', 'unsplittable'), cost, shifted, wide, flag."""
    _, jstrs, _ = kuv.parse(jp_raw)
    cl = kuv.calls(jp_raw)
    vstrs = list(vstrs); rep = []; lost = set()
    for i, (a, b) in enumerate(zip(jstrs, vstrs)):
        if not P.search(a) or P.search(b) or (only is not None and i not in only):
            continue
        if all_offscreen([(x, y) for x, y, _, _ in merged(a)]):
            rep.append(dict(idx=i, how='offscreen', cost=0.0)); continue
        bl, how, cost = blocks_for(a, b)
        if bl is None:
            rep.append(dict(idx=i, how=how, cost=0.0, flag='khong tach duoc')); continue
        lost.add(i)
        rep.append(dict(idx=i, how=how, cost=cost))
    groups = []; cur = []
    for f, args, _ in cl:
        if f in MESSAGE_CALLS and args and args[-1] in lost:
            if args[-1] not in cur:
                cur.append(args[-1])
        elif f == 'WinClear' and cur:
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)

    def layout(g, wide):
        blk = dict((s, [list(x) for x in blocks_for(jstrs[s], vstrs[s], wide)[0]]) for s in g)
        mj = dict((s, merged(jstrs[s])) for s in g)
        bl = [(s, k) for s in g for k in range(len(blk[s]))]
        jy = dict(((s, k), blk[s][k][1]) for s, k in bl)
        per = [(jy[b] - jy[a]) / float(mj[a[0]][a[1]][3]) for a, b in zip(bl, bl[1:]) if jy[b] > jy[a]]
        lh = min(LH_MAX, max(LH_MIN, min(per))) if per else LH_DEFAULT
        jp_bottom = max(jy[b] + mj[b[0]][b[1]][3] * lh for b in bl)
        carry = 0
        for a, b in zip(bl, bl[1:]):
            if jy[b] <= jy[a]:
                carry = 0; continue                      # a new column, not stacked
            need = blk[a[0]][a[1]][1] + len(blk[a[0]][a[1]][2]) * lh
            ny = max(jy[b] + carry, need)
            carry = ny - jy[b]
            blk[b[0]][b[1]][1] = ny
        bottom = max(blk[s][k][1] + len(blk[s][k][2]) * lh for s, k in bl)
        allowed = max(BOTTOM, jp_bottom)
        if bottom > allowed:
            top = min(blk[s][k][1] for s, k in bl)
            up = min(bottom - allowed, max(0, top - 40))
            for s, k in bl:
                blk[s][k][1] -= up
            bottom -= up
        moved = set(s for s, k in bl if blk[s][k][1] != jy[(s, k)])
        return blk, bottom, allowed, moved

    todo = {}; seen = set(); shifted = set(); wided = set(); flags = {}
    for g in groups:
        g = [s for s in g if s not in seen]; seen.update(g)
        if not g:
            continue
        blk, bottom, allowed, moved = layout(g, False)
        if bottom > allowed + 20:
            blk, bottom, allowed, moved = layout(g, True); wided.update(g)
            if bottom > allowed + 20:
                for s in g:
                    flags[s] = 'tran cuoi man hinh (%d > %d)' % (bottom, allowed)
        todo.update(blk); shifted.update(moved)
    for i in lost - set(todo):                 # never shown by a message call
        todo[i] = [list(x) for x in blocks_for(jstrs[i], vstrs[i])[0]]
    for r in rep:
        i = r['idx']
        if i not in todo:
            continue
        vstrs[i] = '\n'.join('#P(%d,%d)' % (x, y) + '\n'.join(lines) for x, y, lines in todo[i])
        r.update(shifted=i in shifted, wide=i in wided, flag=flags.get(i, ''))
    return vstrs, rep


def strip_offscreen(strs):
    """Drop #P tags that put a whole string off-screen. -> (list, changed indices)."""
    out = list(strs); changed = []
    for i, s in enumerate(out):
        pos = [(int(x), int(y)) for x, y in P.findall(s)]
        if all_offscreen(pos):
            out[i] = P.sub('', s); changed.append(i)
    return out, changed


def losses(jp, vi):
    """Tag kinds the VI string lost against the JP one."""
    out = []
    if P.search(jp) and not P.search(vi) and not all_offscreen([(x, y) for x, y, _, _ in merged(jp)]):
        out.append('#P')
    if re.search(r'#T[12]', jp) and not re.search(r'#T[12]', vi):
        out.append('#T')
    if jp.count('#KW') > vi.count('#KW'):
        out.append('#KW')
    return out
