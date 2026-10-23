import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from common import sha256
import lucid_inputs as inputs
from lucid_export import collect


@unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('PIL'),
                     'requires numpy and Pillow in independent test environment')
class LucidCameraTests(unittest.TestCase):
    def test_all_real_inputs_and_crop_and_anchor(self):
        import numpy as np
        from PIL import Image
        import base64,io
        if not (ROOT.parent/'world_scene_assets/data/worldscore-indoor-v1/images/000.jpg').exists():
            self.skipTest('external frozen development images unavailable')
        with tempfile.TemporaryDirectory() as temp:
            for index in range(10):
                p=inputs.prepare(index,ROOT.parent/'world_scene_assets',Path(temp)/str(index))
                src=json.loads((Path(temp)/str(index)/'source.json').read_text())
                original=Image.open(io.BytesIO(base64.b64decode(src['image_prompt'].split(',')[-1]))).convert('RGB')
                w,h=original.size; _,oh,ow=src['resolution']
                scale=max(oh/h,ow/w); nw,nh=int(ow/scale),int(oh/scale)
                expected=original.crop(((w-nw)//2,(h-nh)//2,(w-nw)//2+nw,(h-nh)//2+nh)).resize((ow,oh))
                actual=Image.open(Path(temp)/str(index)/'input.png')
                np.testing.assert_array_equal(np.asarray(actual),np.asarray(expected))
                self.assertEqual(p['text_prompt'],src['text_prompt'])
                self.assertEqual(sorted(p['generation_order']),list(range(24)))
                self.assertEqual(p['generation_order'][0],src['image_index'])
                poses=inputs.cv_w2c(p['cameras'])
                np.testing.assert_allclose(poses[p['image_index']],np.eye(4),atol=1e-6)
                np.testing.assert_allclose(np.linalg.det(poses[:,:3,:3]),1,atol=1e-6)
                self.assertEqual(len(p['render_cameras']),346)
                np.testing.assert_allclose(inputs.cv_w2c(p['render_cameras'])[::15],poses,atol=1e-6)
                with self.assertRaises(FileExistsError):
                    inputs.prepare(index,ROOT.parent/'world_scene_assets',Path(temp)/str(index))

    def test_projection_matches_flash_pixel_center_rays(self):
        import numpy as np
        k={'fx':438.02,'fy':438.01,'cx':351.38,'cy':239.70}
        width,height=704,480
        uv=np.array([[0,0],[703,479],[351,239],[123,412]],dtype=float)
        # PCD integer-pixel K is shifted -0.5 to match FlashWorld's +0.5 rays.
        xyz=np.column_stack(((uv[:,0]+.5-k['cx'])/k['fx'],
                             (uv[:,1]+.5-k['cy'])/k['fy'],np.ones(len(uv))))*2
        clip=(inputs.projection(k,width,height)@np.column_stack((xyz,np.ones(len(xyz)))).T).T
        ndc=clip[:,:2]/clip[:,3:4]
        recovered=((ndc+1)*[width,height]-1)/2
        np.testing.assert_allclose(recovered,uv,atol=5e-5)

    def test_gl_to_cv_translation_and_ray_orientation(self):
        import numpy as np
        cameras=[{'quaternion':[1,0,0,0],'position':[0,0,0]},
                 {'quaternion':[1,0,0,0],'position':[1,2,3]}]
        poses=inputs.cv_w2c(cameras)
        np.testing.assert_allclose(np.linalg.inv(poses[1])[:3,3],[1,-2,-3])
        point=np.array([.1,.2,2,1])
        np.testing.assert_allclose(poses[0]@point,point)

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('plyfile'), 'torch needed')
    def test_against_actual_flashworld_normalization(self):
        import numpy as np
        import torch
        # The complete FlashWorld module requires torch 2.6 decorators. Execute
        # its unchanged camera function ASTs under LucidDreamer's torch 2.0.
        import ast, math, types
        tree=ast.parse((ROOT/'upstream/FlashWorld/utils.py').read_text())
        names={'quaternion_to_matrix','matrix_to_quaternion','standardize_quaternion',
               '_sqrt_positive_part','matrix_to_square','normalize_cameras'}
        tree.body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        module=types.ModuleType('flash_camera_reference')
        module.__dict__.update(torch=torch,math=math)
        exec(compile(tree,'pinned_flash_camera_functions','exec'),module.__dict__)
        from showcase import official
        for number in [3,5]:
            d=official(number); cameras=d['cameras']; anchor=d['image_index']
            t=torch.tensor([c['quaternion']+c['position']+[c['fx']/704,c['fy']/480,c['cx']/704,c['cy']/480]
                            for c in cameras]).unsqueeze(0)
            normalized=module.normalize_cameras(t)[0]
            ref=torch.eye(4).repeat(24,1,1)
            ref[:,:3,:3]=module.quaternion_to_matrix(normalized[:,:4]); ref[:,:3,3]=normalized[:,4:7]
            relative=torch.linalg.inv(ref[anchor])@ref
            ours,_=inputs.relative_cameras(cameras,anchor)
            flip=np.diag([1,-1,-1,1])
            expected=np.linalg.inv(flip@relative.numpy()@flip)
            np.testing.assert_allclose(inputs.cv_w2c(ours),expected,atol=2e-6)


class LucidWorkflowTests(unittest.TestCase):
    def test_receipt_requires_all_files_and_unchanged_stats(self):
        import lucid_assets as assets
        from common import write_json
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'sd-inpainting').mkdir()
            names=['sd-inpainting/config.json','ZoeD_M12_N.pt']
            for name in names: (root/name).write_bytes(b'fixture')
            records={name:{'stat':assets.fingerprint(root/name),'sha256':sha256(root/name)} for name in names}
            receipt={'lock_sha256':sha256(assets.LOCK),'files':records}
            write_json(root/'receipt.json',receipt)
            write_json(root/'zoe.download.json',{'sha256':records[names[1]]['sha256']})
            with patch.object(assets,'spec',return_value={'sd':{'files':[{'path':'config.json'}]}}):
                assets.verify(root,quick=True)
                (root/names[0]).write_bytes(b'changed-size')
                with self.assertRaises(RuntimeError): assets.verify(root,quick=True)
                del receipt['files'][names[0]]; write_json(root/'receipt.json',receipt)
                with self.assertRaises(RuntimeError): assets.verify(root,quick=True)

    def test_export_retries_hashes_and_failed_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); state=root/'state'; state.mkdir()
            (state/'case-1.jobid').write_text('123\n')
            run=root/'lucid-01-123-1'; (run/'inputs').mkdir(parents=True); (run/'outputs').mkdir()
            (run/'inputs/input.png').write_bytes(b'image')
            artifacts={}
            for name in ['gaussians.ply','video.mp4']:
                path=run/'outputs'/name; path.write_bytes(b'data'); artifacts['outputs/'+name]={'sha256':sha256(path)}
            m={'status':'complete','mode':'run','model':'LucidDreamer-CVLab','artifacts':artifacts,
               'input_sha256':{'input.png':sha256(run/'inputs/input.png')}}
            (run/'manifest.json').write_text(json.dumps(m))
            self.assertEqual(collect(root,state,[1])[0][0],run)
            (run/'outputs/video.mp4').write_bytes(b'corrupt')
            with self.assertRaises(RuntimeError): collect(root,state,[1])
            m['status']='failed'; (run/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(RuntimeError): collect(root,state,[1])

    def test_relocated_slurm_and_failed_submission_keeps_state(self):
        for stage in ['check','run']:
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as temp:
                root=Path(temp); code=root/'code with spaces'
                shutil.copytree(ROOT/'slurm/lucid',code/'slurm/lucid')
                (code/'tools').mkdir(); (code/'VERSION').write_text('0.7.0\n')
                (code/'tools/lucid.py').write_text('''import os,sys,json
with open(os.environ['TRACE'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
if os.getenv('FAIL') and sys.argv[1]=='preflight': raise SystemExit(1)
''')
                shutil.copy2(ROOT/'tools/showcase.py',code/'tools/showcase.py')
                # Keep just array parsing; no project imports needed by this stand-in.
                (code/'tools/showcase.py').write_text('def task_indices(value): return [1]\n')
                bin=root/'env/bin'; bin.mkdir(parents=True)
                (bin/'python').symlink_to(sys.executable)
                (bin/'nvidia-smi').write_text('#!/bin/sh\necho mock\n'); (bin/'nvidia-smi').chmod(0o755)
                (bin/'sbatch').write_text('#!'+sys.executable+'\n'+'''import json,os,pathlib,shutil,subprocess,sys
r=pathlib.Path(os.environ['TEST_ROOT']); a=sys.argv[1:]
(r/'args.json').write_text(json.dumps(a))
if os.getenv('FAIL_SUBMIT'): raise SystemExit(1)
(r/'spool').mkdir(exist_ok=True); p=r/'spool/slurm_script'; shutil.copy2(a[-2],p)
e=dict(os.environ,SLURM_JOB_ID='123')
if a[-1]=='run': e.update(SLURM_ARRAY_JOB_ID='123',SLURM_ARRAY_TASK_ID='1')
v=subprocess.run(['bash',str(p),a[-1]],env=e,capture_output=True,text=True)
(r/'batch.json').write_text(json.dumps({'code':v.returncode,'err':v.stderr}))
print('123')
'''); (bin/'sbatch').chmod(0o755)
                env={k:v for k,v in os.environ.items() if not k.startswith(('LUCID_','SLURM_','SBATCH_'))}
                env.update(LUCID_ENV=str(root/'env'),LUCID_DATA_ROOT=str(root/'data'),
                           TEST_ROOT=str(root),TRACE=str(root/'trace'),PATH=str(bin)+':'+os.environ['PATH'],
                           LUCID_ACCOUNT='',LUCID_QOS='',LUCID_NODE='')
                command=['bash','slurm/lucid/submit.sh',stage]
                out=subprocess.run(command,cwd=code,env=env,capture_output=True,text=True)
                self.assertEqual(out.returncode,0,out.stderr)
                batch=json.loads((root/'batch.json').read_text()); self.assertEqual(batch['code'],0,batch['err'])
                args=json.loads((root/'args.json').read_text())
                self.assertIn('--mem=64G',args); self.assertIn('--export=ALL',args)
                self.assertFalse(any(arg.startswith(('--account=', '--qos=', '--nodelist=')) for arg in args))
                self.assertEqual('--array=1%1' in args,stage=='run')
                state=root/'data/state/world_scene_lucid/v0.7.0'
                self.assertEqual((state/(stage+'.jobid')).read_text(),'123\n')
                for failvar in ['FAIL','FAIL_SUBMIT']:
                    env[failvar]='1'
                    failed=subprocess.run(command,cwd=code,env=env,capture_output=True,text=True)
                    self.assertNotEqual(failed.returncode,0)
                    self.assertEqual((state/(stage+'.jobid')).read_text(),'123\n')
                    env.pop(failvar)
                self.assertEqual(list((root/'data/world_scene_lucid_assets/tmp').iterdir()),[])


if __name__=='__main__':unittest.main()
