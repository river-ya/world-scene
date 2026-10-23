import copy
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera_control
import showcase
import viewcheck


class ViewcheckTests(unittest.TestCase):
    def test_geometry_and_unchanged_conditions(self):
        # Use the real frozen source image when available; no model dependencies.
        assets = Path(__file__).resolve().parents[2]/'world_scene_assets'
        if not (assets/'data/worldscore-indoor-v1/images/000.jpg').exists():
            self.skipTest('local frozen dev image unavailable; fixture geometry test below still runs')
        baseline = showcase.build(2, assets)
        data = viewcheck.build(assets)
        self.assert_geometry(baseline, data)

    def assert_geometry(self, baseline, data):
        for key in ('image_prompt', 'text_prompt', 'image_index', 'resolution'):
            self.assertEqual(data[key], baseline[key])
        index = data['image_index']
        anchor = baseline['cameras'][index]
        self.assertEqual(data['cameras'][index], anchor)
        scale = data['_camera_control']['reference_scale']
        self.assertGreater(scale, 0.1)  # Prevent epsilon-driven, near-zero export scale.
        q = viewcheck.unit(anchor['quaternion'])
        angles, distances = [], []
        for c, old in zip(data['cameras'], baseline['cameras']):
            for key in ('fx', 'fy', 'cx', 'cy'):
                self.assertEqual(c[key], old[key])
            dot = abs(sum(x*y for x, y in zip(q, viewcheck.unit(c['quaternion']))))
            angles.append(math.degrees(2*math.acos(min(1, dot))))
            # Rigid rotation in upstream normalization preserves these distances.
            distances.append(math.dist(c['position'], anchor['position'])/(scale+0.01))
        self.assertAlmostEqual(max(angles), 5, places=7)
        self.assertAlmostEqual(max(distances), 0.1, places=10)
        self.assertEqual(len(data['cameras']), 24)
        self.assertEqual(data['_viewcheck']['baseline_input_sha256'], viewcheck.BASELINE_INPUT_SHA256)
        # Without the override, the short path would be magnified again.
        native_scale = max(math.dist(c['position'], data['cameras'][0]['position']) for c in data['cameras'])
        native_from_anchor = max(math.dist(c['position'], anchor['position']) for c in data['cameras'])/(native_scale+0.01)
        self.assertGreater(native_from_anchor, 0.4)

    def test_portable_geometry_and_reference_stability(self):
        # Geometry remains testable inside release archives without external assets.
        import hashlib
        baseline = showcase.official(3)
        baseline['_showcase'] = {'camera_policy': 'fixture'}
        digest = hashlib.sha256((json.dumps(baseline, ensure_ascii=False, indent=2)+'\n').encode()).hexdigest()
        original = copy.deepcopy(baseline)
        with patch.object(showcase, 'build', return_value=baseline), patch.object(viewcheck, 'BASELINE_INPUT_SHA256', digest):
            data = viewcheck.build('/unused')
            self.assert_geometry(baseline, data)
        self.assertEqual(baseline, original)
        with patch.object(showcase, 'build', return_value=baseline):
            with self.assertRaisesRegex(ValueError, '70462'):
                viewcheck.build('/unused')

    def test_scope_render_scale_and_exception_restoration(self):
        calls = []
        def original(cameras, **kwargs):
            calls.append(kwargs)
            return 'result'
        module = SimpleNamespace(normalize_cameras=original)
        class Cameras:
            shape = (1, 24, 11)
            def new_full(self, shape, value):
                return ('tensor', shape, value)
        control = {'policy': camera_control.POLICY, 'reference_scale': 4.2}
        cached_app = SimpleNamespace()
        with patch.dict(sys.modules, {'app': cached_app}):
            with self.assertRaisesRegex(RuntimeError, 'deliberate'):
                with camera_control.fixed_camera_scale(control, module):
                    cached_app.normalize_cameras = module.normalize_cameras
                    self.assertEqual(module.normalize_cameras(Cameras(), True, n_frame=24), 'result')
                    self.assertEqual(calls[-1]['T_norm'], ('tensor', (1, 1, 1), 4.2))
                    self.assertTrue(calls[-1]['return_meta'])
                    marker, reference = object(), object()
                    module.normalize_cameras(Cameras(), ref_w2c=reference, T_norm=marker)
                    self.assertIs(calls[-1]['T_norm'], marker)
                    self.assertIs(calls[-1]['ref_w2c'], reference)
                    raise RuntimeError('deliberate')
            self.assertIs(module.normalize_cameras, original)
            self.assertIs(cached_app.normalize_cameras, original)
        with camera_control.fixed_camera_scale(None, module):
            self.assertIs(module.normalize_cameras, original)

    def test_protocol_validation_and_mixed_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = root/'a.json'
            a.write_text('{}')
            self.assertIsNone(camera_control.input_control(root))
            control = {'policy': camera_control.POLICY, 'reference_scale': 3.0}
            a.write_text(json.dumps({'_camera_control': control}))
            self.assertEqual(camera_control.input_control(root), control)
            for value in (0, -1, float('nan'), float('inf'), True, '3'):
                a.write_text(json.dumps({'_camera_control': {**control, 'reference_scale': value}}))
                with self.assertRaises(ValueError):
                    camera_control.input_control(root)
            a.write_text(json.dumps({'_camera_control': control}))
            (root/'b.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, '混用'):
                camera_control.input_control(root)


if __name__ == '__main__':
    unittest.main()
