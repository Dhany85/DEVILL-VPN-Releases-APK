#!/usr/bin/env python3
"""Tiny writer for Android binary XML (AXML) resource files.

Only what a vector drawable needs is implemented: a UTF-8 string pool, the
resource-map chunk (so the framework can resolve `android:` attributes by
resource id), namespaces and start/end elements with typed attribute values.

The attribute ids below were read back from the APK's own compiled
`res/oN.xml`, so they are known-good for this framework.

  python3 axml.py out.xml      # writes a demo vector, for inspection
"""

import struct

TYPE_STRING = 0x03
TYPE_FLOAT = 0x04
TYPE_DIMENSION = 0x05
TYPE_INT_DEC = 0x10
TYPE_INT_COLOR_ARGB8 = 0x1C

ANDROID_NS = 'http://schemas.android.com/apk/res/android'
ANDROID_ID = {
    'height': 0x01010155,
    'width': 0x01010159,
    'pivotX': 0x010101B5,
    'pivotY': 0x010101B6,
    'scaleX': 0x01010324,
    'scaleY': 0x01010325,
    'viewportWidth': 0x01010402,
    'viewportHeight': 0x01010403,
    'fillColor': 0x01010404,
    'pathData': 0x01010405,
    'fillType': 0x0101051E,
}


class Pool:
    def __init__(self):
        self.strings = []
        self.index = {}

    def add(self, s):
        i = self.index.get(s)
        if i is None:
            i = len(self.strings)
            self.strings.append(s)
            self.index[s] = i
        return i


def _chunk(t, hsz, body):
    return struct.pack('<HHI', t, hsz, 8 + len(body)) + body


def _pool_chunk(pool):
    data = bytearray()
    offsets = []
    for s in pool.strings:
        offsets.append(len(data))
        raw = s.encode('utf-8')
        n = len(s.encode('utf-16-le')) // 2
        for v in (n, len(raw)):
            if v > 0x7F:
                data += bytes((0x80 | (v >> 8), v & 0xFF))
            else:
                data.append(v)
        data += raw
        data.append(0)
    while len(data) % 4:
        data.append(0)

    count = len(pool.strings)
    strings_start = 28 + 4 * count          # header + offset table
    body = struct.pack('<IIIII', count, 0, 0x00000100, strings_start, 0)
    body += b''.join(struct.pack('<I', o) for o in offsets)
    return _chunk(0x0001, 28, body + bytes(data))


def _resmap_chunk(pool, rmap):
    ids = [rmap.get(i, 0) for i in range(len(pool.strings))]
    return _chunk(0x0180, 8, b''.join(struct.pack('<I', i) for i in ids))


def _start_ns(pool, prefix, uri, line=1):
    body = struct.pack('<II', line, 0xFFFFFFFF)
    body += struct.pack('<II', pool.add(prefix), pool.add(uri))
    return _chunk(0x0100, 16, body)


def _end_ns(pool, prefix, uri, line=1):
    body = struct.pack('<II', line, 0xFFFFFFFF)
    body += struct.pack('<II', pool.add(prefix), pool.add(uri))
    return _chunk(0x0101, 16, body)


def _start_element(pool, rmap, name, attrs, line=1):
    """attrs: list of (attr_name, resource_id_or_None, raw_or_None, type, data)."""
    body = struct.pack('<II', line, 0xFFFFFFFF)
    body += struct.pack('<II', 0xFFFFFFFF, pool.add(name))
    body += struct.pack('<HHHHHH', 20, 20, len(attrs), 0, 0, 0)
    ns_idx = pool.add(ANDROID_NS)
    for attr_name, rid, raw, dtype, data in attrs:
        ni = pool.add(attr_name)
        if rid is not None:
            rmap[ni] = rid
        body += struct.pack('<III', ns_idx, ni, 0xFFFFFFFF if raw is None else raw)
        body += struct.pack('<HBBI', 8, 0, dtype, data)
    return _chunk(0x0102, 16, body)


def _end_element(pool, name, line=1):
    body = struct.pack('<II', line, 0xFFFFFFFF)
    body += struct.pack('<II', 0xFFFFFFFF, pool.add(name))
    return _chunk(0x0103, 16, body)


# ---------------------------------------------------------------- values


def dimen(dp):
    return (TYPE_DIMENSION, (int(round(dp)) << 8) | 1)


def f32(v):
    return (TYPE_FLOAT, struct.unpack('<I', struct.pack('<f', v))[0])


def color(argb):
    return (TYPE_INT_COLOR_ARGB8, argb & 0xFFFFFFFF)


def int_dec(v):
    return (TYPE_INT_DEC, v & 0xFFFFFFFF)


# ---------------------------------------------------------------- documents


def vector_drawable(path_data, width=24, height=24, viewport=24.0,
                    argb=0xFFFFFFFF, even_odd=True):
    """One-path vector drawable (shield silhouette with a keyhole hole)."""
    pool, rmap, chunks = Pool(), {}, []

    chunks.append(_start_ns(pool, 'android', ANDROID_NS))
    vec = [
        ('height', ANDROID_ID['height']) + dimen(height),
        ('width', ANDROID_ID['width']) + dimen(width),
        ('viewportWidth', ANDROID_ID['viewportWidth']) + f32(viewport),
        ('viewportHeight', ANDROID_ID['viewportHeight']) + f32(viewport),
    ]
    chunks.append(_start_element(pool, rmap, 'vector',
                                 [(n, r, None, t, d) for n, r, t, d in vec]))
    pi = pool.add(path_data)
    attrs = [
        ('fillColor', ANDROID_ID['fillColor'], None) + color(argb),
        ('pathData', ANDROID_ID['pathData'], pi) + (TYPE_STRING, pi),
    ]
    if even_odd:
        attrs.append(('fillType', ANDROID_ID['fillType'], None) + int_dec(1))
    chunks.append(_start_element(pool, rmap, 'path', attrs, line=2))
    chunks.append(_end_element(pool, 'path', line=2))
    chunks.append(_end_element(pool, 'vector'))
    chunks.append(_end_ns(pool, 'android', ANDROID_NS))

    body = b''.join([_pool_chunk(pool), _resmap_chunk(pool, rmap)] + chunks)
    total = 8 + len(body)
    return struct.pack('<HHI', 0x0003, 8, total) + body


if __name__ == '__main__':
    import sys
    demo = ('M9.5,2.2L14.5,2.2L14.5,9.1C14.5,12.1 13.2,14.1 12,15'
            'C10.8,14.1 9.5,12.1 9.5,9.1Z')
    out = vector_drawable(demo)
    path = sys.argv[1] if len(sys.argv) > 1 else 'vector-demo.xml'
    open(path, 'wb').write(out)
    print('%s: %d bytes' % (path, len(out)))
