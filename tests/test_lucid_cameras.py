import ast
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import lucid_cameras as cameras
import lucid_inputs as inputs
from camera_control import fixed_camera_scale
from camera_paths import inverse, multiply, rotate


ASSETS = ROOT.parent/'world_scene_assets'


class LucidYawTests(unittest.TestCase):
    def test_all_ten_angles_preserve_source_and_are_diverse_and_continuous(self):
        self.assertEqual(set(cameras.PROFILES), set(range(10)))
        self.assertEqual(len({abs(yaw) for _, yaw in cameras.PROFILES.values()}), 10)
        self.assertEqual({yaw > 0 for _, yaw in cameras.PROFILES.values()}, {True, False})
        for index, (_, target) in cameras.PROFILES.items():
            original = inputs.source_input(index, ASSETS)
            snapshot = copy.deepcopy(original)
            data = cameras.build(index, original)
            anchor = original['cameras'][original['image_index']]
            for field in ('image_prompt','text_prompt','resolution'):
                self.assertEqual(data[field], original[field])
            self.assertEqual(data['cameras'][0], anchor)
            self.assertEqual(data['image_index'], 0)
            self.assertNotIn('_gallery', data)
            previous = 0.
            for frame, c in enumerate(data['cameras']):
                for field in ('position','fx','fy','cx','cy'):
                    self.assertEqual(c[field], anchor[field])
                q = multiply(inverse(anchor['quaternion']), c['quaternion'])
                forward = rotate(q, [0,0,-1])
                yaw = math.degrees(math.atan2(-forward[0], -forward[2]))
                self.assertAlmostEqual(yaw, cameras.yaw_at(index, frame), places=8)
                self.assertLessEqual(abs(yaw-previous), 5)
                self.assertGreaterEqual((yaw-previous)*target, -1e-8)
                self.assertAlmostEqual(forward[1], 0, places=8)
                previous = yaw
            self.assertAlmostEqual(previous, target, places=8)
            self.assertEqual(original, snapshot)
            self.assertLess(abs(cameras.PROFILES[4][1]), abs(cameras.PROFILES[3][1]))

    def test_invalid_indices_and_missing_reference_scale(self):
        original = inputs.source_input(1, ASSETS)
        for index in (-1,10,True,1.0):
            with self.assertRaises(ValueError): cameras.build(index, original)
        flat = cameras.build(1, original)
        with self.assertRaises(ValueError): inputs.relative_cameras(flat['cameras'], 0)
        for scale in (0,-1,True,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                inputs.relative_cameras(flat['cameras'], 0, scale)


@unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('PIL'),
                     'requires numpy and Pillow')
class LucidYawIntegrationTests(unittest.TestCase):
    def test_all_cases_actual_cv_poses_dense_render_and_portable_inputs(self):
        import numpy as np
        for index, (_, target) in cameras.PROFILES.items():
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                p = inputs.prepare(index, ASSETS, Path(temp)/'inputs')
                source = json.loads((Path(temp)/'inputs/source.json').read_text())
                flash = json.loads((Path(temp)/'inputs/flashworld.json').read_text())
                self.assertEqual(p['protocol'], 'lucid-flash-inputs-v2')
                self.assertEqual(p['generation_order'], list(range(24)))
                self.assertEqual(flash['_camera_control'], p['camera_control'])
                self.assertEqual(flash['image_index'], 0)
                self.assertEqual(flash['text_prompt'], source['text_prompt'])
                for k in ('fx','fy','cx','cy'):
                    self.assertAlmostEqual(flash['cameras'][0][k], p['cameras'][0][k])
                poses = inputs.cv_w2c(p['cameras'])
                dense = inputs.cv_w2c(p['render_cameras'])
                np.testing.assert_allclose(poses[0], np.eye(4), atol=1e-6)
                np.testing.assert_allclose(dense[::15], poses, atol=1e-6)
                np.testing.assert_allclose(poses[:,:3,3], 0, atol=1e-7)
                np.testing.assert_allclose(np.linalg.det(dense[:,:3,:3]), 1, atol=1e-6)
                theta = math.radians(target)
                # Independent CV w2c reference, including the GL/CV handed-axis flip.
                expected = np.array([[math.cos(theta),0,math.sin(theta)],
                                     [0,1,0],[-math.sin(theta),0,math.cos(theta)]])
                np.testing.assert_allclose(poses[-1,:3,:3], expected, atol=1e-6)
                # A positive GL yaw really looks left in the local CV world.
                forward = np.linalg.inv(poses[-1])[:3,:3] @ [0,0,1]
                self.assertAlmostEqual(math.degrees(math.atan2(-forward[0], forward[2])), target, places=5)

    def test_reject_direction_zoom_translation_anchor_dense_and_scale_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            original = inputs.prepare(1, ASSETS, Path(temp)/'inputs')
            for name in ('direction','zoom','translation','anchor','dense','scale','order','quaternion'):
                p = copy.deepcopy(original)
                if name == 'direction': p['camera_profile']['signed_yaw_deg'] *= -1
                elif name == 'zoom': p['cameras'][-1]['fx'] *= 1.1
                elif name == 'translation': p['cameras'][-1]['position'][0] = .1
                elif name == 'anchor': p['image_index'] = 9
                elif name == 'dense': p['render_cameras'][-1]['quaternion'] = [1,0,0,0]
                elif name == 'scale': p['camera_control']['reference_scale'] = 0
                elif name == 'order': p['generation_order'] = list(reversed(range(24)))
                else: p['cameras'][0]['quaternion'][0] = 2
                with self.subTest(mutation=name), self.assertRaises(ValueError):
                    cameras.validate_protocol(p)

    @unittest.skipUnless(importlib.util.find_spec('torch'), 'requires CPU torch')
    def test_actual_pinned_flashworld_normalization_and_interpolation(self):
        import numpy as np
        import torch
        # Execute unchanged upstream camera functions without importing gsplat,
        # plyfile or any model. This checks the portable same-camera rerun path.
        names = {'quaternion_to_matrix','matrix_to_quaternion','standardize_quaternion',
                 '_sqrt_positive_part','matrix_to_square','normalize_cameras',
                 'sample_from_dense_cameras','sample_from_two_pose','quaternion_slerp'}
        tree = ast.parse((ROOT/'upstream/FlashWorld/utils.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        module = types.ModuleType('lucid_yaw_flash_reference')
        module.__dict__.update(torch=torch,math=math)
        exec(compile(tree, 'pinned_flash_camera_functions', 'exec'), module.__dict__)
        for index in cameras.PROFILES:
            with tempfile.TemporaryDirectory() as temp:
                p = inputs.prepare(index, ASSETS, Path(temp)/'inputs')
                flash = json.loads((Path(temp)/'inputs/flashworld.json').read_text())
                values = [c['quaternion']+c['position']+
                          [c['fx']/704,c['fy']/480,c['cx']/704,c['cy']/480]
                          for c in flash['cameras']]
                tensor = torch.tensor(values, dtype=torch.float32).unsqueeze(0)
                with fixed_camera_scale(flash['_camera_control'], module):
                    normalized, ref, scale = module.normalize_cameras(tensor, return_meta=True)
                    dense = module.sample_from_dense_cameras(tensor[0], torch.linspace(0,1,346)).unsqueeze(0)
                    dense = module.normalize_cameras(dense, ref_w2c=ref, T_norm=scale)
                for actual, expected in ((normalized[0],p['cameras']), (dense[0],p['render_cameras'])):
                    rotation = module.quaternion_to_matrix(actual[:,:4]).numpy()
                    ours = np.linalg.inv(inputs.cv_w2c(expected))[:,:3,:3]
                    flip = np.diag([1.,-1.,-1.])
                    np.testing.assert_allclose(flip@rotation@flip, ours, atol=1e-5)
                    np.testing.assert_allclose(actual[:,4:7].numpy(), 0, atol=1e-7)
                self.assertAlmostEqual(scale.item(), p['camera_control']['reference_scale'], places=5)


if __name__ == '__main__': unittest.main()
