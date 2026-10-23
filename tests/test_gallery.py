import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import gallery
from camera_paths import ASSIGNMENTS, template
import showcase


class GalleryTests(unittest.TestCase):
    def test_only_remaining_indices_and_retries(self):
        self.assertEqual(gallery.task_indices('3-9%1'), list(range(3, 10)))
        self.assertEqual(gallery.task_indices('4,7%1'), [4, 7])
        for value in ('0-9%1', '2%1', '3,3%1', '9-3%1', '3-9%0', '3-10%1'):
            with self.assertRaises(ValueError):
                gallery.task_indices(value)
        for index in (0, 1, 2, 10, True):
            with self.assertRaises(ValueError):
                gallery.build(index, '/unused')

    def check_transfer(self, index, original, data):
        for key in ('image_prompt', 'text_prompt', 'resolution'):
            self.assertEqual(data[key], original[key])
        self.assertEqual(data['image_index'], 9)
        self.assertNotIn('_camera_control', data)
        crop = data['_showcase']['crop']
        for actual, expected in zip(data['cameras'], template(ASSIGNMENTS[index])['cameras']):
            for key in ('quaternion', 'position'):
                self.assertEqual(actual[key], expected[key])
            for key in ('fx', 'fy'):
                self.assertAlmostEqual(actual[key]*crop['scale'], expected[key])
            for key, offset in (('cx', 0), ('cy', 1)):
                self.assertAlmostEqual((actual[key]-crop['crop_xywh'][offset])*crop['scale'], expected[key])
        self.assertEqual(data['_gallery']['index'], index)
        self.assertEqual(data['_gallery']['camera_profile'], ASSIGNMENTS[index])
        if index == 9:
            studio = showcase.official(5)
            stripped = {k:v for k,v in data.items() if not k.startswith('_')}
            self.assertNotEqual(stripped['text_prompt'], studio['text_prompt'])
            stripped['text_prompt'] = studio['text_prompt']
            self.assertEqual(stripped, studio)

    def test_portable_all_cases_and_prepare_no_overwrite(self):
        for index in range(3, 10):
            original = (showcase.build(index, '/unused') if index >= 8 else
                        {**showcase.official(3), '_showcase': {'recipe_file_sha256': 'fixture'}})
            before = copy.deepcopy(original)
            with patch.object(showcase, 'build', return_value=original):
                self.check_transfer(index, original, gallery.build(index, '/unused'))
                self.assertEqual(original, before)
                with tempfile.TemporaryDirectory() as temp:
                    output = Path(temp)/'prepared'
                    gallery.prepare('/unused', index, output)
                    self.assertTrue((output/f'gallery-{index:02d}.json').is_file())
                    with self.assertRaises(FileExistsError):
                        gallery.prepare('/unused', index, output)

    def test_real_frozen_assets(self):
        assets = Path(__file__).resolve().parents[2]/'world_scene_assets'
        if not (assets/'data/worldscore-indoor-v1/images/001.jpg').exists():
            self.skipTest('external frozen images unavailable')
        for index in range(3, 10):
            data = gallery.build(index, assets)
            self.check_transfer(index, showcase.build(index, assets), data)
            if index <= 7:
                self.assertEqual(data['_showcase']['split'], 'dev')
                self.assertFalse(data['_showcase']['source_camera_commands_executed'])


if __name__ == '__main__':
    unittest.main()
