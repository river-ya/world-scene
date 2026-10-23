"""Separate, pinned LucidDreamer assets and receipts; never touch FlashWorld caches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from common import ROOT, now, sha256, write_json

LOCK = ROOT/'configs/lucid.lock.json'


def spec():
    return json.loads(LOCK.read_text())


def source_check():
    for component, record in spec()['sources'].items():
        for name, expected in record['files'].items():
            path = ROOT/'upstream'/component/name
            if not path.is_file() or sha256(path) != expected:
                raise RuntimeError(f'第二模型源码不匹配: {component}/{name}')


def paths(root):
    root=Path(root).resolve()
    return root/'sd-inpainting', root/'ZoeD_M12_N.pt'


def fingerprint(path):
    s=path.stat()
    return {'size':s.st_size, 'mtime_ns':s.st_mtime_ns}


def check_sd_file(path, record):
    if not path.is_file() or path.stat().st_size != record['size']:
        raise RuntimeError('资产缺失或长度错误: '+str(path))
    if record['algorithm']=='sha256':
        actual=sha256(path)
    else:
        h=hashlib.sha1(f'blob {path.stat().st_size}\0'.encode()); h.update(path.read_bytes())
        actual=h.hexdigest()
    if actual != record['digest']:
        raise RuntimeError('资产摘要不匹配: '+str(path))


def verify(root, quick=False):
    root=Path(root).resolve(); sd, zoe=paths(root)
    old=json.loads((root/'receipt.json').read_text()) if (root/'receipt.json').exists() else None
    if quick:
        if not old or old['lock_sha256'] != sha256(LOCK):
            raise RuntimeError('缺少第二模型完整校验回执；先运行 lucid_assets.py verify')
        expected={'sd-inpainting/'+f['path'] for f in spec()['sd']['files']} | {zoe.name}
        if set(old['files']) != expected:
            raise RuntimeError('第二模型校验回执文件清单不完整')
        for name, record in old['files'].items():
            p=root/name
            if not p.is_file() or fingerprint(p) != record['stat']:
                raise RuntimeError('资产状态改变，需要完整校验: '+str(p))
        zoe_provenance=json.loads((root/'zoe.download.json').read_text())
        if zoe_provenance['sha256'] != old['files'][zoe.name]['sha256']:
            raise RuntimeError('ZoeDepth 下载回执与资产回执不一致')
        return old
    files={}
    for record in spec()['sd']['files']:
        path=sd/record['path']; check_sd_file(path,record)
        files[str(path.relative_to(root))]={'sha256':sha256(path),'stat':fingerprint(path)}
    if not zoe.is_file() or zoe.stat().st_size < 100_000_000:
        raise RuntimeError('ZoeDepth 权重缺失或截断')
    digest=sha256(zoe)
    # The original release has no published SHA256 in our source lock. TOFU is
    # explicit; subsequent verification NEVER silently trusts a changed weight.
    zoe_lock=root/'zoe.download.json'
    if not zoe_lock.is_file():
        raise RuntimeError('缺少 ZoeDepth 首次下载回执，请用 download 命令获取')
    provenance=json.loads(zoe_lock.read_text())
    if provenance['url'] != spec()['zoe']['url'] or provenance['sha256'] != digest:
        raise RuntimeError('ZoeDepth 与首次下载摘要不符；拒绝自动更新回执')
    files[zoe.name]={'sha256':digest,'stat':fingerprint(zoe)}
    receipt={'created_at':now(),'lock_sha256':sha256(LOCK),'files':files,
             'zoe_digest_origin':'first_download_from_pinned_release_URL_not_publisher_digest'}
    write_json(root/'receipt.json',receipt)
    return receipt


def download(root):
    import fcntl
    from huggingface_hub import hf_hub_download
    root=Path(root).resolve(); root.mkdir(parents=True,exist_ok=True)
    with (root/'.download.lock').open('w') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX | fcntl.LOCK_NB)
        sd,zoe=paths(root)
        for f in spec()['sd']['files']:
            hf_hub_download(spec()['sd']['repo'], f['path'], revision=spec()['sd']['revision'],
                            local_dir=str(sd), local_dir_use_symlinks=False)
            check_sd_file(sd/f['path'],f)
        if not zoe.exists():
            part=zoe.with_suffix('.pt.part')
            subprocess.run(['curl','--fail','--location','--retry','5','--continue-at','-',
                            '--output',str(part),spec()['zoe']['url']],check=True)
            if part.stat().st_size < 100_000_000:
                raise RuntimeError('ZoeDepth 下载长度异常')
            os.replace(part,zoe)
        if not (root/'zoe.download.json').exists():
            write_json(root/'zoe.download.json',{'url':spec()['zoe']['url'],
                       'sha256':sha256(zoe),'bytes':zoe.stat().st_size,'downloaded_at':now()})
        verify(root)


def preflight(root):
    """CPU-only dependency and offline-path check. Full model loading is GPU check."""
    source_check(); receipt=verify(root,quick=True)
    import importlib
    import importlib.metadata as metadata
    required={'torch':'2.0.1','torchvision':'0.15.2','diffusers':'0.23.1',
              'transformers':'4.35.2','huggingface-hub':'0.25.2','numpy':'1.24.4',
              'timm':'0.6.7','open3d':'0.18.0'}
    for package,version in required.items():
        if metadata.version(package).split('+')[0] != version:
            raise RuntimeError(f'{package} 必须为 {version}；请使用独立 LUCID_ENV')
    for module in ['torch','diffusers','transformers','open3d','cv2',
                   'depth_diff_gaussian_rasterization_min','simple_knn._C','imageio_ffmpeg']:
        importlib.import_module(module)
    import torch
    if torch.version.cuda != '11.8':
        raise RuntimeError('LucidDreamer 环境要求 torch cu118')
    from transformers import CLIPTokenizer
    sd,_=paths(root)
    tokenizer=CLIPTokenizer.from_pretrained(str(sd/'tokenizer'),local_files_only=True)
    assert len(tokenizer('an indoor room')['input_ids']) > 2
    # Verify image dimensions/inputs before requesting a GPU; remove every temporary file.
    from lucid_inputs import prepare
    with tempfile.TemporaryDirectory(prefix='lucid-preflight-') as temp:
        prepare(1,os.environ.get('SCENE_ASSETS',''),Path(temp)/'inputs')
    print('LUCID_OFFLINE_PREFLIGHT_OK',len(receipt['files']),'files',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['download','verify','preflight','source-check'])
    p.add_argument('--root',type=Path,default=os.getenv('LUCID_ASSETS'))
    p.add_argument('--quick',action='store_true')
    a=p.parse_args()
    if a.command=='source-check': source_check(); print('LUCID_SOURCE_OK'); return
    if a.root is None: p.error('--root or LUCID_ASSETS is required')
    if a.command=='download': download(a.root)
    elif a.command=='verify': verify(a.root,a.quick); print('LUCID_ASSETS_OK')
    else: preflight(a.root)


if __name__=='__main__':main()
