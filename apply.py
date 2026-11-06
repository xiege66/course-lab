#!/usr/bin/env python3
"""Install only on the course-pinned source. Idempotent, no reset or checkout."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

COMMIT = '71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd'
# Files are checked against hashes of the actual fixed-commit source archive.
HASHES = {'include/utils/spmat_filter_store.h': '56ba5e7bced3d3aed444b154926a450069ad5f2a02ed9ae193eccb158c586fd8', 'src/search/pipe_search.cpp': '8880a15a8beb6c405e43da4047977c04833f4e8184e10fe60f59206bb32c7185', 'include/utils/percentile_stats.h': 'ec43167d3fc9111f5bc240f0e1cfefe11b962192f5511aaaf87597f6fc5ae57b', 'tests/search_disk_index_yfcc.cpp': '072ad97803b2cc6053e569d43fad556e115f14cd6b00ba9cdfdeff6793ce452c'}

def run(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    a = p.parse_args()
    repo = a.repo.resolve()
    root = Path(__file__).resolve().parent
    head = run(repo, 'rev-parse', 'HEAD')
    if head.returncode or head.stdout.strip() != COMMIT:
        raise SystemExit('Expected GateANN commit ' + COMMIT + '; refusing to modify source')
    patch = root / 'patches/gateann_adaptive.patch'
    installed = run(repo, 'apply', '--reverse', '--check', str(patch)).returncode == 0
    if not installed:
        for name, expected in HASHES.items():
            actual = hashlib.sha256((repo / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            if actual != expected:
                raise SystemExit('Modified or incompatible source: ' + name)
        check = run(repo, 'apply', '--check', str(patch))
        if check.returncode:
            raise SystemExit(check.stderr)
    target = repo / 'include/utils/adaptive_filter_policy.h'
    content = (root / 'include/adaptive_filter_policy.h').read_bytes()
    if target.exists() and target.read_bytes() != content:
        raise SystemExit('Existing policy header differs; refusing overwrite: ' + str(target))
    if not installed:
        result = run(repo, 'apply', str(patch))
        if result.returncode:
            raise SystemExit(result.stderr)
    shutil.copyfile(root / 'include/adaptive_filter_policy.h', target)
    print('Optimization installed' if not installed else 'Optimization already installed')

if __name__ == '__main__':
    main()
