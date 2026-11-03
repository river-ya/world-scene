"""Relocated matched-input job: path propagation, seed and cleanup; no GPU."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MatchedJobTests(unittest.TestCase):
    def test_relocated_job_uses_frozen_inputs_and_cleans_on_success_and_failure(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                code = root/'release with spaces'
                (code/'slurm').mkdir(parents=True)
                (code/'tools').mkdir()
                (code/'examples/paired-room40').mkdir(parents=True)
                (code/'VERSION').write_text('0.10.1\n')
                shutil.copy2(ROOT/'slurm/config.sh',code/'slurm/config.sh')
                script = root/'spool-copy.sh'
                shutil.copy2(ROOT/'slurm/matched_job.sh',script)
                probe = (
                    'import json,os,sys\n'
                    'with open(os.environ["PAIR_TEST_TRACE"],"a") as f:\n'
                    ' f.write(json.dumps(sys.argv[1:])+"\\n")\n'
                    'if sys.argv[1]=="run" and os.environ["PAIR_TEST_FAIL"]=="1": raise SystemExit(9)\n')
                for name in ('experiment.py','assets.py'):
                    (code/'tools'/name).write_text(probe)
                envdir = root/'env/bin'
                envdir.mkdir(parents=True)
                (envdir/'python').symlink_to(sys.executable)
                trace = root/'calls.jsonl'
                env = dict(os.environ,SCENE_CODE=str(code),SCENE_ENV=str(envdir.parent),
                           DATA_ROOT=str(root/'data'),SCENE_ASSETS=str(root/'data/assets'),
                           SCENE_LOGS=str(root/'logs'),SCENE_RUNS=str(root/'runs'),
                           SLURM_JOB_ID='98765',PAIR_TEST_TRACE=str(trace),
                           PAIR_TEST_FAIL='1' if fail else '0')
                result = subprocess.run(['bash',str(script)],cwd=root,env=env,
                                        capture_output=True,text=True)
                self.assertEqual(result.returncode,9 if fail else 0,result.stderr)
                calls = [json.loads(line) for line in trace.read_text().splitlines()]
                self.assertEqual([v[0] for v in calls],['check','verify','run'])
                self.assertIn(str(code/'examples/paired-room40'),calls[-1])
                self.assertIn('matched-room40-98765',calls[-1])
                self.assertEqual(calls[-1][-2:],['--seed','0'])
                self.assertEqual(list((root/'data/assets/tmp').iterdir()),[])


if __name__ == '__main__':
    unittest.main()
