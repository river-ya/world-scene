import copy
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import angles
from camera_paths import inverse, multiply, rotate
import gallery


class AngleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = ROOT.parent/'world_scene_assets'
        if not (cls.assets/'data/worldscore-indoor-v1/images/001.jpg').is_file():
            raise unittest.SkipTest('external frozen living-room image unavailable')

    def test_same_frozen_image_text_intrinsics_and_only_yaw_changes(self):
        original = gallery.build(3, self.assets)
        anchor = original['cameras'][9]
        all_data = [angles.build(i, self.assets) for i in range(3)]
        for i, data in enumerate(all_data):
            for key in ('image_prompt', 'text_prompt', 'resolution'):
                self.assertEqual(data[key], original[key])
            self.assertEqual(data['image_index'], 0)
            self.assertEqual(data['cameras'][0], anchor)
            self.assertEqual(data['_showcase']['split'], 'dev')
            self.assertEqual(data['_showcase']['crop'], original['_showcase']['crop'])
            self.assertEqual(data['_camera_control'], all_data[0]['_camera_control'])
            self.assertGreater(data['_camera_control']['reference_scale'], 0)
            self.assertNotIn('_gallery', data)
            for frame, c in enumerate(data['cameras']):
                for key in ('position', 'fx', 'fy', 'cx', 'cy'):
                    self.assertEqual(c[key], anchor[key])
                relative = multiply(inverse(anchor['quaternion']), c['quaternion'])
                forward = rotate(relative, [0, 0, -1])
                yaw = math.atan2(-forward[0], -forward[2])*180/math.pi
                self.assertAlmostEqual(yaw, angles.ANGLES[i]*frame/23, places=8)
                up = rotate(relative, [0, 1, 0])
                for a, b in zip(up, [0, 1, 0]):
                    self.assertAlmostEqual(a, b, places=8)
        self.assertEqual(gallery.build(3, self.assets), original)

    def test_subset_and_invalid_indices(self):
        self.assertEqual(angles.task_indices('0-2%1'), [0, 1, 2])
        self.assertEqual(angles.task_indices('1,2%1'), [1, 2])
        for bad in ('0-3%1', '3%1', '0,0%1', '2-0%1', '0-2', '0-2%0'):
            with self.assertRaises(ValueError):
                angles.task_indices(bad)
        for bad in (-1, 3, True, 0.0):
            with self.assertRaises(ValueError):
                angles.build(bad, self.assets)

    def test_prepare_portable_and_refuses_overwrite(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'inputs'
            angles.prepare(self.assets, 2, output)
            data = json.loads((output/'angles-living-left-75.json').read_text())
            self.assertTrue(data['image_prompt'].startswith('data:image/jpeg;base64,'))
            self.assertEqual(data['_angles']['max_yaw_deg'], 75)
            with self.assertRaises(FileExistsError):
                angles.prepare(self.assets, 2, output)

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('plyfile'), 'requires CPU torch and plyfile')
    def test_actual_upstream_dense_cameras_and_rejects_wrong_geometry(self):
        for i in range(3):
            angles.runtime_check(angles.build(i, self.assets))
        data = angles.build(0, self.assets)
        bad = copy.deepcopy(data)
        bad['cameras'][-1]['position'][0] += .1
        with self.assertRaises(RuntimeError):
            angles.runtime_check(bad)
        bad = copy.deepcopy(data)
        bad['_angles']['max_yaw_deg'] = 45
        with self.assertRaises(RuntimeError):
            angles.runtime_check(bad)


if __name__ == '__main__':
    unittest.main()
