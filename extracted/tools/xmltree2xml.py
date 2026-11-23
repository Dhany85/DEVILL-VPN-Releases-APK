#!/usr/bin/env python3
"""Convert `aapt2 dump xmltree` output into readable XML files.

Usage:
  python3 xmltree2xml.py <input.txt> <output.xml>
"""
import re
import sys

E_RE = re.compile(r'^( *)E: (\S+) \(line=\d+\)$')
A_RE = re.compile(r'^( *)A: (.*?)(?:\(0x[0-9a-fA-F]+\))?=(.*)$')
N_RE = re.compile(r'^ *N: (\w+)=(.*?) \(line=\d+\)$')


class Node:
    def __init__(self, tag, indent):
        self.tag = tag
        self.indent = indent
        self.attrs = []
        self.children = []


def clean_value(rest):
    rest = rest.rstrip()
    raw = None
    idx = rest.rfind(' (Raw: ')
    if idx != -1 and rest.endswith(')'):
        raw = rest[idx + 7:-1]
        rest = rest[:idx]
    if raw is not None:
        return resolve(raw)
    rest = rest.strip()
    if rest.endswith('dp'):
        try:
            return '%gdp' % float(rest[:-2])
        except ValueError:
            pass
    return resolve(rest)


RES_MAP = {}


def resolve(value):
    if value.startswith('@0x') and value[1:] in RES_MAP:
        return '@' + RES_MAP[value[1:]]
    return value


def load_resources(path):
    if not path:
        return
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = re.match(r'^\s*resource (0x[0-9a-fA-F]{8}) (\S+)\s*$', line)
            if m:
                RES_MAP[m.group(1)] = m.group(2)


def parse(path):
    root = None
    stack = []
    namespaces = []
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        m = N_RE.match(line)
        if m:
            namespaces.append((m.group(1), m.group(2)))
            continue
        m = E_RE.match(line)
        if m:
            indent = len(m.group(1))
            node = Node(m.group(2), indent)
            while stack and stack[-1].indent >= indent:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            elif root is None:
                root = node
            stack.append(node)
            continue
        m = A_RE.match(line)
        if m and stack:
            name = re.sub(r'\(0x[0-9a-fA-F]+\)$', '', m.group(2))
            for prefix, uri in namespaces:
                if name.startswith(uri + ':'):
                    name = prefix + ':' + name[len(uri) + 1:]
                    break
            stack[-1].attrs.append((name, clean_value(m.group(3))))
    return root, namespaces


def esc(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def serialize(node, depth, out, ns_attrs):
    pad = '  ' * depth
    attrs = list(ns_attrs) if depth == 0 else []
    for name, value in node.attrs:
        attrs.append((name, value))
    attr_text = ''
    for n, v in attrs:
        if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
            attr_text += ' %s=%s' % (esc(n), esc(v))
        else:
            attr_text += ' %s="%s"' % (esc(n), esc(v))
    if node.children:
        out.append('%s<%s%s>' % (pad, node.tag, attr_text))
        for child in node.children:
            serialize(child, depth + 1, out, ns_attrs)
        out.append('%s</%s>' % (pad, node.tag))
    else:
        out.append('%s<%s%s />' % (pad, node.tag, attr_text))


def main():
    src, dst = sys.argv[1], sys.argv[2]
    load_resources(sys.argv[3] if len(sys.argv) > 3 else None)
    root, namespaces = parse(src)
    if root is None:
        print('no XML elements found in', src, file=sys.stderr)
        return 1
    ns_attrs = [('xmlns:%s' % p, '"%s"' % u) for p, u in namespaces]
    out = []
    serialize(root, 0, out, ns_attrs)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write('\n'.join(out))
        f.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
