"""Exercise submission with the batch script relocated as Slurm does."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SlurmTests(unittest.TestCase):
    def test_relocated_batch_script_for_all_stages(self):
        for stage in ('check', 'smoke', 'batch', 'showcase', 'viewcheck', 'studioview', 'gallery', 'angles', 'ui'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                code = root / 'release with spaces'
                (code / 'slurm').mkdir(parents=True)
                (code / 'tools').mkdir()
                (code / 'VERSION').write_text('0.1.2\n')
                for name in ('config.sh', 'submit.sh', 'job.sh'):
                    shutil.copy2(ROOT / 'slurm' / name, code / 'slurm' / name)
                # Stand-ins avoid importing CUDA or reading model assets.
                probe = ('import json, os, sys\n'
                         'with open(os.environ["SCENE_TEST_TRACE"], "a") as f:\n'
                         '    f.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                         'if sys.argv[1] == "preflight" and os.getenv("SCENE_TEST_FAIL_PREFLIGHT"):\n'
                         '    raise SystemExit("preflight failed")\n'
                         'if sys.argv[0].endswith(("showcase.py", "viewcheck.py", "studioview.py", "gallery.py", "angles.py")) and sys.argv[1] == "verify" and os.getenv("SCENE_TEST_FAIL_INPUTS"):\n'
                         '    raise SystemExit("showcase inputs failed")\n')
                for name in ('experiment.py', 'assets.py', 'showcase.py', 'viewcheck.py', 'studioview.py', 'gallery.py', 'angles.py'):
                    (code / 'tools' / name).write_text(probe)
                bin_dir = root / 'env' / 'bin'
                bin_dir.mkdir(parents=True)
                (bin_dir / 'python').symlink_to(sys.executable)
                nvidia = bin_dir / 'nvidia-smi'
                nvidia.write_text('#!/bin/sh\nprintf "mock GPU\\n"\n')
                nvidia.chmod(0o755)
                sbatch = bin_dir / 'sbatch'
                sbatch.write_text('#!' + sys.executable + '\n' + '''
import json, os, pathlib, shutil, subprocess, sys
root = pathlib.Path(os.environ['SCENE_TEST_ROOT'])
with (root / 'submissions.txt').open('a') as f:
    f.write('submitted\\n')
args = sys.argv[1:]
(root / 'sbatch-args.json').write_text(json.dumps(args))
spool = root / 'spool' / 'job12345'
spool.mkdir(parents=True)
script = spool / 'slurm_script'
shutil.copyfile(args[-2], script)
env = dict(os.environ, SLURM_JOB_ID='12345')
if args[-1] in ('batch', 'showcase', 'gallery', 'angles'):
    env.update(SLURM_ARRAY_JOB_ID='12345', SLURM_ARRAY_TASK_ID='3' if args[-1] == 'gallery' else '2')
cwd = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--chdir='))
result = subprocess.run(['bash', str(script), args[-1]], cwd=cwd,
                        env=env, capture_output=True, text=True)
(root / 'batch-result.json').write_text(json.dumps({
    'returncode': result.returncode, 'stderr': result.stderr}))
print('12345')
''')
                sbatch.chmod(0o755)
                env = {key: value for key, value in os.environ.items()
                       if not key.startswith(('SCENE_', 'SLURM_', 'SBATCH_'))}
                trace = root / 'trace.jsonl'
                env.update(DATA_ROOT=str(root / 'data'), SCENE_ENV=str(root / 'env'),
                           SCENE_TEST_ROOT=str(root), SCENE_TEST_TRACE=str(trace),
                           PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                           MEM='16G', CPUS='4', MAX_JOBS='2', DEPENDENCY='', ACCOUNT='', QOS='', NODE='')
                submitted = subprocess.run(['bash', 'slurm/submit.sh', stage],
                                           cwd=code, env=env, capture_output=True, text=True)
                self.assertEqual(submitted.returncode, 0, submitted.stderr)
                result = json.loads((root / 'batch-result.json').read_text())
                self.assertEqual(result['returncode'], 0, result['stderr'])
                args = json.loads((root / 'sbatch-args.json').read_text())
                self.assertIn('--export=ALL', args)
                self.assertIn('--mem=16G', args)
                self.assertIn('--cpus-per-task=4', args)
                self.assertFalse(any(arg.startswith(('--account=', '--qos=', '--nodelist=')) for arg in args))
                calls = [json.loads(line) for line in trace.read_text().splitlines()]
                expected = {'check': ['inspect', 'check'],
                            'smoke': ['inspect', 'preflight', 'check', 'verify', 'prepare', 'run'],
                            'batch': ['inspect', 'preflight', 'check', 'verify', 'prepare', 'run'],
                            'showcase': ['inspect', 'verify', 'preflight', 'check', 'verify', 'prepare', 'run'],
                            'viewcheck': ['inspect', 'preflight', 'verify', 'check', 'verify', 'prepare', 'run'],
                            'studioview': ['inspect', 'preflight', 'verify', 'check', 'verify', 'prepare', 'run'],
                            'gallery': ['inspect', 'verify', 'preflight', 'verify', 'check', 'verify', 'prepare', 'run'],
                            'angles': ['inspect', 'verify', 'preflight', 'verify', 'check', 'verify', 'prepare', 'run'],
                            'ui': ['inspect', 'preflight', 'check', 'verify', 'ui']}[stage]
                self.assertEqual([call[0] for call in calls], expected)
                if stage == 'batch':
                    self.assertIn('studio_b0', calls[-2])
                if stage == 'showcase':
                    self.assertIn('--array=2-9%1', args)
                    self.assertIn('--index', calls[-2])
                    self.assertIn('showcase-02-12345-2', calls[-1])
                if stage in ('viewcheck', 'studioview'):
                    self.assertFalse(any(a.startswith('--array=') for a in args))
                    self.assertIn('--runtime', calls[2])
                    self.assertIn('--runtime', calls[-2])
                    self.assertIn(('kitchen-small' if stage == 'viewcheck' else 'kitchen-studio') + '-12345-0', calls[-1])
                if stage == 'gallery':
                    self.assertIn('--array=3-9%1', args)
                    self.assertIn('--runtime', calls[3])
                    self.assertIn('--runtime', calls[-2])
                    self.assertIn('gallery-03-12345-3', calls[-1])
                if stage == 'angles':
                    self.assertIn('--array=0-2%1', args)
                    self.assertIn('--runtime', calls[3])
                    self.assertIn('--runtime', calls[-2])
                    self.assertIn('angles-living-left-75-12345-2', calls[-1])
                state = root / 'data/state/world_scene/v0.1.2'
                self.assertEqual((state / f'{stage}.jobid').read_text(), '12345\n')
                self.assertEqual(list((root / 'data/world_scene_assets/tmp').iterdir()), [])
                if stage != 'check':
                    env['SCENE_TEST_FAIL_PREFLIGHT'] = '1'
                    failed = subprocess.run(['bash', 'slurm/submit.sh', stage],
                                            cwd=code, env=env, capture_output=True, text=True)
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertEqual((root / 'submissions.txt').read_text(), 'submitted\n')
                    self.assertEqual((state / f'{stage}.jobid').read_text(), '12345\n')
                if stage in ('showcase', 'viewcheck', 'studioview', 'gallery', 'angles'):
                    env.pop('SCENE_TEST_FAIL_PREFLIGHT', None)
                    env['SCENE_TEST_FAIL_INPUTS'] = '1'
                    failed = subprocess.run(['bash', 'slurm/submit.sh', stage],
                                            cwd=code, env=env, capture_output=True, text=True)
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertEqual((root / 'submissions.txt').read_text(), 'submitted\n')
                    self.assertEqual((state / f'{stage}.jobid').read_text(), '12345\n')
                if stage in ('viewcheck', 'studioview', 'gallery', 'angles'):
                    env.pop('SCENE_TEST_FAIL_INPUTS', None)
                    env['SEED'] = '1'
                    failed = subprocess.run(['bash', 'slurm/submit.sh', stage],
                                            cwd=code, env=env, capture_output=True, text=True)
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertEqual((root / 'submissions.txt').read_text(), 'submitted\n')


if __name__ == '__main__':
    unittest.main()
