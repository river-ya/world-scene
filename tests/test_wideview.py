import copy
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from camera_paths import inverse, multiply, rotate
import gallery
import wideview


class WideViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = ROOT.parent/'world_scene_assets'
        if not (cls.assets/'data/worldscore-indoor-v1/images/002.jpg').is_file():
            raise unittest.SkipTest('external frozen development images unavailable')

    def test_all_scenes_preserve_inputs_and_expand_horizontal_field(self):
        self.assertEqual(set(wideview.PROFILES), set(range(4, 10)))
        self.assertEqual({yaw > 0 for _, yaw in wideview.PROFILES.values()}, {True, False})
        for index, (_, target) in wideview.PROFILES.items():
            original = gallery.build(index, self.assets)
            data = wideview.build(index, self.assets)
            anchor = original['cameras'][9]
            for key in ('image_prompt', 'text_prompt', 'resolution'):
                self.assertEqual(data[key], original[key])
            self.assertEqual(data['_showcase']['crop'], original['_showcase']['crop'])
            self.assertEqual(data['image_index'], 0)
            self.assertEqual(data['cameras'][0], anchor)
            self.assertTrue(55 <= abs(target) <= 65)
            self.assertGreater(abs(target), original['_gallery']['camera_profile_stats']['max_rotation_deg']+20)
            self.assertNotIn('_gallery', data)
            self.assertEqual(data['_camera_control']['reference_scale'], original['_gallery']['camera_profile_stats']['export_scale'])
            self.assertGreater(data['_camera_control']['reference_scale'], 0)
            for frame, camera in enumerate(data['cameras']):
                for key in ('position', 'fx', 'fy', 'cx', 'cy'):
                    self.assertEqual(camera[key], anchor[key])
                relative = multiply(inverse(anchor['quaternion']), camera['quaternion'])
                forward = rotate(relative, [0, 0, -1])
                angle = math.degrees(math.atan2(-forward[0], -forward[2]))
                self.assertAlmostEqual(angle, target*frame/23, places=8)
                for a, b in zip(rotate(relative, [0, 1, 0]), [0, 1, 0]):
                    self.assertAlmostEqual(a, b, places=8)
            self.assertEqual(gallery.build(index, self.assets), original)

    def test_indices_and_prepare_does_not_overwrite(self):
        self.assertEqual(wideview.task_indices('4-9%1'), list(range(4, 10)))
        self.assertEqual(wideview.task_indices('4,7%1'), [4, 7])
        for value in ('0-9%1', '3%1', '4,4%1', '9-4%1', '4-9', '4-9%0'):
            with self.assertRaises(ValueError): wideview.task_indices(value)
        for value in (3, 10, True, 4.0):
            with self.assertRaises(ValueError): wideview.build(value, self.assets)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'prepared'
            wideview.prepare(self.assets, 7, target)
            self.assertTrue((target/'wideview-07.json').is_file())
            with self.assertRaises(FileExistsError): wideview.prepare(self.assets, 7, target)

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('plyfile'), 'requires CPU torch and plyfile')
    def test_actual_upstream_generation_and_video_for_both_directions(self):
        for index in wideview.PROFILES:
            wideview.runtime_check(wideview.build(index, self.assets))

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('plyfile'), 'requires CPU torch and plyfile')
    def test_reject_wrong_direction_motion_anchor_and_scale(self):
        original = wideview.build(7, self.assets)
        for mutation in ('direction', 'position', 'anchor', 'scale', 'intrinsics'):
            data = copy.deepcopy(original)
            if mutation == 'direction':
                data['cameras'] = list(reversed(data['cameras']))
            elif mutation == 'position':
                data['cameras'][-1]['position'][0] += .1
            elif mutation == 'anchor': data['image_index'] = 9
            elif mutation == 'scale': data['_camera_control']['reference_scale'] = 0
            else: data['cameras'][-1]['fx'] *= 1.2
            with self.subTest(mutation=mutation), self.assertRaises((RuntimeError, ValueError)):
                wideview.runtime_check(data)


if __name__ == '__main__': unittest.main()
