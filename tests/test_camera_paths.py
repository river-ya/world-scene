import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera_paths as paths
import showcase


class CameraPathsTests(unittest.TestCase):
    def test_studio_unchanged_and_three_distinct_profiles(self):
        self.assertEqual(paths.template('studio'),showcase.official(5))
        self.assertEqual(set(paths.ASSIGNMENTS.values()),{'studio','studio_mirrored','room_short'})
        self.assertEqual(paths.ASSIGNMENTS[9],'studio')  # Text comparison stays controlled.
        for profile in set(paths.ASSIGNMENTS.values()):
            data=paths.template(profile)
            self.assertEqual(len(data['cameras']),24)
            self.assertEqual(data['image_index'],9)
            stats=paths.stats(data)
            self.assertTrue(20 < stats['max_rotation_deg'] < 35)
            self.assertTrue(.5 < stats['max_translation_model_units'] < .8)
            self.assertGreater(stats['export_scale'],1)
            for camera in data['cameras']:
                self.assertAlmostEqual(sum(v*v for v in camera['quaternion']),1,places=5)
        with self.assertRaises(ValueError):
            paths.template('unknown')

    def test_mirror_anchor_involution_and_opposite_side(self):
        data=showcase.official(5);original=copy.deepcopy(data['cameras'])
        mirrored=paths.mirror(original,9)
        restored=paths.mirror(mirrored,9)
        self.assertEqual(original,data['cameras'])
        self.assertEqual(mirrored[9],original[9])
        anchor=original[9]
        for a,b,c in zip(original,mirrored,restored):
            for x,y in zip(a['position'],c['position']):self.assertAlmostEqual(x,y,places=10)
            dot=abs(sum(x*y for x,y in zip(paths.unit(a['quaternion']),paths.unit(c['quaternion']))))
            self.assertAlmostEqual(dot,1,places=10)
            local_a=paths.rotate(paths.inverse(anchor['quaternion']),[x-y for x,y in zip(a['position'],anchor['position'])])
            local_b=paths.rotate(paths.inverse(anchor['quaternion']),[x-y for x,y in zip(b['position'],anchor['position'])])
            self.assertAlmostEqual(local_a[0],-local_b[0],places=10)
            self.assertAlmostEqual(local_a[1],local_b[1],places=10)
            self.assertAlmostEqual(local_a[2],local_b[2],places=10)
        self.assertNotEqual(original[-1]['position'],mirrored[-1]['position'])

    def test_room_short_uses_only_early_segment_and_retains_anchor(self):
        original=showcase.official(3)
        short=paths.template('room_short')
        self.assertEqual(short['cameras'][9],original['cameras'][3])
        for actual,expected in ((short['cameras'][0],original['cameras'][0]),
                                (short['cameras'][-1],original['cameras'][11])):
            for a,b in zip(actual['position'],expected['position']):self.assertAlmostEqual(a,b)
            dot=abs(sum(a*b for a,b in zip(paths.unit(actual['quaternion']),paths.unit(expected['quaternion']))))
            self.assertAlmostEqual(dot,1)
        self.assertGreater(paths.stats(original)['max_rotation_deg'],140)
        self.assertLess(paths.stats(short)['max_rotation_deg'],31)
        self.assertEqual(short['text_prompt'],original['text_prompt'])


if __name__=='__main__':unittest.main()
