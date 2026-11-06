#!/usr/bin/env python3
"""Median/min/max by variant and bucket; report recall threshold failures."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

def main():
    p = argparse.ArgumentParser()
    p.add_argument('results', type=Path)
    a = p.parse_args()
    groups = defaultdict(list)
    with a.results.open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            groups[row['variant'], row['bucket']].append(row)
    metrics = ['recall_percent', 'mean_latency_us', 'mean_ios', 'filter_skips',
               'tunnel_time_us', 'io_time_us', 'process_time_us', 'peak_rss_kb']
    dest = a.results.with_name('optimization_summary.csv')
    with dest.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['variant', 'bucket', 'repeats', 'all_recall_ge90'] +
                   [m + '_' + stat for m in metrics for stat in ('median', 'min', 'max')])
        for (variant, bucket), rows in sorted(groups.items()):
            values = [variant, bucket, len(rows), all(float(r['recall_percent']) >= 90 for r in rows)]
            for m in metrics:
                v = [float(r[m]) for r in rows if r.get(m, '') != '']
                values.extend([median(v), min(v), max(v)] if v else ['', '', ''])
            w.writerow(values)
    print(dest)

if __name__ == '__main__':
    main()
