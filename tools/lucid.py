"""Manifest-first Slurm check/run wrapper for the second model."""
import argparse
import json
import os
from pathlib import Path
import random
import resource
import shutil
import subprocess
import sys
import tempfile
import time

from common import ROOT, now, project_identity, safe_name, sha256, write_json
import lucid_assets


def artifact_check(run,protocol):
    import numpy as np
    import imageio.v2 as imageio
    from plyfile import PlyData
    output=run/'outputs'
    vertices=PlyData.read(output/'gaussians.ply')['vertex'].data
    fields={'x','y','z','opacity','scale_0','scale_1','scale_2',
            'rot_0','rot_1','rot_2','rot_3','f_dc_0','f_dc_1','f_dc_2'}
    if not len(vertices) or not fields.issubset(vertices.dtype.names):
        raise RuntimeError('导出的 PLY 不是完整三维高斯')
    for key in fields:
        if not np.isfinite(vertices[key]).all(): raise RuntimeError('非有限高斯字段: '+key)
    with imageio.get_reader(output/'video.mp4') as reader:
        if reader.count_frames()!=len(protocol['render_cameras']): raise RuntimeError('视频帧数错误')
        if reader.get_data(0).shape[:2]!=tuple(protocol['resolution'][1:]): raise RuntimeError('视频尺寸错误')
    result={}
    for p in sorted(output.iterdir()):
        if p.is_file(): result[str(p.relative_to(run))]={'sha256':sha256(p),'bytes':p.stat().st_size}
    return result


def run(args):
    identity=project_identity(); lucid_assets.source_check()
    run=Path(args.run_root).resolve()/safe_name(args.name)
    run.mkdir(parents=True,exist_ok=False)
    meta={**identity,'model':'LucidDreamer-CVLab','mode':args.command,'status':'running',
          'started_at':now(),'job_id':os.getenv('SLURM_JOB_ID'),
          'array_task':os.getenv('SLURM_ARRAY_TASK_ID'),'node':os.getenv('SLURMD_NODENAME'),
          'case_index':args.index,'seed':0,'phases_seconds':{},
          'lucid_commit':lucid_assets.spec()['sources']['LucidDreamer']['commit'],
          'lock_sha256':sha256(lucid_assets.LOCK), 'visual_acceptance':'pending'}
    write_json(run/'manifest.json',meta)
    start=time.perf_counter()
    try:
        lucid_assets.verify(args.assets,quick=True)
        for source in [lucid_assets.LOCK,Path(args.assets)/'receipt.json',Path(args.assets)/'zoe.download.json']:
            shutil.copy2(source,run/source.name)
        (run/'environment.freeze.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
        import numpy as np
        import torch
        if torch.cuda.device_count()!=1 or not torch.cuda.is_available(): raise RuntimeError('需要一个可见 GPU')
        random.seed(0); np.random.seed(0); torch.manual_seed(0); torch.cuda.manual_seed_all(0)
        torch.cuda.reset_peak_memory_stats()
        meta['gpu']=torch.cuda.get_device_name(0)
        if '4090' not in meta['gpu']: raise RuntimeError('本版正式运行目标为 RTX 4090')
        from lucid_runtime import offline,generate,check_gpu
        with offline():
            if args.command=='check': check_gpu(args.assets,run)
            else:
                from lucid_inputs import prepare
                protocol=prepare(args.index,os.environ['SCENE_ASSETS'],run/'inputs')
                meta['input_sha256']={p.name:sha256(p) for p in (run/'inputs').iterdir()}
                meta['protocol']=protocol['protocol']
                meta['camera_profile']=protocol['camera_profile']
                meta['camera_control']=protocol['camera_control']
                meta['metric_scale_alignment']=protocol['metric_scale_alignment']
                def phase(name,seconds):
                    meta['phases_seconds'][name]=seconds
                    write_json(run/'manifest.json',meta)
                    print('PHASE_COMPLETE',name,round(seconds,2),'seconds',flush=True)
                generate(args.assets,protocol,run,phase)
                meta['artifacts']=artifact_check(run,protocol)
        meta['gpu_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
        meta['gpu_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
        meta['status']='complete'
    except BaseException as e:
        meta.update(status='failed',error_type=type(e).__name__,error=str(e)); raise
    finally:
        meta.update(finished_at=now(),seconds_including_model_load=time.perf_counter()-start,
                    cpu_peak_rss_kib_linux=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(run/'manifest.json',meta)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['preflight','check','run'])
    p.add_argument('--assets',type=Path,default=os.getenv('LUCID_ASSETS'))
    p.add_argument('--array',default='1%1')
    p.add_argument('--index',type=int,default=1)
    p.add_argument('--run-root',type=Path,default=os.getenv('LUCID_RUNS'))
    p.add_argument('--name')
    a=p.parse_args()
    if a.assets is None: p.error('缺少 LUCID_ASSETS')
    if a.command=='preflight':
        project_identity(); lucid_assets.preflight(a.assets)
        from showcase import task_indices
        from lucid_inputs import prepare
        with tempfile.TemporaryDirectory(prefix='lucid-input-check-') as temp:
            for index in task_indices(a.array):
                prepare(index,os.environ['SCENE_ASSETS'],Path(temp)/str(index))
        return
    if a.run_root is None or not a.name: p.error('缺少 --run-root / --name')
    run(a)


if __name__=='__main__':main()
