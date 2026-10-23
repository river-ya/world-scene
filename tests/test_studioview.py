import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import showcase
import studioview
from camera_control import input_control


class StudioViewTests(unittest.TestCase):
    def assert_transfer(self, baseline, data):
        studio = showcase.official(5)
        for key in ('image_prompt', 'text_prompt', 'resolution'):
            self.assertEqual(data[key], baseline[key])
        self.assertEqual(data['image_index'], 9)
        self.assertEqual(data['_studio_view']['input_anchor_video_seconds'], 9)
        self.assertNotIn('_camera_control', data)
        self.assertNotIn('_viewcheck', data)
        crop = data['_showcase']['crop']
        for actual, expected in zip(data['cameras'], studio['cameras']):
            for key in ('quaternion', 'position'):
                self.assertEqual(actual[key], expected[key])
            for key in ('fx', 'fy'):
                self.assertAlmostEqual(actual[key]*crop['scale'], expected[key])
            self.assertAlmostEqual((actual['cx']-crop['crop_xywh'][0])*crop['scale'], expected['cx'])
            self.assertAlmostEqual((actual['cy']-crop['crop_xywh'][1])*crop['scale'], expected['cy'])
        self.assertEqual(data['_showcase']['camera_template_image_index'], 9)
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'input.json').write_text(json.dumps(data))
            self.assertIsNone(input_control(temp))

    def test_frozen_kitchen_transfer(self):
        assets = Path(__file__).resolve().parents[2]/'world_scene_assets'
        if not (assets/'data/worldscore-indoor-v1/images/000.jpg').exists():
            self.skipTest('external kitchen asset unavailable')
        self.assert_transfer(showcase.build(2, assets), studioview.build(assets))

    def test_portable_template_transfer_and_no_mutation(self):
        baseline = showcase.official(3)
        baseline['_showcase'] = {'camera_policy': 'fixture'}
        before = copy.deepcopy(baseline)
        digest = hashlib.sha256((json.dumps(baseline, ensure_ascii=False, indent=2)+'\n').encode()).hexdigest()
        with patch.object(showcase, 'build', return_value=baseline), patch.object(studioview, 'BASELINE_INPUT_SHA256', digest):
            self.assert_transfer(baseline, studioview.build('/unused'))
        self.assertEqual(baseline, before)

    def test_baseline_drift_is_rejected(self):
        with patch.object(showcase, 'build', return_value=showcase.official(3)):
            with self.assertRaisesRegex(ValueError, '70462'):
                studioview.build('/unused')


if __name__ == '__main__':
    unittest.main()
