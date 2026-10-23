"""LucidDreamer adapter: local loaders, matched intrinsics, bounded video memory."""
from contextlib import contextmanager
import gc
import math
import os
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace

from common import ROOT
from lucid_inputs import cv_w2c, projection
from lucid_assets import paths


@contextmanager
def offline():
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      GRADIO_ANALYTICS_ENABLED='False', HF_HUB_DISABLE_TELEMETRY='1',
                      LUCID_MIDAS_SOURCE=str(ROOT/'upstream/MiDaS'))
    original=socket.socket.connect
    def denied(*args, **kwargs):
        raise RuntimeError('LucidDreamer GPU 任务禁止联网；请在登录节点完整下载资产')
    socket.socket.connect=denied
    try: yield
    finally: socket.socket.connect=original


def imports():
    upstream=ROOT/'upstream/LucidDreamer'
    sys.path.insert(0,str(upstream))
    sys.path.insert(0,str(upstream/'ZoeDepth'))
    import luciddreamer as ld
    return ld


def load_depth(root, device='cuda'):
    imports()
    from zoedepth.utils.config import get_config
    from zoedepth.models.builder import build_model
    _,zoe=paths(root)
    config=get_config('zoedepth','infer',pretrained_resource='local::'+str(zoe),
                      use_pretrained_midas=False)
    return build_model(config).eval().requires_grad_(False).to(device)


def make_camera(w2c, k, width, height, image=None, uid=0):
    import numpy as np
    import torch
    from scene.cameras import Camera, MiniCam
    fx=2*math.atan(width/(2*k['fx'])); fy=2*math.atan(height/(2*k['fy']))
    view=torch.as_tensor(w2c,dtype=torch.float32,device='cuda').T.contiguous()
    proj=torch.as_tensor(projection(k,width,height),device='cuda').T.contiguous()
    if image is None:
        return MiniCam(width,height,fy,fx,.01,100.,view,view@proj)
    # Keep RGBs on CPU. Original optimization loop moves one target to GPU.
    cam=Camera(uid,w2c[:3,:3].T,w2c[:3,3],fx,fy,
               torch.from_numpy(np.asarray(image).copy()).permute(2,0,1).float()/255,
               None,'',uid,data_device='cpu')
    cam.world_view_transform=view
    cam.projection_matrix=proj
    cam.full_proj_transform=view@proj
    cam.camera_center=view.inverse()[3,:3]
    return cam


def install_cameras(protocol):
    import numpy as np
    import luciddreamer as ld
    import scene.dataset_readers as readers
    original=ld.get_pcdGenPoses
    poses=cv_w2c(protocol['cameras'])
    order=protocol['generation_order']
    def get_poses(name, argdict=None):
        if name=='world_scene': return poses[order,:3,:].copy()
        return original(name,{} if argdict is None else argdict)
    ld.get_pcdGenPoses=get_poses
    _,h,w=protocol['resolution']; k=protocol['cameras'][0]
    def training_cameras(data,white_background):
        cams=[]
        for i,frame in enumerate(data['frames']):
            # Upstream frames are Blender c2w; convert back to CV w2c.
            m=np.asarray(frame['transform_matrix']).copy(); m[:3,1:3]*=-1
            cams.append(make_camera(np.linalg.inv(m),k,w,h,frame['image'],i))
        if not cams: raise RuntimeError('无有效高斯优化视图')
        return cams
    readers.loadCamerasFromData=training_cameras
    # Avoid allocating >1000 irrelevant default camera presets.
    readers.loadCameraPreset=lambda *args,**kwargs: {}


def create_system(root, protocol, output):
    import numpy as np
    import torch
    ld=imports()
    from arguments import GSParams
    from scene.gaussian_model import GaussianModel
    from diffusers import StableDiffusionInpaintPipeline
    # Deliberately bypass the old constructor's remote IDs and removed fp16 branch.
    system=ld.LucidDreamer.__new__(ld.LucidDreamer)
    system.opt=GSParams(); system.for_gradio=False; system.save_dir=str(output)
    system.default_model=system.current_model='SD1.5 (default)'
    system.controlnet=system.lama=None
    _,h,w=protocol['resolution']; k=protocol['cameras'][0]
    # Upstream projects integer pixel centers. Convert FlashWorld's +0.5 rays.
    system.cam=SimpleNamespace(H=h,W=w,K=np.array([[k['fx'],0,k['cx']-.5],
                    [0,k['fy'],k['cy']-.5],[0,0,1]],dtype=np.float32),
                    fov=(2*math.atan(w/(2*k['fx'])),2*math.atan(h/(2*k['fy']))))
    system.gaussians=GaussianModel(system.opt.sh_degree)
    system.background=torch.ones(3,device='cuda') if system.opt.white_background else torch.zeros(3,device='cuda')
    sd,_=paths(root)
    system.rgb_model=StableDiffusionInpaintPipeline.from_pretrained(
        str(sd),variant='fp16',torch_dtype=torch.float16,use_safetensors=True,
        local_files_only=True).to('cuda')
    # Attention slicing has no extra weights and avoids a dependency on xformers.
    system.rgb_model.enable_attention_slicing()
    system.d_model=load_depth(root)
    install_cameras(protocol)
    return system


def check_gpu(root, output):
    import numpy as np
    import torch
    from PIL import Image
    ld=imports()
    if not torch.cuda.is_available() or torch.cuda.device_count()!=1:
        raise RuntimeError('请通过 Slurm 单 GPU 作业运行')
    if '4090' not in torch.cuda.get_device_name(0):
        raise RuntimeError('本版验证目标为 RTX 4090；其他硬件需要单独记录与验收')
    from simple_knn._C import distCUDA2
    from scene.gaussian_model import GaussianModel
    from utils.graphics import BasicPointCloud
    from arguments import GSParams
    points=np.array([[-.2,0,2],[.2,0,2],[0,.2,2],[0,-.2,2]],dtype=np.float32)
    assert torch.isfinite(distCUDA2(torch.tensor(points,device='cuda'))).all()
    gs=GaussianModel(0)
    gs.create_from_pcd(BasicPointCloud(points,np.full_like(points,.7),None),1.)
    camera=make_camera(np.eye(4),{'fx':60,'fy':60,'cx':31.5,'cy':31.5},64,64)
    image=ld.render(camera,gs,GSParams(),torch.zeros(3,device='cuda'))['render']
    assert torch.isfinite(image).all() and image.max()>0
    image.mean().backward()
    assert gs._xyz.grad is not None and torch.isfinite(gs._xyz.grad).all()
    del gs,image; gc.collect(); torch.cuda.empty_cache()
    from lucid_inputs import prepare
    protocol=prepare(1,os.environ['SCENE_ASSETS'],Path(output)/'inputs')
    system=create_system(root,protocol,output)
    rgb=Image.open(Path(output)/'inputs/input.png').convert('RGB')
    depth=system.d(rgb)
    if depth.shape != (480,704) or not np.isfinite(depth).all() or depth.min()<=0:
        raise RuntimeError('ZoeDepth 实际深度推理失败')
    # A real two-step inpainting pass catches tokenizer/UNet/VAE incompatibility.
    mask=np.ones((480,704)); mask[:,-64:]=0
    result=system.rgb(protocol['text_prompt'],np.asarray(rgb)/255.,mask_image=mask,
                      num_inference_steps=2,generator=torch.Generator('cuda').manual_seed(0))
    if result.size != (704,480): raise RuntimeError('SD 输出分辨率发生变化')
    result.save(Path(output)/'check-inpaint.png')
    torch.cuda.synchronize()
    print('LUCID_GPU_CHECK_OK raster_forward_backward + KNN + ZoeDepth + SD_inpaint',flush=True)


def generate(root, protocol, run, phase_callback):
    import numpy as np
    import torch
    import imageio.v2 as imageio
    from PIL import Image
    ld=imports()
    output=run/'outputs'; output.mkdir()
    stage=time.perf_counter()
    system=create_system(root,protocol,output)
    torch.cuda.synchronize(); phase_callback('model_load',time.perf_counter()-stage)
    rgb=Image.open(run/'inputs/input.png').convert('RGB')
    stage=time.perf_counter()
    data=system.generate_pcd(rgb,protocol['text_prompt'],'','world_scene',0,50)
    if not np.isfinite(data['pcd_points']).all(): raise RuntimeError('点云含非有限值')
    torch.cuda.synchronize(); phase_callback('dream_and_align',time.perf_counter()-stage)
    # Diffusion/depth networks are no longer needed during scene optimization.
    del system.rgb_model,system.d_model; gc.collect(); torch.cuda.empty_cache()
    stage=time.perf_counter()
    system.scene=ld.Scene(data,system.gaussians,system.opt)
    system.training()
    torch.cuda.synchronize(); phase_callback('gaussian_optimization',time.perf_counter()-stage)
    system.save_ply(str(output/'gaussians.ply'))
    # Reload the saved representation before rendering: MP4 genuinely comes from
    # the reusable exported scene, not cached generated views.
    from scene.gaussian_model import GaussianModel
    loaded=GaussianModel(system.opt.sh_degree)
    loaded.load_ply(str(output/'gaussians.ply'))
    system.gaussians=loaded
    del system.scene,data; gc.collect(); torch.cuda.empty_cache()
    stage=time.perf_counter()
    _,h,w=protocol['resolution']; dense=protocol['render_cameras']
    poses=cv_w2c(dense)
    with imageio.get_writer(output/'video.mp4',fps=protocol['fps'],codec='libx264',
                            quality=8,macro_block_size=1) as writer,torch.no_grad():
        for i,(pose,k) in enumerate(zip(poses,dense)):
            cam=make_camera(pose,k,w,h)
            rgb=ld.render(cam,loaded,system.opt,system.background)['render']
            if not torch.isfinite(rgb).all(): raise RuntimeError('渲染含非有限值')
            frame=(rgb.permute(1,2,0).clamp(0,1).cpu().numpy()*255).round().astype(np.uint8)
            writer.append_data(frame)
            if i%protocol['fps']==0:
                Image.fromarray(frame).save(output/f'view-{i//protocol["fps"]:02d}.png')
            if i%60==0: print('RENDER_FRAME',i+1,'/',len(dense),flush=True)
    torch.cuda.synchronize(); phase_callback('render_export',time.perf_counter()-stage)
