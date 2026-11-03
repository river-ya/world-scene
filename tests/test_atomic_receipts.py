from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import common
import assets


class AtomicReceiptTests(unittest.TestCase):
    def test_concurrent_writers_publish_complete_json_with_distinct_temps(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'verified-models.json'
            payloads = [{'writer': i, 'text': '校验记录'*1000*(i+1)} for i in range(6)]
            barrier = threading.Barrier(len(payloads), timeout=10)
            replace = common.os.replace
            sources = []
            def simultaneous_replace(src, dst):
                sources.append(Path(src))
                barrier.wait()
                replace(src, dst)
            with patch.object(common.os, 'replace', side_effect=simultaneous_replace):
                with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
                    futures = [pool.submit(common.write_json, dest, value) for value in payloads]
                    for f in futures: f.result(timeout=15)
            self.assertEqual(len(set(sources)), len(payloads))
            self.assertTrue(all(p.parent == dest.parent for p in sources))
            self.assertIn(json.loads(dest.read_text()), payloads)
            self.assertEqual(list(Path(tmp).iterdir()), [dest])

    def test_failed_replace_and_bad_json_preserve_old_receipt_and_clean_temps(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'receipt.json'
            common.write_json(dest, {'old': True})
            before = dest.read_bytes()
            with patch.object(common.os, 'replace', side_effect=OSError('injected failure')):
                with self.assertRaises(OSError): common.write_json(dest, {'new': True})
            self.assertEqual(dest.read_bytes(), before)
            with self.assertRaises(TypeError): common.write_json(dest, object())
            self.assertEqual(dest.read_bytes(), before)
            self.assertEqual(list(Path(tmp).iterdir()), [dest])

    def test_second_process_refuses_full_verify_while_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (root/'.verify-models.lock').open('a') as guard:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
                code = 'import sys;sys.path.insert(0,sys.argv[1]);from assets import verify;verify(sys.argv[2],"models")'
                result = subprocess.run([sys.executable, '-B', '-c', code, str(common.ROOT/'tools'), tmp], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('完整校验正在运行', result.stderr)
                # Quick checks are read-only and do not wait behind a full scan.
                with patch.object(assets, '_verify', return_value='quick') as verify:
                    self.assertEqual(assets.verify(root, 'models', quick=True), 'quick')
                    verify.assert_called_once_with(root, 'models', quick=True)
            # Lock ownership, not existence of the persistent file, controls access.
            with patch.object(assets, '_verify', side_effect=RuntimeError('scan failed')):
                with self.assertRaisesRegex(RuntimeError, 'scan failed'):
                    assets.verify(root, 'models')
            with patch.object(assets, '_verify', return_value='complete'):
                self.assertEqual(assets.verify(root, 'models'), 'complete')


if __name__ == '__main__': unittest.main()
