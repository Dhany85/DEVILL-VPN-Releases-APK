#!/usr/bin/env python3
"""Rebuild the APK with in-place, same-length string replacements.

Usage:
  python3 rebuild_apk.py <original.apk> <source-dir> <output.apk>

Every replacement MUST keep the byte length identical: Flutter AOT strings and
Go string/type tables are length-prefixed, so resizing them corrupts the
binaries.  URLs are therefore rewritten to a dead localhost endpoint of exactly
the same length, and names that got longer/shorter are padded so the byte count
never changes.

Rebrand:
  Shivaay VPN            -> DEVILL VPN     (ASCII + UTF-16LE)
  Shivaay20005           -> Dhany Devill
  Shivaay-vpn-client     -> DhanyDevill-Client
  Shivaay-VPN-*          -> DEVILL-VPN--*
  shivaay-vpn            -> devill-vpns
  shivaay_vpn            -> devill_vpns
  __shivaayReply         -> __devillReply_
  __shivaayHooked        -> __devillHooked_
  ShivaayFxa             -> DevillFxa_

Kept on purpose (required by DEX/JNI, never shown in the UI):
  com.shivaay.firefoxvpn / com/shivaay/firefoxvpn  (Java class + JNI package)
"""
import os
import re
import struct
import sys
import zipfile
import zlib

from patch_manifest import decode_all, read_pool

ALIGN = 4
DEAD = 'https://127.0.0.1:9/'      # unreachable, but a syntactically valid URL
REPO = 'Dhany85/DEVILL-VPN-Releases-APK'
VERSION_NAME = '1.0.1'
VERSION_CODE = 2002

APP = 'lib/arm64-v8a/libapp.so'
GO = 'lib/arm64-v8a/libgojni.so'
HEV = 'lib/arm64-v8a/libhev-socks5-tunnel.so'
ARSC = 'resources.arsc'


def pad(n, text):
    """Return `text` padded with 'x' up to exactly n bytes."""
    if len(text) > n:
        raise ValueError('%r longer than %d' % (text, n))
    return text + 'x' * (n - len(text))


def dead_url(n):
    return pad(n, DEAD)


def u16(s):
    return s.encode('utf-16-le')


REPLACEMENTS = {
    'AndroidManifest.xml': [
        ('1.0.0'.encode('utf-16-le'), VERSION_NAME.encode('utf-16-le')),
    ],
    ARSC: [
        (b'Shivaay VPN', b'DEVILL VPN '),
    ],
    APP: [
        # Branding, both encodings (11 chars -> 11 chars, same byte length)
        (u16('Shivaay VPN'), u16('DEVILL VPN ')),
        (b'Shivaay VPN', b'DEVILL VPN '),

        # Neutral wording in the update-error messages (same byte length).
        # Longer phrases first: "GitHub. V" is a prefix of "GitHub. Verifique".
        (b'GitHub. Check', b'server. Check'),
        (b'GitHub. Periksa', b'server. Periksa'),
        (b'GitHub. Comprueba', b'la red. Comprueba'),
        (b'GitHub. Verifique', b'server. Verifique'),
        (b'GitHub. V', b"l'hote. V"),

        # Full project URLs first, longest first
        # The app's own GitHub project, byte-for-byte the same length as the
        # original (owner 12 -> DhanyDevill 11 + repo 19 = 31 chars).
        (b'https://raw.githubusercontent.com/Shivaay20005/Shivaay-vpn-client/HEAD/.github/updates.json',
         b'https://raw.githubusercontent.com/%s/HEAD/.github/updates.json' % REPO.encode()),
        (b'https://cdn.jsdelivr.net/gh/Shivaay20005/Shivaay-vpn-client@main/.github/updates.json',
         b'https://cdn.jsdelivr.net/gh/%s@main/.github/updates.json' % REPO.encode()),
        (b'https://api.github.com/repos/Shivaay20005/Shivaay-vpn-client/releases/latest',
         b'https://api.github.com/repos/%s/releases/latest' % REPO.encode()),
        (b'https://github.com/Shivaay20005/Shivaay-vpn-client/releases',
         b'https://github.com/%s/releases' % REPO.encode()),
        (b'https://github.com/Shivaay20005/Shivaay-vpn-client',
         b'https://github.com/%s' % REPO.encode()),

        # Owner/repo names (about screen, URL building) - 31 and 18 bytes
        (b'Shivaay20005/Shivaay-vpn-client', b'DhanyDevill/Dhany-Devill-Client'),
        (b'Shivaay20005', b'Dhany Devill'),
        (b'Shivaay-vpn-client', b'DhanyDevill-Client'),

        # Remaining generic prefixes (Flutter docs links, flag SVGs) - kept
        # intact, they cost nothing and the app builds URLs from them.

        # Filenames / user agent / JS bridge (invisible to users)
        (b'SHIVAAY_VPN_UPDATE_SERVER', b'DEVILL_VPN_UPDATE_SERVERS'),  # 25 -> 25
        (b'Shivaay-VPN-', b'DEVILL-VPN--'),        # 12 -> 12
        (b'shivaay-vpn', b'devill-vpns'),          # 11 -> 11
        (b'shivaay_vpn', b'devill_vpns'),          # 11 -> 11 (Dart package: URIs)
        (b'__shivaayReply', b'__devillReply_'),    # 14 -> 14
        (b'__shivaayHooked', b'__devillHooked_'),  # 15 -> 15
        (b'ShivaayFxa', b'DevillFxa_'),            # 10 -> 10 (JS channel)
    ],
    GO: [
        (b'Shivaay VPN', b'DEVILL VPN '),
        (b'Shivaay20005/Shivaay-vpn-client', b'DhanyDevill/Dhany-Devill-Client'),
        (b'Shivaay20005', b'Dhany Devill'),
        (b'Shivaay-vpn-client', b'DhanyDevill-Client'),
        (b'Shivaay-VPN-', b'DEVILL-VPN--'),
        (b'shivaay-vpn', b'devill-vpns'),
    ],
    HEV: [
        (b'Shivaay-vpn-client', b'DhanyDevill-Client'),
    ],
}

# Exact number of hits in the *unmodified* source file.  A mismatch means the
# source tree changed and the replacement list needs another look.
EXPECTED = {
    ('AndroidManifest.xml', '1.0.0'.encode('utf-16-le')): 1,
    (ARSC, b'Shivaay VPN'): 1,
    (APP, b'Shivaay VPN'): 20,
    (APP, u16('Shivaay VPN')): 26,
    (APP, b'Shivaay20005'): 6,
    (APP, b'Shivaay-vpn-client'): 8,
    (APP, b'Shivaay-VPN-'): 3,
    (APP, b'SHIVAAY_VPN_UPDATE_SERVER'): 1,
    (APP, b'shivaay-vpn'): 1,
    (APP, b'shivaay_vpn'): 48,
    (APP, b'__shivaayReply'): 2,
    (APP, b'__shivaayHooked'): 2,
    (APP, b'ShivaayFxa'): 2,
    (GO, b'Shivaay VPN'): 15,
    (GO, b'Shivaay20005'): 1973,
    (GO, b'Shivaay-vpn-client'): 1977,
    (GO, b'Shivaay-VPN-'): 3,
    (GO, b'shivaay-vpn'): 8,
    (HEV, b'Shivaay-vpn-client'): 32,
}

# After rebranding only the Java package/class names may keep "shivaay".
ALLOWED_LEFTOVERS = {
    'classes.dex': 10,              # Lcom/shivaay/firefoxvpn/... + intent actions
    'AndroidManifest.xml': 5,       # android:name="com.shivaay.firefoxvpn.*" (UTF-16)
    ARSC: 1,                        # resource-table package name (id 0x7f)
    HEV: 1,                         # com/shivaay/firefoxvpn/Tun2Socks (JNI)
}


def _manifest_attrs(data, name):
    """Offsets of the attribute records named `name` in a binary manifest."""
    names = decode_all(data, read_pool(data, 8))
    try:
        want = names.index(name)
    except ValueError:
        return
    off = 8
    while off + 8 <= len(data):
        typ, hsz, size = struct.unpack_from('<HHI', data, off)
        if typ == 0x0102:                       # RES_XML_START_ELEMENT
            ext = off + hsz
            a_start, a_size, a_count = struct.unpack_from('<HHH', data, ext + 8)
            for i in range(a_count):
                a = ext + a_start + i * a_size
                if struct.unpack_from('<I', data, a + 4)[0] == want:
                    yield a
        if size < 8:
            return
        off += size


def _set_typed(data, attr, dtype, value):
    """Write an attribute's typed value: size=8, res0=0, type, 32-bit data."""
    struct.pack_into('<BB', data, attr + 14, 0, dtype)
    struct.pack_into('<I', data, attr + 16, value)


def disable_backup(data):
    """allowBackup=false: a cloud backup would copy account tokens off-device."""
    for a in _manifest_attrs(data, 'allowBackup'):
        _set_typed(data, a, 0x12, 0)            # TYPE_INT_BOOLEAN
        return data
    raise SystemExit('AndroidManifest.xml: no allowBackup attribute')


def set_version_code(data, code):
    """Bump versionCode so the installer/updater sees a newer build."""
    for a in _manifest_attrs(data, 'versionCode'):
        _set_typed(data, a, 0x10, code)         # TYPE_INT_DEC
        return data
    raise SystemExit('AndroidManifest.xml: no versionCode attribute')


def bump_app_version(data):
    """Dart-side version strings (user agent + version constant).

    Skips "1.0.0.x" text: those are DNS resolver IPs, not versions.
    """
    data, n = re.subn(rb'1\.0\.0(?![0-9.])', VERSION_NAME.encode(), data)
    if n != 2:
        raise SystemExit('libapp.so: expected 2 version strings, found %d' % n)
    return bytearray(data)                      # manifest patch needs writable


def deflate_raw(data, level=9):
    """Raw DEFLATE stream (no zlib header/trailer) - required by the ZIP spec."""
    co = zlib.compressobj(level, zlib.DEFLATED, -15)
    return co.compress(data) + co.flush()


def dos_datetime(t):
    y, mo, d, h, mi, s = t
    return ((h << 11) | (mi << 5) | (s // 2),
            ((y - 1980) << 9) | (mo << 5) | d)


def alignment_extra(offset, name_len):
    """Extra field that makes the entry data start on a 4-byte boundary."""
    pad = (-(offset + 30 + name_len)) % ALIGN
    if pad == 0:
        return b''
    while pad < 6:          # room for id(2) + size(2) + value(2)
        pad += ALIGN
    size = pad - 4
    return struct.pack('<HHH', 0xD935, size, ALIGN) + b'\0' * (size - 2)


def shivaay_count(data):
    return data.lower().count(b'shivaay') + data.lower().count(u16('shivaay'))


def verify_output(path):
    """Fail if any non-allowlisted 'shivaay' string survives."""
    bad = {}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            n = shivaay_count(z.read(name))
            if n and n != ALLOWED_LEFTOVERS.get(name, 0):
                bad[name] = n
    if bad:
        raise SystemExit('leftover "shivaay" outside allowlist: %r' % bad)
    print('verify: no "shivaay" outside the allowlisted DEX/JNI names')


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    original, src_dir, output = sys.argv[1], sys.argv[2], sys.argv[3]

    with zipfile.ZipFile(original) as z:
        infos = z.infolist()

    counts = {}
    with open(output, 'wb') as f:
        central = []
        for info in infos:
            with open(os.path.join(src_dir, info.filename), 'rb') as fh:
                data = fh.read()
            raw = data

            for old, new in REPLACEMENTS.get(info.filename, []):
                if len(old) != len(new):
                    raise SystemExit('length mismatch: %r -> %r' % (old, new))
                want = EXPECTED.get((info.filename, old))
                if want is not None and raw.count(old) != want:
                    raise SystemExit('%s: expected %d x %r, source has %d'
                                     % (info.filename, want, old,
                                        raw.count(old)))
                n = data.count(old)
                if n:
                    data = data.replace(old, new)
                    counts[(info.filename, old)] = n

            if info.filename == APP:
                data = bump_app_version(data)
            if info.filename == 'AndroidManifest.xml':
                data = bytearray(data)
                data = set_version_code(data, VERSION_CODE)
                data = disable_backup(data)

            method = info.compress_type
            if method == zipfile.ZIP_DEFLATED:
                payload = deflate_raw(data)
            elif method == zipfile.ZIP_STORED:
                payload = data
            else:
                raise SystemExit('unsupported method %d for %s'
                                 % (method, info.filename))

            name = info.filename.encode('utf-8')
            crc = zlib.crc32(data) & 0xFFFFFFFF
            dostime, dosdate = dos_datetime(info.date_time)
            offset = f.tell()

            extra = b''
            if method == zipfile.ZIP_STORED:
                extra = alignment_extra(offset, len(name))
                if (offset + 30 + len(name) + len(extra)) % ALIGN != 0:
                    raise SystemExit('alignment failed for ' + info.filename)

            f.write(struct.pack(
                '<IHHHHHIIIHH',
                0x04034B50, 20, 0, method, dostime, dosdate,
                crc, len(payload), len(data), len(name), len(extra)))
            f.write(name)
            f.write(extra)
            f.write(payload)

            central.append(struct.pack(
                '<IHHHHHHIIIHHHHHII',
                0x02014B50, (3 << 8) | 20, 20, 0, method, dostime, dosdate,
                crc, len(payload), len(data), len(name), len(extra),
                0, 0, 0, info.external_attr, offset) + name + extra)

        cd_offset = f.tell()
        for record in central:
            f.write(record)
        cd_size = f.tell() - cd_offset
        f.write(struct.pack(
            '<IHHHHIIH',
            0x06054B50, 0, 0, len(central), len(central),
            cd_size, cd_offset, 0))

    print('wrote %s (%d bytes, %d entries)'
          % (output, os.path.getsize(output), len(infos)))
    for (fname, old), n in sorted(counts.items()):
        label = old.decode('latin-1') if b'\0' not in old else repr(old)
        print('  %-32s %-40s x%d' % (fname, label, n))

    verify_output(output)


if __name__ == '__main__':
    main()
