"""CPU integration probe; NEVER presented as CUDA/weight/inference validation.

CUDA extension import symbols and import-time .cuda() are stubbed only here.
Actual upstream point-cloud generation/alignment executes with synthetic RGB/depth.
The real local Zoe/MiDaS architecture is constructed without downloaded weights.
"""
import gc
import os
from pathlib import Path
import sys
import types
import json
import tempfile
from unittest.mock import patch

os.environ['GRADIO_ANALYTICS_ENABLED']='False'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
import torch
from PIL import Image
import lucid_runtime


def unavailable(*args,**kwargs):
    raise AssertionError('CPU probe must not execute a CUDA extension')


def main():
    raster=types.ModuleType('depth_diff_gaussian_rasterization_min')
    raster.GaussianRasterizationSettings=raster.GaussianRasterizer=unavailable
    knn=types.ModuleType('simple_knn'); knnc=types.ModuleType('simple_knn._C'); knnc.distCUDA2=unavailable
    sys.modules.update(depth_diff_gaussian_rasterization_min=raster,simple_knn=knn)
    sys.modules['simple_knn._C']=knnc
    with lucid_runtime.offline():
        with patch.object(torch.nn.Module,'cuda',lambda self,*a,**kw:self):
            ld=lucid_runtime.imports()
        # Real diffusers components with small random weights: test rectangular
        # size and the exact upstream rgb() adapter, not scene quality.
        from diffusers import StableDiffusionInpaintPipeline,AutoencoderKL,UNet2DConditionModel,DDIMScheduler
        from transformers import CLIPTextConfig,CLIPTextModel,CLIPTokenizer
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            (d/'vocab.json').write_text(json.dumps({'<|startoftext|>':0,'<|endoftext|>':1}))
            (d/'merges.txt').write_text('#version: 0.2\n')
            tokenizer=CLIPTokenizer(str(d/'vocab.json'),str(d/'merges.txt'),model_max_length=16)
            text=CLIPTextModel(CLIPTextConfig(vocab_size=2,hidden_size=32,intermediate_size=37,
                    num_hidden_layers=1,num_attention_heads=4,max_position_embeddings=16,bos_token_id=0,eos_token_id=1))
            vae=AutoencoderKL(block_out_channels=(32,64,64),
                    down_block_types=('DownEncoderBlock2D',)*3,up_block_types=('UpDecoderBlock2D',)*3)
            unet=UNet2DConditionModel(sample_size=16,in_channels=9,out_channels=4,
                    block_out_channels=(32,64),layers_per_block=1,cross_attention_dim=32,
                    down_block_types=('DownBlock2D','CrossAttnDownBlock2D'),
                    up_block_types=('CrossAttnUpBlock2D','UpBlock2D'))
            pipe=StableDiffusionInpaintPipeline(vae,text,tokenizer,unet,DDIMScheduler(),
                    safety_checker=None,feature_extractor=None,requires_safety_checker=False)
            pipe.save_pretrained(d/'tiny',safe_serialization=True,variant='fp16')
            pipe=StableDiffusionInpaintPipeline.from_pretrained(d/'tiny',local_files_only=True,
                    variant='fp16',use_safetensors=True,torch_dtype=torch.float32)
            stub=ld.LucidDreamer.__new__(ld.LucidDreamer)
            stub.cam=types.SimpleNamespace(H=64,W=96)
            stub.current_model=stub.default_model='SD1.5 (default)'; stub.rgb_model=pipe
            mask=np.ones((64,96));mask[:,-16:]=0
            rendered=stub.rgb('room',np.full((64,96,3),.5),mask_image=mask,num_inference_steps=2,
                              generator=torch.Generator().manual_seed(0))
            assert rendered.size==(96,64),rendered.size
            print('REAL_DIFFUSERS_LOCAL_VARIANT_AND_RECTANGULAR_INPAINT_OK',flush=True)
            del pipe,stub,text,vae,unet;gc.collect()
        from zoedepth.utils.config import get_config
        from zoedepth.models.builder import build_model
        config=get_config('zoedepth','infer',pretrained_resource=None,use_pretrained_midas=False)
        model=build_model(config).eval()
        count=sum(p.numel() for p in model.parameters())
        assert count>300_000_000
        print('LOCAL_ZOE_MIDAS_ARCHITECTURE_OK',count,flush=True)
        del model; gc.collect()
        system=ld.LucidDreamer.__new__(ld.LucidDreamer)
        w,h=96,64
        system.cam=types.SimpleNamespace(W=w,H=h,K=np.array([[80.,0,47.5],[0,80.,31.5],[0,0,1]],dtype=np.float32),
                                        fov=(2*np.arctan(w/160),2*np.arctan(h/160)))
        system.for_gradio=False
        system.d=lambda image: np.full((h,w),2.5,dtype=np.float32)
        def rgb(**kwargs):
            mask=kwargs['mask_image'][...,None]
            return Image.fromarray(np.round(np.clip(kwargs['image']*mask+.5*(1-mask),0,1)*255).astype(np.uint8))
        system.rgb=rgb
        poses=np.repeat(np.eye(4)[None,:3,:],2,axis=0); poses[1,0,3]=-.15
        original=ld.get_pcdGenPoses
        ld.get_pcdGenPoses=lambda name,args={}: poses if name=='probe' else original(name,args)
        image=Image.fromarray(np.random.default_rng(0).integers(0,256,(h,w,3),dtype=np.uint8))
        generator=torch.Generator
        with patch.object(torch,'Generator',lambda **kw:generator()):
            result=system.generate_pcd(image,'an indoor room','','probe',0,2)
        assert result['W']==w and result['H']==h
        assert result['pcd_points'].shape[1]>=w*h and np.isfinite(result['pcd_points']).all()
        assert len(result['frames'])==10
        assert all(f['image'].size==(w,h) for f in result['frames'])
        print('UPSTREAM_RECTANGULAR_PCD_ALIGNMENT_OK',len(result['frames']),flush=True)


if __name__=='__main__':main()
