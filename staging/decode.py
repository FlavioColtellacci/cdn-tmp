#!/usr/bin/env python3
"""Decode staging/*.jpg.b64 (or .jpg.b64.NN parts) into root *.jpg and commit if changed."""
import base64, pathlib, subprocess, re
from collections import defaultdict

root = pathlib.Path('.')
staging = root / 'staging'
changed = []

wholes = {p.name: p for p in staging.glob('*.jpg.b64')}
parts_map = defaultdict(list)
for p in staging.glob('*.jpg.b64.*'):
    m = re.match(r'^(.+\.jpg\.b64)\.(\d+)$', p.name)
    if m:
        parts_map[m.group(1)].append((int(m.group(2)), p))

targets = set(wholes) | set(parts_map)
for b64name in sorted(targets):
    if b64name in parts_map:
        chunks = sorted(parts_map[b64name], key=lambda x: x[0])
        text = ''.join(p.read_text() for _, p in chunks)
    else:
        text = wholes[b64name].read_text()
    name = b64name[:-4]
    out = root / name
    data = base64.b64decode(text.strip())
    if not data.startswith(b'\xff\xd8'):
        raise SystemExit(f'not a jpeg after decode: {b64name}')
    if out.exists() and out.read_bytes() == data:
        continue
    out.write_bytes(data)
    changed.append(str(out))
    print(f'wrote {out} ({len(data)} bytes)')

if not changed:
    print('no changes')
    raise SystemExit(0)

subprocess.check_call(['git', 'config', 'user.name', 'media-bot'])
subprocess.check_call(['git', 'config', 'user.email', 'bot@localhost'])
subprocess.check_call(['git', 'add', '--'] + changed)
subprocess.check_call(['git', 'commit', '-m', 'Decode staged assets'])
subprocess.check_call(['git', 'push'])
print('pushed', changed)
