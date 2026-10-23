import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from offline_models import WAN_REPO, offline_environment, redirect_loader, wan_snapshot


class OfflineModelsTests(unittest.TestCase):
    def test_local_redirect_preserves_subclass_arguments_and_restores_on_error(self):
        class Base:
            @classmethod
            def from_pretrained(cls, name, *args, **kwargs):
                return cls, name, args, kwargs

        class UpstreamModel(Base):
            pass

        original = Base.__dict__['from_pretrained']
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            with redirect_loader(Base, Path('/pinned cache/revision')):
                cls, path, args, kwargs = UpstreamModel.from_pretrained(
                    WAN_REPO, 'extra', subfolder='transformer',
                    torch_dtype='float32', local_files_only=False)
                self.assertIs(cls, UpstreamModel)
                self.assertEqual(path, '/pinned cache/revision')
                self.assertEqual(args, ('extra',))
                self.assertEqual(kwargs, {'subfolder': 'transformer',
                                         'torch_dtype': 'float32', 'local_files_only': True})
                # Other repositories/local paths are not silently redirected.
                self.assertEqual(UpstreamModel.from_pretrained('/other/model'),
                                 (UpstreamModel, '/other/model', (), {}))
                raise RuntimeError('inference failed')
        self.assertIs(Base.__dict__['from_pretrained'], original)

    def test_nested_redirect_restores_outer_binding(self):
        class Base:
            @classmethod
            def from_pretrained(cls, name, **kwargs):
                return name

        original = Base.__dict__['from_pretrained']
        with redirect_loader(Base, '/outer'):
            with redirect_loader(Base, '/inner'):
                self.assertEqual(Base.from_pretrained(WAN_REPO), '/inner')
            self.assertEqual(Base.from_pretrained(WAN_REPO), '/outer')
        self.assertIs(Base.__dict__['from_pretrained'], original)

    def test_snapshot_uses_locked_revision_not_mutable_main(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / 'hf/hub/models--Wan-AI--Wan2.2-TI2V-5B-Diffusers'
            (repo / 'refs').mkdir(parents=True)
            (repo / 'refs/main').write_text('different-revision')
            snapshot = repo / 'snapshots/pinned-revision'
            snapshot.mkdir(parents=True)
            spec = {'assets': [{'repo': WAN_REPO, 'revision': 'pinned-revision'}]}
            with patch('offline_models.lock', return_value=spec):
                self.assertEqual(wan_snapshot(temp), snapshot)
                snapshot.rmdir()
                with self.assertRaises(FileNotFoundError):
                    wan_snapshot(temp)

    def test_offline_environment_removes_legacy_cache_overrides(self):
        old_names = ('TRANSFORMERS_CACHE', 'PYTORCH_TRANSFORMERS_CACHE',
                     'PYTORCH_PRETRAINED_BERT_CACHE')
        env = {name: '/wrong/cache' for name in old_names}
        env.update(HF_HUB_CACHE='/correct/cache', HF_HUB_OFFLINE='0')
        with patch.dict(os.environ, env, clear=True):
            offline_environment()
            self.assertTrue(all(name not in os.environ for name in old_names))
            self.assertEqual(os.environ['HF_HUB_CACHE'], '/correct/cache')
            self.assertEqual(os.environ['HF_HUB_OFFLINE'], '1')
            self.assertEqual(os.environ['TRANSFORMERS_OFFLINE'], '1')


if __name__ == '__main__':
    unittest.main()
