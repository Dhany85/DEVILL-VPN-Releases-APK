#!/usr/bin/env python3
"""Render the DEVILL VPN artwork: launcher icons, adaptive icon layers,
notification vector and the Android TV banner.

Pure Python (no Pillow / ImageMagick in this environment):
  * PNG writer (RGBA8) + a tiny PNG reader for verification
  * scanline rasteriser with analytic horizontal + 8x vertical coverage
  * TTF (glyf) reader so banner text uses the app's own Vazirmatn font

Usage:
  python3 make_icons.py [--preview DIR]
"""

import math
import os
import struct
import sys
import zlib

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
BG_TOP = (201, 18, 29)       # #C9121D
BG_BOT = (88, 4, 9)          # #580409
SHIELD_TOP = (255, 255, 255)
SHIELD_BOT = (255, 231, 228)
KEY_TOP = (198, 20, 30)
KEY_BOT = (104, 4, 11)

# --------------------------------------------------------------------------
# PNG
# --------------------------------------------------------------------------


def write_png(path, w, h, rgba):
    """rgba: bytes/bytearray of length w*h*4. Fully opaque images are written as
    RGB (colour type 2), which is what a launcher background should be."""
    stride = w * 4
    opaque = rgba[stride - 1::stride].count(255) == h if h else True
    raw = bytearray()
    if opaque:
        for y in range(h):
            row = rgba[y * stride:(y + 1) * stride]
            raw.append(0)
            for x in range(0, stride, 4):
                raw += row[x:x + 3]
    else:
        for y in range(h):
            raw.append(0)
            raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    out = [b'\x89PNG\r\n\x1a\n',
           chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2 if opaque else 6,
                                      0, 0, 0)),
           chunk(b'IDAT', zlib.compress(bytes(raw), 9)),
           chunk(b'IEND', b'')]
    with open(path, 'wb') as f:
        f.write(b''.join(out))


def read_png(path):
    """Minimal decoder for colour types 6/2/0, bit depth 8 (verification)."""
    d = open(path, 'rb').read()
    pos, idat, ct, bd, w, h = 8, b'', None, None, None, None
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos + 4])[0]
        tag = d[pos + 4:pos + 8]
        data = d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b'IHDR':
            w, h, bd, ct = struct.unpack('>IIBB', data[:10])
        elif tag == b'IDAT':
            idat += data
        elif tag == b'IEND':
            break
    bpp = {0: 1, 2: 3, 6: 4}[ct]
    raw = zlib.decompress(idat)
    stride = w * bpp
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        prev = line
        for x in range(w):
            o = (y * w + x) * 4
            if ct == 6:
                out[o:o + 4] = line[x * 4:x * 4 + 4]
            elif ct == 2:
                out[o:o + 3] = line[x * 3:x * 3 + 3]
                out[o + 3] = 255
            else:
                v = line[x]
                out[o] = out[o + 1] = out[o + 2] = v
                out[o + 3] = 255
    return w, h, bytes(out)


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------


def arc(cx, cy, r, a0, a1, n=48):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def cubic(p0, p1, p2, p3, n=32):
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        out.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0]
                    + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                    mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1]
                    + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def round_rect(x, y, w, h, r, n=16):
    """Clockwise rounded rectangle."""
    pts = []
    pts += arc(x + w - r, y + r, r, -90, 0, n)
    pts += arc(x + w - r, y + h - r, r, 0, 90, n)
    pts += arc(x + r, y + h - r, r, 90, 180, n)
    pts += arc(x + r, y + r, r, 180, 270, n)
    return pts


# shield in a local space: width 1.0 centred on x=0, y from 0 (top) to H (tip)
SH_H = 1.18
SH_R = 0.135
SH_TIP_R = 0.020                  # tiny rounding so the tip is not a knife edge
SH_C2 = (0.127, 1.098)            # control point above the tip
SH_SIDE_C1 = (0.5, 0.82)


def shield_contour():
    """Badge shield: rounded top corners, curved sides, softly rounded V tip."""
    p = []
    p += arc(-0.5 + SH_R, SH_R, SH_R, 180, 270)          # top-left corner
    p += [(0.5 - SH_R, 0.0)]
    p += arc(0.5 - SH_R, SH_R, SH_R, 270, 360)           # top-right corner
    p += [(0.5, 0.36)]

    # where the side curve meets the tip circle, so the outline stays smooth
    cy = SH_H - SH_TIP_R
    a, b = SH_C2[0], cy - SH_C2[1]
    th = math.degrees(math.acos(SH_TIP_R / math.hypot(a, b)) - math.atan2(b, a))
    tip = (SH_TIP_R * math.cos(math.radians(th)),
           cy + SH_TIP_R * math.sin(math.radians(th)))

    p += cubic((0.5, 0.36), SH_SIDE_C1, SH_C2, tip)
    p += arc(0.0, cy, SH_TIP_R, th, 180.0 - th)
    p += cubic((-tip[0], tip[1]), (-SH_C2[0], SH_C2[1]),
               (-0.5, SH_SIDE_C1[1]), (-0.5, 0.36))
    return p


def keyhole_outline(k=1.0):
    """Circle + tapered slot as ONE contour (so even-odd filling works)."""
    r, cy = 0.105 * k, 0.455
    hw_t, hw_b, yb = 0.060 * k, 0.082 * k, 0.800
    dy = math.sqrt(max(r * r - hw_t * hw_t, 0.0))
    a = math.degrees(math.atan2(dy, hw_t))               # slot leaves circle
    p = [(hw_t, cy + dy)]
    p += arc(0.0, cy, r, a, 180.0 - a - 360.0, 120)      # around the top
    p += [(-hw_b, yb)]
    p += arc(0.0, yb, hw_b, 180, 0, 48)                  # rounded bottom
    return p


# --------------------------------------------------------------------------
# rasteriser
# --------------------------------------------------------------------------


def rasterize(contours, w, h, sub=8):
    """Even-odd coverage (0..1) for pixel centroids, sub rows per pixel."""
    cov = [0.0] * (w * h)
    inv = 1.0 / sub
    for y in range(h):
        base = y * w
        for s in range(sub):
            ys = y + (s + 0.5) * inv
            xs = []
            ap = xs.append
            for c in contours:
                x1, y1 = c[-1]
                for x2, y2 in c:
                    if (y1 <= ys < y2) or (y2 <= ys < y1):
                        ap(x1 + (ys - y1) * (x2 - x1) / (y2 - y1))
                    x1, y1 = x2, y2
            if len(xs) < 2:
                continue
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                a, b = xs[i], xs[i + 1]
                if b <= 0.0 or a >= w:
                    continue
                if a < 0.0:
                    a = 0.0
                if b > w:
                    b = float(w)
                ia, ib = int(a), int(b)
                if ia == ib:
                    cov[base + ia] += (b - a) * inv
                    continue
                cov[base + ia] += (ia + 1 - a) * inv
                for x in range(ia + 1, ib):
                    cov[base + x] += inv
                if ib < w:
                    cov[base + ib] += (b - ib) * inv
    return cov


def union(cov_a, cov_b):
    return [max(a, b) for a, b in zip(cov_a, cov_b)]


def scale(cov, k):
    return [c * k for c in cov]


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        n = w * h
        self.r = [0.0] * n
        self.g = [0.0] * n
        self.b = [0.0] * n
        self.a = [0.0] * n

    def paint(self, cov, color, alpha=1.0):
        w, h = self.w, self.h
        R, G, B, A = self.r, self.g, self.b, self.a
        i = 0
        for y in range(h):
            for x in range(w):
                c = cov[i]
                if c > 0.0:
                    if c > 1.0:
                        c = 1.0
                    sa = c * alpha
                    da = A[i]
                    oa = sa + da * (1.0 - sa)
                    if oa > 0.0:
                        sr, sg, sb = color(x, y, w, h)
                        if da > 0.0:
                            k = da * (1.0 - sa)
                            R[i] = (sr * sa + R[i] * k) / oa
                            G[i] = (sg * sa + G[i] * k) / oa
                            B[i] = (sb * sa + B[i] * k) / oa
                        else:
                            R[i], G[i], B[i] = sr, sg, sb
                        A[i] = oa
                i += 1

    def fill(self, color, alpha=1.0):
        n = self.w * self.h
        for i in range(n):
            self.r[i], self.g[i], self.b[i], self.a[i] = *color(i % self.w,
                                                               i // self.w,
                                                               self.w,
                                                               self.h), alpha

    def bytes(self):
        out = bytearray(self.w * self.h * 4)
        o = 0
        for i in range(self.w * self.h):
            out[o] = _u8(self.r[i])
            out[o + 1] = _u8(self.g[i])
            out[o + 2] = _u8(self.b[i])
            a = self.a[i]
            out[o + 3] = 0 if a <= 0.0 else (255 if a >= 1.0 else int(a * 255.0 + 0.5))
            o += 4
        return bytes(out)


def _u8(v):
    return 0 if v <= 0 else (255 if v >= 255 else int(v + 0.5))


def lerp(c0, c1, t):
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return (c0[0] + (c1[0] - c0[0]) * t,
            c0[1] + (c1[1] - c0[1]) * t,
            c0[2] + (c1[2] - c0[2]) * t)


# --------------------------------------------------------------------------
# colour fields
# --------------------------------------------------------------------------


def bg_color(x, y, w, h):
    u, v = x / (w - 1), y / (h - 1)
    base = lerp(BG_TOP, BG_BOT, v ** 1.15)
    # soft light behind the emblem, upper centre
    d = math.hypot((u - 0.5) * 0.85, v - 0.28)
    g = max(0.0, 1.0 - d / 0.95) ** 2 * 30.0
    # gentle vignette keeps the corners from looking flat
    vig = 1.0 - 0.10 * (max(abs(u - 0.5), abs(v - 0.5)) * 2.0) ** 2.2
    return (min(255.0, (base[0] + g) * vig),
            min(255.0, (base[1] + g * 0.55) * vig),
            min(255.0, (base[2] + g * 0.5) * vig))


def shield_color(x, y, w, h):
    u, v = x / (w - 1), y / (h - 1)
    return lerp(SHIELD_TOP, SHIELD_BOT, (0.35 * u + 0.65 * v) ** 1.15)


def key_color(x, y, w, h):
    u, v = x / (w - 1), y / (h - 1)
    return lerp(KEY_TOP, KEY_BOT, (0.25 * u + 0.75 * v))


# --------------------------------------------------------------------------
# composite artwork
# --------------------------------------------------------------------------


def place(contours, scale_, cx, cy):
    """Scale (about origin) and translate contours into pixel space."""
    return [[(cx + px * scale_, cy + py * scale_) for px, py in c]
            for c in contours]


def art_layers(size, shield_frac, cx=None, cy=None, sup=8, key_boost=1.0):
    """Return (shield_cov, key_cov) for a transparent canvas."""
    w = h = size
    cx = w / 2.0 if cx is None else cx
    cy = h / 2.0 if cy is None else cy
    s = size * shield_frac / SH_H          # local units -> pixels
    off = -SH_H / 2.0                      # centre vertically
    sh = place([[ (px, py + off) for px, py in shield_contour() ]], s, cx, cy)
    kh = place([[ (px, py + off) for px, py in keyhole_outline(key_boost) ]], s, cx, cy)
    return rasterize(sh, w, h, sup), rasterize(kh, w, h, sup)


def key_boost_for(size):
    """Bolder keyhole where the icon is tiny, so it stays legible."""
    if size <= 48:
        return 1.28
    if size <= 72:
        return 1.16
    if size <= 96:
        return 1.07
    return 1.0


def render_legacy(size):
    w = h = size
    c = Canvas(w, h)
    mask = rasterize([round_rect(0, 0, w, h, w * 0.225)], w, h, 8)
    c.paint(mask, bg_color)
    sh, key = art_layers(size, 0.60, sup=8, key_boost=key_boost_for(size))
    c.paint(sh, shield_color)
    c.paint(key, key_color)
    return c.bytes()


def render_adaptive_bg(size):
    c = Canvas(size, size)
    c.fill(bg_color)
    return c.bytes()


def render_adaptive_fg(size):
    c = Canvas(size, size)
    # 108dp canvas, visible mask is 72dp: 0.44 * 108dp = 47.5dp, i.e. 66% of
    # the visible circle - the same optical size as the legacy icon.
    sh, key = art_layers(size, 0.44, sup=8)
    c.paint(sh, shield_color)
    c.paint(key, key_color)
    return c.bytes()


def render_logo(size):
    """In-app badge (was a black rounded square with a white glyph)."""
    return render_legacy(size)


# --------------------------------------------------------------------------
# TrueType (glyf) reader - enough for the banner wordmark
# --------------------------------------------------------------------------


class Font:
    def __init__(self, path):
        self.d = d = open(path, 'rb').read()
        n = struct.unpack('>H', d[4:6])[0]
        self.t = {}
        for i in range(n):
            o = 12 + 16 * i
            tag = d[o:o + 4].decode('latin-1')
            off, ln = struct.unpack('>II', d[o + 8:o + 16])
            self.t[tag] = (off, ln)
        head = self.t['head'][0]
        self.upm = struct.unpack('>H', d[head + 18:head + 20])[0]
        self.loca_fmt = struct.unpack('>h', d[head + 50:head + 52])[0]
        self.n_glyphs = struct.unpack('>H', d[self.t['maxp'][0] + 4:][:2])[0]
        self.n_hm = struct.unpack('>H', d[self.t['hhea'][0] + 34:][:2])[0]
        self.hmtx = self.t['hmtx'][0]
        self.loca = self._loca()
        self.cmap = self._cmap()

    def _loca(self):
        o, _ = self.t['loca']
        if self.loca_fmt == 0:
            return [2 * v for v in struct.unpack('>%dH' % (self.n_glyphs + 1),
                                                 self.d[o:o + 2 * (self.n_glyphs + 1)])]
        return list(struct.unpack('>%dI' % (self.n_glyphs + 1),
                                  self.d[o:o + 4 * (self.n_glyphs + 1)]))

    def _cmap(self):
        o, _ = self.t['cmap']
        n = struct.unpack('>H', self.d[o + 2:o + 4])[0]
        best = None
        for i in range(n):
            pid, eid, off = struct.unpack('>HHI', self.d[o + 4 + 8 * i:o + 12 + 8 * i])
            if (pid, eid) in ((3, 10), (0, 4), (0, 6)):
                best = o + off
        if best is None:
            for i in range(n):
                pid, eid, off = struct.unpack('>HHI', self.d[o + 4 + 8 * i:o + 12 + 8 * i])
                if (pid, eid) == (3, 1):
                    best = o + off
        if best is None:
            raise SystemExit('no usable cmap')
        fmt = struct.unpack('>H', self.d[best:best + 2])[0]
        m = {}
        if fmt == 4:
            segx2 = struct.unpack('>H', self.d[best + 6:best + 8])[0]
            seg = segx2 // 2
            p = best + 14
            ends = struct.unpack('>%dH' % seg, self.d[p:p + segx2]); p += segx2 + 2
            starts = struct.unpack('>%dH' % seg, self.d[p:p + segx2]); p += segx2
            deltas = struct.unpack('>%dh' % seg, self.d[p:p + segx2]); p += segx2
            range_off_pos = p
            ro = struct.unpack('>%dH' % seg, self.d[p:p + segx2])
            for i in range(seg):
                for ch in range(starts[i], min(ends[i], 0xFFFF) + 1):
                    if ro[i] == 0:
                        g = (ch + deltas[i]) & 0xFFFF
                    else:
                        gp = range_off_pos + 2 * i + ro[i] + 2 * (ch - starts[i])
                        g = struct.unpack('>H', self.d[gp:gp + 2])[0]
                        if g:
                            g = (g + deltas[i]) & 0xFFFF
                    if g:
                        m[ch] = g
        elif fmt == 12:
            ngroups = struct.unpack('>I', self.d[best + 12:best + 16])[0]
            p = best + 16
            for i in range(ngroups):
                s, e, g = struct.unpack('>III', self.d[p:p + 12])
                p += 12
                for ch in range(s, e + 1):
                    m[ch] = g + (ch - s)
        return m

    def advance(self, gid):
        if gid >= self.n_hm:
            gid = self.n_hm - 1
        o = self.hmtx + 4 * gid
        return struct.unpack('>H', self.d[o:o + 2])[0]

    def contours(self, ch):
        """Glyph outline as list of contours in font units (y up)."""
        gid = self.cmap.get(ord(ch))
        if gid is None:
            return []
        o, _ = self.t['glyf']
        start, end = o + self.loca[gid], o + self.loca[gid + 1]
        if end <= start:
            return []
        nc = struct.unpack('>h', self.d[start:start + 2])[0]
        if nc < 0:
            return []                      # composite: not needed for our text
        p = start + 10
        ends = struct.unpack('>%dH' % nc, self.d[p:p + 2 * nc]); p += 2 * nc
        ilen = struct.unpack('>H', self.d[p:p + 2])[0]; p += 2 + ilen
        npts = ends[-1] + 1
        flags = []
        while len(flags) < npts:
            f = self.d[p]; p += 1
            flags.append(f)
            if f & 8:
                r = self.d[p]; p += 1
                flags += [f] * r
        flags = flags[:npts]
        xs, v = [], 0
        for f in flags:
            if f & 2:
                dx = self.d[p]; p += 1
                v += dx if f & 16 else -dx
            elif not f & 16:
                v += struct.unpack('>h', self.d[p:p + 2])[0]; p += 2
            xs.append(v)
        ys, v = [], 0
        for f in flags:
            if f & 4:
                dy = self.d[p]; p += 1
                v += dy if f & 32 else -dy
            elif not f & 32:
                v += struct.unpack('>h', self.d[p:p + 2])[0]; p += 2
            ys.append(v)
        out, s = [], 0
        for e in ends:
            pts = [(xs[i], ys[i], flags[i] & 1) for i in range(s, e + 1)]
            s = e + 1
            out.append(_flatten_quad(pts))
        return out

    def text_contours(self, text, cap_px, tracking=0.0):
        """Outline of `text` scaled so cap height == cap_px, origin at x=0,
        baseline y=0, y pointing DOWN (ready for the rasteriser)."""
        scale = cap_px / (self.upm * 0.70)          # cap height ~ 70% UPM
        x = 0.0
        out = []
        for ch in text:
            gid = self.cmap.get(ord(ch))
            for c in self.contours(ch):
                out.append([(x + px * scale, -py * scale) for px, py in c])
            if gid is not None:
                x += self.advance(gid) * scale + tracking
            else:
                x += cap_px * 0.5 + tracking
        return out, x


def _flatten_quad(pts):
    """TrueType contour (on/off points, implicit midpoints) -> polyline."""
    n = len(pts)
    if n < 2:
        return []
    start = None
    for i in range(n):
        if pts[i][2]:
            start = i
            break
    if start is None:                      # all off-curve: synthesise
        a, b = pts[0], pts[1]
        start_pt = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, 1)
        pts = [start_pt] + pts
        n += 1
        start = 0
    seq = pts[start:] + pts[:start]
    poly = []
    cur = (seq[0][0], seq[0][1])
    poly.append(cur)
    i = 1
    while i <= len(seq):
        p = seq[i % len(seq)]
        if p[2]:
            poly.append((p[0], p[1]))
            cur = (p[0], p[1])
            i += 1
            continue
        nxt = seq[(i + 1) % len(seq)]
        if nxt[2]:
            end = (nxt[0], nxt[1])
            i += 2
        else:
            end = ((p[0] + nxt[0]) / 2.0, (p[1] + nxt[1]) / 2.0)
            i += 1
        steps = 10
        for k in range(1, steps + 1):
            t = k / steps
            mt = 1 - t
            poly.append((mt * mt * cur[0] + 2 * mt * t * p[0] + t * t * end[0],
                         mt * mt * cur[1] + 2 * mt * t * p[1] + t * t * end[1]))
        cur = end
    return poly


# --------------------------------------------------------------------------
# banner
# --------------------------------------------------------------------------


def banner_color(x, y, w, h):
    u, v = x / (w - 1), y / (h - 1)
    d = math.hypot((u - 0.16) * 1.1, v - 0.55)
    g = max(0.0, 1.0 - d / 0.9) ** 2
    r = 18 + 120 * g
    gg = 6 + 26 * g
    b = 10 + 18 * g
    t = 0.35 * v
    return (r - 6 * t, gg - 2 * t, b + 4 * (1 - v))


def render_banner(w, h, font_path, preview_dir=None):
    c = Canvas(w, h)
    c.fill(banner_color)

    # shield on the left, vertically centred
    sh_h = h * 0.60
    s = sh_h / SH_H
    cx, cy = w * 0.205, h * 0.50
    sh = place([[ (px, py - SH_H / 2.0) for px, py in shield_contour() ]], s, cx, cy)
    kh = place([[ (px, py - SH_H / 2.0) for px, py in keyhole_outline() ]], s, cx, cy)
    cov_sh = rasterize(sh, w, h, 8)
    cov_key = rasterize(kh, w, h, 8)

    f = Font(font_path)
    title, sub = 'DEVILL', 'VPN'

    x0 = cx + s * 0.52 + w * 0.048
    avail = w - x0 - w * 0.075

    # measure once at a reference cap height, then fit the title to the space
    ref = 100.0
    _, ref_w = f.text_contours(title, ref, ref * 0.05)
    cap1 = min(h * 0.285, avail * ref / ref_w)
    tr1 = cap1 * 0.05
    cap2 = cap1 * 0.40
    tr2 = cap2 * 0.72

    t_cont, t_w = f.text_contours(title, cap1, tr1)
    s_cont, s_w = f.text_contours(sub, cap2, tr2)

    block = cap1 + cap2 * 1.75
    top = (h - block) * 0.5 + h * 0.015
    base1 = top + cap1
    base2 = base1 + cap2 * 1.75

    c.paint(cov_sh, shield_color)
    c.paint(cov_key, key_color)

    white = lambda x, y, ww, hh: (255, 255, 255)
    polys = [[(x0 + px, base1 + py) for px, py in cnt] for cnt in t_cont]
    c.paint(rasterize(polys, w, h, 8), white)
    polys = [[(x0 + px, base2 + py) for px, py in cnt] for cnt in s_cont]
    c.paint(rasterize(polys, w, h, 8), white, alpha=0.93)
    return c.bytes()


# --------------------------------------------------------------------------
# notification icon (vector path data)
# --------------------------------------------------------------------------


def _rdp(pts, tol):
    """Ramer-Douglas-Peucker: fewest points that stay within `tol`."""
    if len(pts) < 3:
        return list(pts)
    ax, ay = pts[0]
    bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    den = math.hypot(dx, dy)
    best, bi = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = (abs(dy * px - dx * py + bx * ay - by * ax) / den) if den else math.hypot(px - ax, py - ay)
        if d > best:
            best, bi = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _rdp(pts[:bi + 1], tol)[:-1] + _rdp(pts[bi:], tol)


def vector_path_data(sh_height=17.6, cx=12.0, cy=12.0, nd=2, tol=0.012):
    """Shield + keyhole as one even-odd path in a 24x24 viewport."""
    s = sh_height / SH_H
    out = []
    for cont in (shield_contour(), keyhole_outline()):
        pts = _rdp([(cx + px * s, cy + (py - SH_H / 2.0) * s) for px, py in cont], tol)
        d = 'M%.*f,%.*f' % (nd, pts[0][0], nd, pts[0][1])
        for p in pts[1:]:
            d += 'L%.*f,%.*f' % (nd, p[0], nd, p[1])
        out.append(d + 'Z')
    return ''.join(out)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

RES = {
    # legacy launcher (48 / 72 / 96 / 144 / 192)
    '9w.png': ('legacy', 48), 'yn.png': ('legacy', 72),
    'FS.png': ('legacy', 96), 'RJ.png': ('legacy', 144),
    'o-.png': ('legacy', 192),
    # adaptive background
    '3z.png': ('bg', 108), 'I2.png': ('bg', 162), '6h.png': ('bg', 216),
    'cV.png': ('bg', 324), 'Gx.png': ('bg', 432),
    # adaptive foreground
    'QZ.png': ('fg', 108), 'zr.png': ('fg', 162), 'Em.png': ('fg', 216),
    'Lf.png': ('fg', 324), 'as.png': ('fg', 432),
}


def render_adaptive_preview(size):
    """bg + fg composited inside the 72dp mask, for review only."""
    S = size * 3 // 2
    bg, fg = render_adaptive_bg(S), render_adaptive_fg(S)
    out = bytearray(S * S * 4)
    for i in range(S * S):
        sa = fg[i * 4 + 3] / 255.0
        o = i * 4
        for k in range(3):
            out[o + k] = int(fg[o + k] * sa + bg[o + k] * (1 - sa))
        out[o + 3] = 255
    # circular crop of the visible area
    vis = size
    off = (S - vis) // 2
    img = bytearray(vis * vis * 4)
    for y in range(vis):
        img[y * vis * 4:(y + 1) * vis * 4] = \
            out[((y + off) * S + off) * 4:((y + off) * S + off + vis) * 4]
    c, r = (vis - 1) / 2.0, vis / 2.0 - 1
    for y in range(vis):
        for x in range(vis):
            o = (y * vis + x) * 4
            if math.hypot(x - c, y - c) > r:
                img[o:o + 4] = b'\0\0\0\0'
    return bytes(img)


def main():
    apk = sys.argv[1] if len(sys.argv) > 1 else 'extracted/apk'
    preview = sys.argv[2] if len(sys.argv) > 2 else None
    res = os.path.join(apk, 'res')
    font = os.path.join(apk, 'assets/flutter_assets/assets/fonts/Vazirmatn-Bold.ttf')

    for name, (kind, size) in RES.items():
        data = {'legacy': render_legacy, 'bg': render_adaptive_bg,
                'fg': render_adaptive_fg}[kind](size)
        write_png(os.path.join(res, name), size, size, data)
        print('  %-8s %-7s %dx%d  %d bytes'
              % (name, kind, size, size, os.path.getsize(os.path.join(res, name))))

    # in-app badge
    logo = os.path.join(apk, 'assets/flutter_assets/assets/logo.png')
    write_png(logo, 256, 256, render_logo(256))
    print('  logo.png badge   256x256  %d bytes' % os.path.getsize(logo))

    # TV banner
    br = os.path.join(res, 'OA.png')
    write_png(br, 320, 180, render_banner(320, 180, font))
    print('  OA.png   banner   320x180  %d bytes' % os.path.getsize(br))

    # notification / Quick Settings icon (compiled binary XML)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import axml
    pd = vector_path_data(17.6, 12.0, 12.0)
    vec = os.path.join(res, 'oN.xml')
    with open(vec, 'wb') as f:
        f.write(axml.vector_drawable(pd, 24, 24, 24.0))
    print('  oN.xml   vector   24x24    %d bytes (path %d chars)'
          % (os.path.getsize(vec), len(pd)))

    if preview:
        os.makedirs(preview, exist_ok=True)
        write_png(os.path.join(preview, 'icon-512.png'), 512, 512,
                  render_legacy(512))
        write_png(os.path.join(preview, 'icon-192.png'), 192, 192,
                  render_legacy(192))
        write_png(os.path.join(preview, 'icon-48.png'), 48, 48,
                  render_legacy(48))
        write_png(os.path.join(preview, 'adaptive-round-512.png'), 512, 512,
                  render_adaptive_preview(512))
        write_png(os.path.join(preview, 'logo-256.png'), 256, 256,
                  render_logo(256))
        write_png(os.path.join(preview, 'banner-320x180.png'), 320, 180,
                  render_banner(320, 180, font))
        print('artwork previews in', preview)


if __name__ == '__main__':
    main()
