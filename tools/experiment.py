"""Versioned wrapper around unmodified FlashWorld inference."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import random
import runpy
import shutil
import subprocess
import sys
import time
import resource
from common import ROOT, lock, now, project_identity, safe_name, sha256, source_check, write_json
from offline_models import local_wan_loaders, offline_environment, preflight, wan_snapshot
from camera_control import fixed_camera_scale, input_control


def validate_input(data):
    if not isinstance(data.get('text_prompt',''),str):raise ValueError('文本必须是字符串')
    if not data.get('image_prompt'):raise ValueError('本项目首阶段要求单张 RGB 输入')
    if not isinstance(data['image_prompt'],str):raise ValueError('图像必须为路径或 base64 字符串')
    shape=data.get('resolution')
    if not isinstance(shape,list) or len(shape)!=3 or not all(type(x)==int and x>0 for x in shape):raise ValueError('resolution 必须为 [N,H,W] 正整数')
    if any(x%32 for x in shape[1:]):raise ValueError('图像分辨率需与模型 patch 对齐至 32 倍数')
    cameras=data.get('cameras')
    if not isinstance(cameras,list) or len(cameras)<2:raise ValueError('至少需要两个相机采样点')
    idx=data.get('image_index',0)
    if type(idx)!=int or not 0<=idx<shape[0]:raise ValueError('image_index 越界')
    for c in cameras:
        if len(c.get('quaternion',[]))!=4 or len(c.get('position',[]))!=3:raise ValueError('相机结构错误')
        values=c['quaternion']+c['position']+[c[k] for k in ['fx','fy','cx','cy']]
        if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):raise ValueError('相机参数必须有限')
        if c['fx']<=0 or c['fy']<=0:raise ValueError('焦距必须为正')
        if abs(sum(v*v for v in c['quaternion'])-1)>0.02:raise ValueError('四元数未归一化')


def prepare(output, case):
    mapping={'room_b0':('3',True),'room_b1':('3',False),'studio_b0':('5',True),'studio_b1':('5',False)}
    sample,empty=mapping[case]
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    data=json.loads((ROOT/f'upstream/FlashWorld/examples/{sample}.json').read_text())
    if empty:data['text_prompt']=''
    validate_input(data)
    write_json(output/f'{case}.json',data)
    print('准备官方连通样例:',case,'不计入独立泛化测试')


def gpu_check():
    source_check()
    import importlib.util
    assert importlib.util.find_spec('spaces') is None, '检测到云 Spaces 专用包'
    import torch
    from gsplat import rasterization
    import spz
    assert torch.cuda.is_available() and torch.cuda.device_count()==1, '必须是 Slurm 单卡作业'
    assert torch.__version__.split('+')[0]=='2.6.0' and torch.version.cuda=='12.4'
    assert '4090' in torch.cuda.get_device_name(0), '目标硬件是 4090；其他卡需单独记录配置'
    assert torch.cuda.is_bf16_supported()
    device='cuda'
    x=torch.randn((64,64),device=device,dtype=torch.bfloat16);assert torch.isfinite(x@x).all()
    rendered,alpha,_=rasterization(
        means=torch.tensor([[0.,0.,2.]],device=device),
        quats=torch.tensor([[1.,0.,0.,0.]],device=device),
        scales=torch.full((1,3),0.1,device=device),
        opacities=torch.tensor([0.8],device=device),
        colors=torch.tensor([[1.,0.2,0.1]],device=device),
        viewmats=torch.eye(4,device=device)[None],
        Ks=torch.tensor([[[60.,0.,32.],[0.,60.,32.],[0.,0.,1.]]],device=device),width=64,height=64)
    assert torch.isfinite(rendered).all() and alpha.max()>0
    torch.cuda.synchronize()
    print('GPU/BF16/实际高斯栅格化检查通过:',torch.cuda.get_device_name(0),flush=True)


def snapshot_inputs(inputs, dest):
    dest.mkdir()
    sources=sorted(Path(inputs).glob('*.json'))
    if not sources:raise ValueError('无输入 JSON')
    for p in sources:
        safe_name(p.stem)
        data=json.loads(p.read_text());validate_input(data)
        image=data['image_prompt']
        if not image.startswith('data:'):
            source=Path(image)
            if not source.is_absolute():source=p.parent/source
            try:
                is_file=source.is_file()
            except OSError:
                is_file=False  # Long bare base64 is not a filesystem path.
            if is_file:
                copied=dest/(p.stem+'-input'+source.suffix.lower())
                shutil.copy2(source,copied);data['image_prompt']=str(copied.resolve())
            else:
                # Upstream accepts bare base64; validate it rather than treating missing paths as images.
                import base64
                try:base64.b64decode(image,validate=True)
                except Exception as exc:raise ValueError('输入图片不存在或不是合法 base64: '+str(p)) from exc
        write_json(dest/p.name,data)
    return {p.name:sha256(p) for p in dest.iterdir() if p.is_file()}


def artifacts_check(run):
    from plyfile import PlyData
    import numpy as np
    result={}
    names={'x','y','z','opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3','f_dc_0','f_dc_1','f_dc_2'}
    for inp in sorted((run/'inputs').glob('*.json')):
        directory=run/'outputs'/inp.stem
        for name in ['gaussians.ply','gaussians.spz','video.mp4']:
            p=directory/name
            if not p.is_file() or p.stat().st_size==0:raise RuntimeError('输出缺失: '+str(p))
            result[str(p.relative_to(run))]={'bytes':p.stat().st_size,'sha256':sha256(p)}
        vertices=PlyData.read(directory/'gaussians.ply')['vertex'].data
        if not len(vertices) or not names.issubset(vertices.dtype.names):raise RuntimeError('高斯字段不完整')
        # opacity is a logit and can approach +/-inf; geometry must remain finite.
        for name in names-{'opacity'}:
            if not np.isfinite(vertices[name]).all():raise RuntimeError('非有限高斯几何/颜色: '+name)
    return result


def launch(args):
    source_check();identity=project_identity()
    root=Path(args.run_root).resolve();root.mkdir(parents=True,exist_ok=True)
    run=root/safe_name(args.name);run.mkdir(exist_ok=False)
    meta={**identity,'started_at':now(),'status':'running','mode':args.command,
          'job_id':os.getenv('SLURM_JOB_ID'),'array_task':os.getenv('SLURM_ARRAY_TASK_ID'),
          'node':os.getenv('SLURMD_NODENAME'),'seed':args.seed,
          'offload':['t5','vae'],'lock_sha256':sha256(ROOT/'configs/versions.lock.json')}
    write_json(run/'manifest.json',meta)
    try:
        offline_environment()
        snapshot = wan_snapshot(os.environ['SCENE_ASSETS'])
        meta['wan_snapshot'] = str(snapshot)
        meta['model_loading'] = 'pinned_local_snapshot'
        shutil.copy2(ROOT/'configs/versions.lock.json',run/'versions.lock.json')
        (run/'environment.freeze.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
        import numpy as np
        import torch
        meta['gpu']=torch.cuda.get_device_name(0)
        random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed)
        torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
        spec=next(a for a in lock()['assets'] if a['repo']=='imlixinyang/FlashWorld')
        ckpt=Path(os.environ['SCENE_ASSETS'])/'hf/hub/models--imlixinyang--FlashWorld/snapshots'/spec['revision']/'model.ckpt'
        upstream=ROOT/'upstream/FlashWorld'
        camera_control = None
        if args.command=='ui':
            sys.argv=['app.py','--ckpt',str(ckpt),'--offload_t5','--offload_vae','--port','7860','--cache_dir',str(Path(os.environ['TMPDIR'])/'web-cache')]
        else:
            meta['input_sha256']=snapshot_inputs(args.inputs,run/'inputs')
            camera_control = input_control(run/'inputs')
            meta['camera_normalization'] = camera_control or {'policy': 'upstream_per_trajectory'}
            sys.argv=['cli.py','--ckpt',str(ckpt),'--input_dir',str(run/'inputs'),'--output_dir',str(run/'outputs'),
                      '--offload_t5','--offload_vae','--ply','--spz','--video']
        write_json(run/'manifest.json',meta)
        os.chdir(upstream);sys.path.insert(0,str(upstream))
        with local_wan_loaders(snapshot), fixed_camera_scale(camera_control):
            runpy.run_path(str(upstream/sys.argv[0]),run_name='__main__')
        torch.cuda.synchronize()
        meta['runtime']={'seconds_including_model_load':time.perf_counter()-start,
            'gpu_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'gpu_peak_reserved_bytes':torch.cuda.max_memory_reserved(),
            'cpu_peak_rss_kib_linux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        if args.command=='run':meta['artifacts']=artifacts_check(run)
        meta['status']='complete';meta['visual_acceptance']='pending'
    except BaseException as exc:
        meta['status']='failed';meta['error_type']=type(exc).__name__;meta['error']=str(exc)
        raise
    finally:
        meta['finished_at']=now();write_json(run/'manifest.json',meta)


def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='command',required=True)
    sp.add_parser('inspect');sp.add_parser('check');sp.add_parser('preflight')
    prep=sp.add_parser('prepare');prep.add_argument('--output',type=Path,required=True)
    prep.add_argument('--case',choices=['room_b0','room_b1','studio_b0','studio_b1'],default='room_b1')
    for command in ['run','ui']:
        sub=sp.add_parser(command);sub.add_argument('--run-root',type=Path,required=True);sub.add_argument('--name',required=True)
        sub.add_argument('--seed',type=int,default=0)
        if command=='run':sub.add_argument('--inputs',type=Path,required=True)
    a=p.parse_args()
    if a.command=='inspect':source_check();print(json.dumps(project_identity(),indent=2))
    elif a.command=='check':gpu_check()
    elif a.command=='preflight':source_check();preflight(os.environ['SCENE_ASSETS'])
    elif a.command=='prepare':source_check();prepare(a.output,a.case)
    else:launch(a)


if __name__=='__main__':main()
