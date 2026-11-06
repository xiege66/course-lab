#!/usr/bin/env python3
"""Run isolated, randomized paired ablations through the unchanged course adapter."""
import argparse
import csv
import datetime
import json
import os
from pathlib import Path
import random
import subprocess
import sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--course-repo', type=Path, required=True)
    p.add_argument('--repo', type=Path, required=True, help='patched GateANN')
    p.add_argument('--dataset-root', type=Path, required=True)
    p.add_argument('--index-prefix', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True, help='new dedicated output directory')
    p.add_argument('--tier', default='formal', choices=['formal', 'debug'])
    p.add_argument('--repeats', type=int, default=5)
    p.add_argument('--seed', type=int, default=2026)
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if a.repeats < 1:
        p.error('--repeats must be positive')
    if a.index_prefix.name != 'yfcc':
        p.error('Course adapter requires an index prefix named yfcc')
    tiers = sorted(a.dataset_root.resolve().glob(a.tier + '_*'))
    if len(tiers) != 1:
        p.error('Expected exactly one dataset tier directory')
    cfg = {
        'FVS_OPT_MIN_L': '320', 'FVS_OPT_MAX_L': '5120',
        'FVS_OPT_TARGET': '32', 'FVS_OPT_PQ_MARGIN': '1.25',
    }
    # No tuning from ground truth. Use held-out queries if changing these settings.
    variants = [('fixed320', 'off', 320, 32), ('fixed5120', 'off', 5120, 32),
                ('selectivity', 'selectivity', 320, 32),
                ('adaptive', 'adaptive', 320, 32),
                ('adaptive_prune', 'adaptive', 320, 16)]
    jobs = []
    rng = random.Random(a.seed)
    for repeat in range(1, a.repeats + 1):
        block = [(repeat, bucket, *v) for bucket in ('low', 'medium', 'high') for v in variants]
        rng.shuffle(block)
        jobs.extend(block)
    manifest = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'arguments': {k: str(v) for k, v in vars(a).items()}, 'config': cfg, 'jobs': jobs,
                'cache_policy': 'OS cache uncontrolled; randomized paired blocks; hot cache disabled'}
    if not a.dry_run:
        a.output.mkdir(parents=True, exist_ok=False)
        (a.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        for name, _, _, _ in variants:
            link = a.output / name / 'indices/gateann' / tiers[0].name
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(a.index_prefix.resolve().parent, target_is_directory=True)
    records = []
    for repeat, bucket, name, mode, budget, keep in jobs:
        run_id = f'{name}-r{repeat}'
        command = [sys.executable, str(a.course_repo.resolve() / 'adapters/gateann_adapter.py'),
                   'search', '--repo', str(a.repo.resolve()),
                   '--dataset-root', str(a.dataset_root.resolve()), '--tier', a.tier,
                   '--run-root', str(a.output.resolve() / name),
                   '--threads', '1', '--beamwidth', '8', '--k', '10',
                   '--bucket', bucket, '--L', str(budget), '--full-adj-neighbors', '32',
                   '--cache-budget', '0', '--run-id', run_id]
        env = {**os.environ, **cfg, 'FVS_OPT_MODE': mode, 'FVS_OPT_TUNNEL_KEEP': str(keep)}
        print(name, bucket, run_id, command, flush=True)
        if a.dry_run:
            continue
        subprocess.run(command, env=env, check=True)
        found = list((a.output / name / 'results/gateann').glob(f'*/{bucket}/{run_id}/results.csv'))
        if len(found) != 1:
            raise RuntimeError(f'Expected one result file, found {found}')
        with found[0].open(encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                records.append({'variant': name, 'repeat': repeat, **row})
        # Persist each completed job; failures preserve evidence and stop the sweep.
        with (a.output / 'optimization_results.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    if not a.dry_run:
        print('Completed:', a.output / 'optimization_results.csv')

if __name__ == '__main__':
    main()
