#!/usr/bin/env python3
"""Build every launcher/notification asset of DEVILL VPN from one artwork file.

The artwork (``extracted/artwork/icon-source.png``) is a 1024x1024 PNG and is
used exactly as sent: nothing is cropped, retouched or redrawn.  The marble
frame around the rounded card stays part of the image, the wordmark stays where
the artist put it.

  legacy launcher icon   48..192 px   the whole artwork
  adaptive background    108..432 px  the whole artwork, centred on the card's
                                      plate colour
  adaptive foreground    108..432 px  transparent (res/BW.xml references it)
  notification icon      24 dp        white vector shield (res/oN.xml)
  TV banner              320x180      the whole artwork, centred
  in-app logo            256 px       the whole artwork

Only pure Python is used (PNG reader/writer and the resampler below are
hand-written); Pillow/ImageMagick/cairo are not available here.

    python3 extracted/tools/icons_from_art.py extracted/apk build/artwork
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import axml                                            # noqa: E402
from make_icons import read_png, write_png             # noqa: E402

SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'artwork', 'icon-source.png')

# The adaptive icon drops the artwork's card frame: a square card can never
# both fill a circular/squircle mask and keep its corners.  What is left is the
# card surface (plate) as a full-bleed background plus the design itself.
# CROP is the card interior (bevel and marble left out); ART_DP is its side on
# the 108 dp layer, sized so that head, ring and wordmark stay 1.8 dp inside
# the 72 dp circle.
CROP = (135, 125, 890, 908)
ART_DP = 58.0
FEATHER = 14                            # source px, soft edge of the crop


# --------------------------------------------------------------------------
# resampling: premultiplied box filter, fractional source coverage
# --------------------------------------------------------------------------

def _weights(src_n, dst_n):
    scale = src_n / float(dst_n)
    out = []
    for d in range(dst_n):
        s0, s1 = d * scale, (d + 1) * scale
        i0, i1 = int(math.floor(s0)), int(math.ceil(s1))
        acc = []
        for i in range(i0, i1):
            cov = min(s1, i + 1.0) - max(s0, float(i))
            if cov > 0.0:
                acc.append((min(max(i, 0), src_n - 1), cov / scale))
        if not acc:
            acc = [(min(max(i0, 0), src_n - 1), 1.0)]
        out.append(acc)
    return out


def resize(src, sw, sh, dw, dh):
    """Area-average downscale (works for upscale too), alpha-correct."""
    xw, yw = _weights(sw, dw), _weights(sh, dh)
    tmp = [None] * (dw * sh)
    for y in range(sh):
        row = y * sw * 4
        for dx, acc in enumerate(xw):
            r = g = b = a = 0.0
            for sx, w in acc:
                o = row + sx * 4
                al = src[o + 3]
                r += src[o] * al * w
                g += src[o + 1] * al * w
                b += src[o + 2] * al * w
                a += al * w
            tmp[y * dw + dx] = (r, g, b, a)

    out = bytearray(dw * dh * 4)
    for dy, acc in enumerate(yw):
        base = dy * dw
        for dx in range(dw):
            r = g = b = a = 0.0
            for sy, w in acc:
                sr, sg, sb, sa = tmp[sy * dw + dx]
                r += sr * w
                g += sg * w
                b += sb * w
                a += sa * w
            o = (base + dx) * 4
            if a > 1e-6:
                out[o] = min(255, int(r / a + 0.5))
                out[o + 1] = min(255, int(g / a + 0.5))
                out[o + 2] = min(255, int(b / a + 0.5))
                out[o + 3] = min(255, int(a + 0.5))
    return bytes(out)


def crop(img, w, x0, y0, x1, y1):
    cw, ch = x1 - x0, y1 - y0
    out = bytearray(cw * ch * 4)
    for y in range(ch):
        src = ((y0 + y) * w + x0) * 4
        out[y * cw * 4:(y + 1) * cw * 4] = img[src:src + cw * 4]
    return bytes(out), cw, ch


def blit(dst, dw, dh, src, sw, sh, dx, dy):
    """Alpha-composite `src` over `dst` at integer offset dx,dy."""
    for y in range(sh):
        ty = dy + y
        if ty < 0 or ty >= dh:
            continue
        for x in range(sw):
            tx = dx + x
            if tx < 0 or tx >= dw:
                continue
            so = (y * sw + x) * 4
            sa = src[so + 3]
            if not sa:
                continue
            do = (ty * dw + tx) * 4
            if sa == 255:
                dst[do:do + 4] = src[so:so + 4]
                continue
            inv = 255 - sa
            for k in range(3):
                dst[do + k] = (src[so + k] * sa + dst[do + k] * inv + 127) // 255
            dst[do + 3] = min(255, sa + dst[do + 3] * inv // 255)


def mean_patch(img, w, patches, size):
    acc = [0, 0, 0]
    n = 0
    for px0, py0 in patches:
        for y in range(py0, py0 + size):
            for x in range(px0, px0 + size):
                o = (y * w + x) * 4
                acc[0] += img[o]
                acc[1] += img[o + 1]
                acc[2] += img[o + 2]
                n += 1
    return tuple(c // n for c in acc)


def plate_color(img, w, h):
    """Mean colour of the card surface, just inside its bevel."""
    return mean_patch(img, w, [(140, 150), (820, 150),
                               (140, 760), (820, 760)], 48)


def frame_color(img, w, h):
    """Mean colour of the marble frame around the card (TV banner)."""
    return mean_patch(img, w, [(0, 0), (w - 32, 0),
                               (0, h - 32), (w - 32, h - 32)], 32)


def solid(size, colour):
    """Opaque single-colour RGBA buffer."""
    px = bytes(colour) + b'\xff'
    return bytearray(px * (size * size))


# --------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------

LEGACY = [('9w.png', 48), ('yn.png', 72), ('FS.png', 96),
          ('RJ.png', 144), ('o-.png', 192)]
ADAPT_BG = [('3z.png', 108), ('I2.png', 162), ('6h.png', 216),
            ('cV.png', 324), ('Gx.png', 432)]
ADAPT_FG = [('QZ.png', 108), ('zr.png', 162), ('Em.png', 216),
            ('Lf.png', 324), ('as.png', 432)]

NOTIFY_PATH = (
    'M12,2.4L19.5,2.4C20.05,2.4 20.5,2.85 20.5,3.4L20.5,11.3'
    'C20.5,16.2 16.8,20.4 12,21.6C7.2,20.4 3.5,16.2 3.5,11.3'
    'L3.5,3.4C3.5,2.85 3.95,2.4 4.5,2.4Z')


def build(source, apk, previews=None):
    w, h, img = read_png(source)
    if (w, h) != (1024, 1024):
        raise SystemExit('%s: expected a 1024x1024 source, got %dx%d'
                         % (source, w, h))

    plate = plate_color(img, w, h)
    frame = frame_color(img, w, h)
    print('plate #%02X%02X%02X  frame #%02X%02X%02X' % (plate + frame))

    body, cw, ch = crop(img, w, *CROP)

    def art(size):
        return resize(img, w, h, size, size)

    def adaptive_tile(size):
        """Card surface as a full-bleed background, design on top with the
        crop edge feathered into it, so no frame is left to be cut by the mask."""
        side = max(1, int(round(ART_DP * size / 108.0)))
        side_h = max(1, int(round(side * ch / float(cw))))
        canvas = solid(size, plate)
        design = bytearray(resize(body, cw, ch, side, side_h))
        soft = max(2, int(round(FEATHER * side / float(cw))))
        for y in range(side_h):
            for x in range(side):
                o = (y * side + x) * 4
                d = min(x, side - 1 - x, y, side_h - 1 - y)
                if d < soft:
                    design[o + 3] = design[o + 3] * d // soft
        blit(canvas, size, size, bytes(design), side, side_h,
             (size - side) // 2, (size - side_h) // 2)
        return bytes(canvas)

    res = os.path.join(apk, 'res')

    # --- legacy launcher icons: the artwork as sent -----------------------
    for name, size in LEGACY:
        write_png(os.path.join(res, name), size, size, art(size))
        print('  %-8s legacy   %3dx%-3d' % (name, size, size))

    # --- adaptive icon ----------------------------------------------------
    # background carries the whole artwork (no parallax seams); the foreground
    # is transparent and only exists because the drawable references it.
    for name, size in ADAPT_BG:
        write_png(os.path.join(res, name), size, size, adaptive_tile(size))
        print('  %-8s bg       %3dx%-3d' % (name, size, size))
    for name, size in ADAPT_FG:
        write_png(os.path.join(res, name), size, size,
                  bytes(size * size * 4))
        print('  %-8s fg       %3dx%-3d  (transparent)' % (name, size, size))

    # --- notification / Quick Settings icon -------------------------------
    vec = os.path.join(res, 'oN.xml')
    with open(vec, 'wb') as f:
        f.write(axml.vector_drawable(NOTIFY_PATH, 24, 24, 24.0,
                                     even_odd=False))
    print('  oN.xml   vector   24x24    %d bytes' % os.path.getsize(vec))

    # --- Android TV banner ------------------------------------------------
    bw, bh = 320, 180
    banner = bytearray((bytes(frame) + b'\xff') * (bw * bh))
    blit(banner, bw, bh, art(bh), bh, bh, (bw - bh) // 2, 0)
    write_png(os.path.join(res, 'OA.png'), bw, bh, bytes(banner))
    print('  OA.png   banner   320x180')

    # --- in-app logo ------------------------------------------------------
    logo = os.path.join(apk, 'assets', 'flutter_assets', 'assets', 'logo.png')
    write_png(logo, 256, 256, art(256))
    print('  logo.png badge    256x256')

    if previews:
        os.makedirs(previews, exist_ok=True)
        write_png(os.path.join(previews, 'icon-512.png'), 512, 512, art(512))
        write_png(os.path.join(previews, 'icon-192.png'), 192, 192, art(192))
        write_png(os.path.join(previews, 'icon-48.png'), 48, 48, art(48))
        write_png(os.path.join(previews, 'logo-256.png'), 256, 256, art(256))
        write_png(os.path.join(previews, 'banner-320x180.png'), bw, bh,
                  bytes(banner))
        # the adaptive icon as a round launcher shows it (inner 72 dp)
        S = 540
        canvas = bytearray(adaptive_tile(S))
        vis = int(round(S * 72.0 / 108.0))
        off = (S - vis) // 2
        img2 = bytearray(vis * vis * 4)
        for y in range(vis):
            img2[y * vis * 4:(y + 1) * vis * 4] = \
                canvas[((y + off) * S + off) * 4:((y + off) * S + off + vis) * 4]
        c, r = (vis - 1) / 2.0, vis / 2.0 - 1
        for y in range(vis):
            for x in range(vis):
                o = (y * vis + x) * 4
                if math.hypot(x - c, y - c) > r:
                    img2[o:o + 4] = b'\0\0\0\0'
        write_png(os.path.join(previews, 'adaptive-round-512.png'),
                  vis, vis, bytes(img2))
        print('artwork previews in', previews)


def main():
    apk = sys.argv[1] if len(sys.argv) > 1 else 'extracted/apk'
    previews = sys.argv[2] if len(sys.argv) > 2 else None
    print('source:', os.path.normpath(SOURCE))
    build(os.path.normpath(SOURCE), apk, previews)


if __name__ == '__main__':
    main()
