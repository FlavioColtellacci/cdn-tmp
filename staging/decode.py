#!/usr/bin/env python3
"""Decode staging/*.jpg.b64 (or .jpg.b64.NN parts) into root *.jpg and commit if changed.

Soft-exit: incomplete chunks, bad base64, or non-JPEG never fail the Actions job
(so GitHub does not email workflow-failure noise).
"""
import base64, pathlib, subprocess, re, sys, traceback
from collections import defaultdict

root = pathlib.Path('.')
staging = root / 'staging'
changed = []
skipped = []

try:
    wholes = {p.name: p for p in staging.glob('*.jpg.b64')}
    parts_map = defaultdict(list)
    for p in staging.glob('*.jpg.b64.*'):
        m = re.match(r'^(.+\.jpg\.b64)\.(\d+)$', p.name)
        if m:
            parts_map[m.group(1)].append((int(m.group(2)), p))

    targets = set(wholes) | set(parts_map)
    for b64name in sorted(targets):
        try:
            if b64name in parts_map:
                chunks = sorted(parts_map[b64name], key=lambda x: x[0])
                idxs = [i for i, _ in chunks]
                # Incomplete set: missing 0..max contiguous parts → skip, do not fail
                if not idxs or idxs != list(range(idxs[0], idxs[-1] + 1)) or idxs[0] != 0:
                    skipped.append(f'incomplete parts: {b64name} idxs={idxs}')
                    continue
                text = ''.join(p.read_text() for _, p in chunks)
            else:
                text = wholes[b64name].read_text()

            name = b64name[:-4]  # strip .b64
            out = root / name
            raw = text.strip()
            if not raw or raw == 'PLACEHOLDER_WILL_REPLACE' or raw.startswith('PLACEHOLDER'):
                skipped.append(f'stub/placeholder: {b64name}')
                continue
            try:
                data = base64.b64decode(raw, validate=False)
            except Exception as e:
                skipped.append(f'bad base64: {b64name} ({e})')
                continue
            if not data.startswith(b'\xff\xd8'):
                skipped.append(f'not jpeg: {b64name} ({len(data)} bytes)')
                continue
            if out.exists() and out.read_bytes() == data:
                continue
            out.write_bytes(data)
            changed.append(str(out))
            print(f'wrote {out} ({len(data)} bytes)')
        except Exception as e:
            skipped.append(f'error {b64name}: {e}')
            continue

    for s in skipped:
        print('skip:', s)

    if not changed:
        print('no changes')
        sys.exit(0)

    subprocess.check_call(['git', 'config', 'user.name', 'media-bot'])
    subprocess.check_call(['git', 'config', 'user.email', 'bot@localhost'])
    subprocess.check_call(['git', 'add', '--'] + changed)
    subprocess.check_call(['git', 'commit', '-m', 'Decode staged assets'])
    subprocess.check_call(['git', 'push'])
    print('pushed', changed)
except Exception:
    # Never fail the job (avoids Proton failure emails)
    traceback.print_exc()
    print('soft-exit: decode aborted without failing the workflow')
    sys.exit(0)
