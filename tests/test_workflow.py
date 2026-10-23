import base64
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import ROOT, sha256
from cleanup import candidates
from data import select_scenes
from experiment import prepare, snapshot_inputs, validate_input
from release import tracked_files


class WorkflowTests(unittest.TestCase):
    def test_release_preserves_chinese_and_space_paths(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            subprocess.run(['git','init','-q',str(root)],check=True)
            name='中文 指南.md';(root/name).write_text('guide')
            subprocess.run(['git','add',name],cwd=root,check=True)
            self.assertEqual(tracked_files(root),[name])

    def test_official_cases_snapshot_and_text_ablation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); texts={}
            for case in ['room_b0','room_b1','studio_b0','studio_b1']:
                inputs=root/case;prepare(inputs,case)
                records=snapshot_inputs(inputs,root/(case+'-snapshot'))
                self.assertIn(case+'.json',records)
                texts[case]=json.loads((inputs/(case+'.json')).read_text())['text_prompt']
            self.assertEqual(texts['room_b0'],'');self.assertEqual(texts['studio_b0'],'')
            self.assertTrue(texts['room_b1']);self.assertTrue(texts['studio_b1'])
    def test_snapshot_copies_relative_image_before_source_disappears(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputs=root/'input';prepare(inputs,'room_b1')
            data=json.loads((inputs/'room_b1.json').read_text());data['image_prompt']='photo.png'
            (inputs/'photo.png').write_bytes(b'fixture image')
            (inputs/'room_b1.json').write_text(json.dumps(data))
            snapshot_inputs(inputs,root/'saved');(inputs/'photo.png').unlink()
            saved=json.loads((root/'saved/room_b1.json').read_text())
            self.assertEqual(Path(saved['image_prompt']).read_bytes(),b'fixture image')
    def test_long_bare_base64_is_accepted_without_path_oserror(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputs=root/'input';prepare(inputs,'room_b1')
            p=inputs/'room_b1.json';data=json.loads(p.read_text())
            data['image_prompt']=base64.b64encode(b'image bytes'*100).decode();p.write_text(json.dumps(data))
            snapshot_inputs(inputs,root/'saved')
    def test_invalid_camera_and_missing_image_fail(self):
        sample=json.loads((ROOT/'upstream/FlashWorld/examples/3.json').read_text())
        sample['cameras'][0]['fx']=float('nan')
        with self.assertRaises(ValueError):validate_input(sample)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputs=root/'input';prepare(inputs,'room_b1')
            p=inputs/'room_b1.json';data=json.loads(p.read_text());data['image_prompt']='missing-file.png';p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):snapshot_inputs(inputs,root/'saved')
    def test_frozen_split_is_disjoint_and_deterministic(self):
        manifest=json.loads((ROOT/'configs/data/worldscore-indoor-v1.json').read_text())
        samples=manifest['samples'];rows=[s['original'] for s in samples]
        expected=[(s['source_scene'],s['split']) for s in samples]
        selected=[(r['image'],split) for r,split in select_scenes(rows)]
        self.assertEqual(selected,expected)
        self.assertEqual(select_scenes(rows),select_scenes(rows+rows))
        self.assertEqual(len({s['source_scene'] for s in samples}),18)
        self.assertEqual(sum(s['split']=='dev' for s in samples),6)
    def test_cleanup_only_abandoned_named_dirs_not_symlinks(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for name in ['job-123.ABCD','job-124.EFGH','results','job-bad.XYZ']:(root/name).mkdir()
            (root/'job-999.LINK').symlink_to(root/'results',target_is_directory=True)
            self.assertEqual([p.name for p in candidates(root,{'124'})],['job-123.ABCD'])
    def test_export_checks_hash_and_creates_portable_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);run=root/'runs/smoke-1';(run/'inputs').mkdir(parents=True);(run/'outputs').mkdir()
            img=run/'inputs/photo.png';img.write_bytes(b'image')
            (run/'inputs/sample.json').write_text(json.dumps({'image_prompt':str(img)}))
            output=run/'outputs/scene.ply';output.write_bytes(b'ply fixture')
            manifest={'status':'complete','mode':'run','artifacts':{'outputs/scene.ply':{'sha256':sha256(output)}}}
            (run/'manifest.json').write_text(json.dumps(manifest))
            args=[sys.executable,'-B',str(ROOT/'tools/export_results.py'),'--runs',str(root/'runs'),'--logs',str(root/'logs'),'--names','smoke-1','--output',str(root/'result.tar.gz')]
            subprocess.run(args,check=True,capture_output=True)
            with tarfile.open(root/'result.tar.gz') as tf:
                saved=json.load(tf.extractfile('smoke-1/portable_inputs/sample.json'))
                self.assertEqual(saved['image_prompt'],'../inputs/photo.png')
            output.write_bytes(b'tampered')
            args[-1]=str(root/'bad.tar.gz')
            result=subprocess.run(args,capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse((root/'bad.tar.gz').exists())


if __name__=='__main__':unittest.main()
