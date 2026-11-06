import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]

class DeliveryTests(unittest.TestCase):
    def test_experiment_matrix(self):
        spec = importlib.util.spec_from_file_location('runner', ROOT / 'run_experiments.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / 'data/formal_1000000').mkdir(parents=True)
            index = base / 'index/yfcc'
            index.parent.mkdir()
            calls = []
            def fake_run(command, env, check):
                self.assertTrue(check)
                self.assertNotIn('--index-prefix', command)  # unsupported by course adapter
                def arg(key):
                    return command[command.index(key) + 1]
                bucket, run_id = arg('--bucket'), arg('--run-id')
                dest = Path(arg('--run-root')) / 'results/gateann/formal_1000000' / bucket / run_id
                dest.mkdir(parents=True)
                with (dest / 'results.csv').open('w', newline='', encoding='utf-8') as f:
                    w = csv.DictWriter(f, fieldnames=['bucket', 'recall_percent'])
                    w.writeheader()
                    w.writerow({'bucket': bucket, 'recall_percent': '93'})
                calls.append((env['FVS_OPT_MODE'], bucket))
            # Real symlinks are unnecessary for this command/result contract test.
            argv = ['run_experiments.py', '--course-repo', str(base), '--repo', str(base),
                    '--dataset-root', str(base / 'data'), '--index-prefix', str(index),
                    '--output', str(base / 'out'), '--repeats', '1']
            with patch.object(sys, 'argv', argv), patch.object(mod.subprocess, 'run', side_effect=fake_run), \
                 patch.object(Path, 'symlink_to'), patch('builtins.print'):
                mod.main()
            self.assertEqual(len(calls), 15)
            with (base / 'out/optimization_results.csv').open(encoding='utf-8') as f:
                self.assertEqual(len(list(csv.DictReader(f))), 15)
            with patch.object(sys, 'argv', argv), patch('builtins.print'):
                with self.assertRaises(FileExistsError):
                    mod.main()  # never overwrite a prior experiment

    def test_fixed_source_patch(self):
        # Optional offline integration fixture: extracted pinned upstream archive.
        fixture = os.environ.get('FVS_SOURCE_FIXTURE')
        if not fixture:
            self.skipTest('Set FVS_SOURCE_FIXTURE to pinned source archive directory')
        import shutil
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'source'
            shutil.copytree(fixture, dest)
            subprocess.run(['git', 'init', str(dest)], check=True, capture_output=True)
            patch = str(ROOT / 'patches/gateann_adaptive.patch')
            subprocess.run(['git', '-C', str(dest), 'apply', '--check', patch], check=True)
            subprocess.run(['git', '-C', str(dest), 'apply', patch], check=True)
            subprocess.run(['git', '-C', str(dest), 'apply', '--reverse', '--check', patch], check=True)
            # Ensure no accidental loss of the mandatory IO drain or original branch.
            code = (dest / 'src/search/pipe_search.cpp').read_text(encoding='utf-8')
            self.assertIn('relaxed_monotonicity_l > 0 || adaptive', code)
            self.assertIn('while (!opt_stop && get_first_unvisited()', code)
            self.assertIn('if (adaptive && opt_config.tunnel_keep < nnbrs)', code)

    def test_hashes_match_fixture(self):
        fixture = os.environ.get('FVS_SOURCE_FIXTURE')
        if not fixture:
            self.skipTest('Source fixture not configured')
        import hashlib
        spec = importlib.util.spec_from_file_location('installer', ROOT / 'apply.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(len(mod.HASHES), 4)
        for name, digest in mod.HASHES.items():
            self.assertEqual(hashlib.sha256((Path(fixture) / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), digest)

if __name__ == '__main__':
    unittest.main()
