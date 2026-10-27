# -*- coding: utf-8 -*-
"""Recycle-bin forensics + duplicate-archive check (Windows, read-only).

Two modes, both answering "is this big number one thing or a pile of junk":

  rb  <drive-root> [--out x.json]
      Read $I* metadata in <drive>:\\$RECYCLE.BIN\\S-1-5-* so deleted items get
      a real original path / delete date / size. $R* entries without a matching
      $I mean the metadata was pruned (whole-folder delete, cleaner tool): report
      them by $R name plus their largest children (pkgs/Library/Lib == a deleted
      conda env).

  zip <archive> <dir> [--out x.json]
      Leaf-name coverage: how many files under <dir> appear in <archive>. All of
      them covered + archive much bigger than the dir == the archive is a full
      backup of an already-extracted copy; report both sides and let the user pick.

Console output is ASCII-only on purpose: Chinese paths through git-bash pipes are
lossy. Anything worth reading again goes into the --out JSON (utf-8).
"""
import json
import os
import sys
import zipfile
from datetime import datetime, timedelta


def dir_size(path):
    total = 0
    stack = [path]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                        elif e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def filetime_to_str(ft):
    if not ft or ft <= 0:
        return None
    try:
        dt = datetime(1601, 1, 1) + timedelta(microseconds=ft / 10)
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return None


def parse_i_file(path):
    """$I layout: 0 hdr(8) | 8 size Int64 | 16 FILETIME Int64 | 24 pathlen Int32 | 28 path UTF-16LE."""
    try:
        with open(path, 'rb') as f:
            b = f.read(4096)
    except OSError:
        return None
    if len(b) < 28:
        return None
    size = int.from_bytes(b[8:16], 'little', signed=True)
    ft = int.from_bytes(b[16:24], 'little', signed=True)
    plen = int.from_bytes(b[24:28], 'little', signed=True)
    if 0 < plen <= len(b) - 28:
        original = b[28:28 + plen].decode('utf-16-le', 'replace').rstrip('\x00')
    else:
        original = '?'
    return {
        'i_file': os.path.basename(path),
        'bytes': size,
        'deleted': filetime_to_str(ft),
        'original_path': original,
    }


def rb_scan(drive_root):
    rb = os.path.join(drive_root, '$RECYCLE.BIN')
    items, orphans = [], []
    if not os.path.isdir(rb):
        return items, orphans, rb
    for sid in os.listdir(rb):
        sdir = os.path.join(rb, sid)
        if not os.path.isdir(sdir):
            continue
        try:
            names = os.listdir(sdir)
        except OSError:
            continue
        known = {}
        for name in names:
            if not name.startswith('$I'):
                continue
            meta = parse_i_file(os.path.join(sdir, name))
            if meta:
                meta['sid'] = sid
                items.append(meta)
                known[name[2:]] = meta
        for name in names:
            if not name.startswith('$R') or name[2:] in known:
                continue
            p = os.path.join(sdir, name)
            try:
                if os.path.isdir(p):
                    size = dir_size(p)
                    children = []
                    with os.scandir(p) as it:
                        for e in it:
                            try:
                                csize = dir_size(e.path) if e.is_dir(follow_symlinks=False) \
                                    else e.stat(follow_symlinks=False).st_size
                                children.append({'name': e.name, 'bytes': csize})
                            except OSError:
                                continue
                    children.sort(key=lambda c: -c['bytes'])
                else:
                    size = os.path.getsize(p)
                    children = []
            except OSError:
                size = 0
                children = []
            orphans.append({
                'r_file': name, 'sid': sid, 'bytes': size,
                'top_children': children[:12],
            })
    items.sort(key=lambda x: -x['bytes'])
    orphans.sort(key=lambda x: -x['bytes'])
    return items, orphans, rb


def zip_coverage(zip_path, dir_path):
    with zipfile.ZipFile(zip_path) as z:
        entries = [n for n in z.namelist() if not n.endswith('/')]
    leaves = set(n.replace('\\', '/').rsplit('/', 1)[-1] for n in entries)
    files = []
    stack = [dir_path]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            files.append(e.name)
                        elif e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                    except OSError:
                        continue
        except OSError:
            continue
    covered = sum(1 for f in files if f in leaves)
    return {
        'archive': zip_path,
        'archive_bytes': os.path.getsize(zip_path),
        'archive_files': len(entries),
        'dir': dir_path,
        'dir_bytes': dir_size(dir_path),
        'dir_files': len(files),
        'covered': covered,
        'not_in_archive': len(files) - covered,
    }


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    out = None
    if '--out' in argv:
        i = argv.index('--out')
        out = argv[i + 1]
        del argv[i:i + 2]
    mode = argv[0]

    if mode == 'rb' and len(argv) >= 2:
        items, orphans, rb = rb_scan(argv[1])
        result = {'recycle_bin': rb, 'items': items, 'orphans': orphans}
        print('recycle_bin=%s items=%d orphans=%d' % (rb, len(items), len(orphans)))
        for it in items[:15]:
            print('  I %8.2f GB  del %s  %s' % (it['bytes'] / 2 ** 30, it['deleted'] or '?', it['i_file']))
        for o in orphans[:15]:
            print('  R %8.2f GB  %s  top=%s' % (
                o['bytes'] / 2 ** 30, o['r_file'],
                ','.join(c['name'] for c in o['top_children'][:4])))
        if out:
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
        return 0

    if mode == 'zip' and len(argv) >= 3:
        result = zip_coverage(argv[1], argv[2])
        verdict = ('ARCHIVE IS A FULL BACKUP OF THE EXTRACTED DIR'
                   if result['not_in_archive'] == 0 and result['dir_files'] > 0
                   else 'partial overlap - inspect before proposing deletion')
        print('zip %.2f GB / %d files  dir %.2f GB / %d files  covered %d  missing %d  -> %s' % (
            result['archive_bytes'] / 2 ** 30, result['archive_files'],
            result['dir_bytes'] / 2 ** 30, result['dir_files'],
            result['covered'], result['not_in_archive'], verdict))
        if out:
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
        return 0

    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
