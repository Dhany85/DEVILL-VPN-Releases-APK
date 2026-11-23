#!/usr/bin/env python3
"""Patch strings inside a binary AndroidManifest.xml.

The binary XML stores all strings in one ResStringPool chunk.  Changing a
string's length means rebuilding that chunk and updating the XML header size;
the element/attribute chunks only hold string *indices*, so they stay valid.

Usage:
  python3 patch_manifest.py <AndroidManifest.xml> OLD=NEW [OLD=NEW ...]
"""
import struct
import sys

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
UTF8_FLAG = 1 << 8
SORTED_FLAG = 1 << 0


def read_pool(buf, off):
    typ, hsz, size = struct.unpack_from('<HHI', buf, off)
    if typ != RES_STRING_POOL_TYPE:
        raise SystemExit('no string pool at offset %d (type=0x%04x)' % (off, typ))
    sc, stc, flags, sstart, ststart = struct.unpack_from('<IIIII', buf, off + 8)
    offs = list(struct.unpack_from('<%dI' % sc, buf, off + hsz)) if sc else []
    soffs = (list(struct.unpack_from('<%dI' % stc, buf, off + hsz + 4 * sc))
             if stc else [])
    return dict(off=off, hsz=hsz, size=size, sc=sc, stc=stc, flags=flags,
                sstart=sstart, ststart=ststart, offs=offs, soffs=soffs)


def _len8(buf, p):
    v = buf[p]
    if v & 0x80:
        return ((v & 0x7F) << 8) | buf[p + 1], p + 2
    return v, p + 1


def _len16(buf, p):
    v = struct.unpack_from('<H', buf, p)[0]
    if v & 0x8000:
        return (((v & 0x7FFF) << 16) | struct.unpack_from('<H', buf, p + 2)[0],
                p + 4)
    return v, p + 2


def decode_all(buf, pool):
    base = pool['off'] + pool['sstart']
    utf8 = bool(pool['flags'] & UTF8_FLAG)
    out = []
    for o in pool['offs']:
        p = base + o
        if utf8:
            _u16, p = _len8(buf, p)
            bl, p = _len8(buf, p)
            out.append(buf[p:p + bl].decode('utf-8'))
        else:
            n, p = _len16(buf, p)
            out.append(buf[p:p + 2 * n].decode('utf-16-le'))
    return out


def enc8(s):
    b = s.encode('utf-8')
    u16 = len(s.encode('utf-16-le')) // 2
    out = bytearray()
    for v in (u16, len(b)):
        if v > 0x7F:
            out += bytes((0x80 | (v >> 8), v & 0xFF))
        else:
            out.append(v)
    return bytes(out) + b + b'\0'


def enc16(s):
    b = s.encode('utf-16-le')
    n = len(b) // 2
    out = bytearray()
    if n > 0x7FFF:
        out += struct.pack('<HH', 0x8000 | (n >> 16), n & 0xFFFF)
    else:
        out += struct.pack('<H', n)
    return bytes(out) + b + b'\0\0'


def build_pool(buf, pool, strings):
    if pool['flags'] & SORTED_FLAG:
        raise SystemExit('string pool is sorted; refusing to patch')
    enc = enc8 if pool['flags'] & UTF8_FLAG else enc16

    data = bytearray()
    offs = []
    for s in strings:
        offs.append(len(data))
        data += enc(s)
    while len(data) % 4:
        data.append(0)

    if pool['stc']:
        styles = bytearray(buf[pool['off'] + pool['ststart']:pool['off'] + pool['size']])
        while len(styles) % 4:
            styles.append(0)
    else:
        styles = bytearray()

    hsz = 28
    sstart = hsz + 4 * (pool['sc'] + pool['stc'])
    ststart = sstart + len(data) if pool['stc'] else 0
    size = sstart + len(data) + len(styles)

    out = bytearray(struct.pack('<HHI', RES_STRING_POOL_TYPE, hsz, size))
    out += struct.pack('<IIIII', pool['sc'], pool['stc'], pool['flags'],
                       sstart, ststart)
    out += struct.pack('<%dI' % pool['sc'], *offs)
    if pool['stc']:
        out += struct.pack('<%dI' % pool['stc'], *pool['soffs'])
    out += data
    out += styles
    return bytes(out)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    pairs = []
    for arg in sys.argv[2:]:
        old, new = arg.split('=', 1)
        pairs.append((old, new))

    buf = bytearray(open(path, 'rb').read())
    typ, hsz, size = struct.unpack_from('<HHI', buf, 0)
    if typ != RES_XML_TYPE:
        raise SystemExit('not a binary XML (type=0x%04x)' % typ)
    if hsz != 8:
        raise SystemExit('unexpected XML header size %d' % hsz)

    pool = read_pool(buf, hsz)
    strings = decode_all(buf, pool)

    hits = 0
    for i, s in enumerate(strings):
        for old, new in pairs:
            if s == old:
                strings[i] = new
                hits += 1
    if hits != len(pairs):
        raise SystemExit('expected %d replacements, made %d'
                         % (len(pairs), hits))

    new_pool = build_pool(buf, pool, strings)
    rest = bytes(buf[pool['off'] + pool['size']:])
    header = struct.pack('<HHI', RES_XML_TYPE, hsz,
                         hsz + len(new_pool) + len(rest))
    with open(path, 'wb') as f:
        f.write(header + new_pool + rest)

    print('patched %s: %d strings, pool %d -> %d bytes'
          % (path, hits, pool['size'], len(new_pool)))


if __name__ == '__main__':
    main()
