"""Transfer the complete official studio camera template to the frozen kitchen."""
import argparse
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

from common import ROOT, sha256, source_check, write_json
import showcase
from viewcheck import BASELINE_INPUT_SHA256


def build(assets):
    baseline = showcase.build(2, assets)
    payload = (json.dumps(baseline, ensure_ascii=False, indent=2) + '\n').encode()
    if hashlib.sha256(payload).hexdigest() != BASELINE_INPUT_SHA256:
        raise ValueError('厨房基线输入与 70462 不一致')
    studio = showcase.official(5)
    if studio['resolution'] != baseline['resolution']:
        raise ValueError('模板与厨房目标分辨率不一致')
    # Official studio cameras are already expressed for its 704x480 image.
    out_wh = (studio['resolution'][2], studio['resolution'][1])
    if showcase.image_size(base64.b64decode(studio['image_prompt'].split(',')[-1])) != out_wh:
        raise ValueError('studio 模板原图尺寸变化，需重新核对目标内参')
    raw = base64.b64decode(baseline['image_prompt'].split(',')[-1])
    data = copy.deepcopy(baseline)
    data['cameras'], crop = showcase.transfer_intrinsics(studio['cameras'], showcase.image_size(raw), out_wh)
    data['image_index'] = studio['image_index']
    data['_showcase'].update(
        camera_policy='official_5_complete_template_with_inverse_crop_intrinsics',
        camera_template_image_index=studio['image_index'], crop=crop,
    )
    data['_studio_view'] = {
        'protocol': 'kitchen-studio-camera-v1', 'seed': 0,
        'baseline_run': 'showcase-02-70462-2',
        'baseline_input_sha256': BASELINE_INPUT_SHA256,
        'small_view_run': 'kitchen-small-70680-0',
        'camera_template': 'official-5', 'camera_template_run': 'studio_b1-70387-3',
        'camera_template_sha256': sha256(ROOT/'upstream/FlashWorld/examples/5.json'),
        'recipe_file_sha256': sha256(Path(__file__)),
        'normalization': 'upstream_per_trajectory', 'camera_calibrated': False,
        'changed_from_70462': ['camera_poses', 'target_intrinsics', 'image_index'],
        'input_anchor_video_seconds': studio['image_index'] * 1.0,
    }
    # Do not add _camera_control: this experiment uses native studio normalization.
    from experiment import validate_input
    validate_input(data)
    return data


def runtime_check(data):
    """Compare effective camera tensors against the unmodified studio template."""
    import torch
    sys.path.insert(0, str(ROOT/'upstream/FlashWorld'))
    import utils
    studio = showcase.official(5)
    crop = data['_showcase']['crop']
    effective = copy.deepcopy(data['cameras'])
    for camera in effective:
        camera['fx'] *= crop['scale']
        camera['fy'] *= crop['scale']
        camera['cx'] = (camera['cx'] - crop['crop_xywh'][0]) * crop['scale']
        camera['cy'] = (camera['cy'] - crop['crop_xywh'][1]) * crop['scale']

    def tensor(cameras):
        height, width = data['resolution'][1:]
        return torch.tensor([c['quaternion']+c['position']+
                             [c['fx']/width, c['fy']/height, c['cx']/width, c['cy']/height]
                             for c in cameras], dtype=torch.float32).unsqueeze(0)

    cameras, reference = tensor(effective), tensor(studio['cameras'])
    if not torch.allclose(cameras, reference, atol=1e-6, rtol=0):
        raise RuntimeError('裁剪后的有效相机与 studio 官方模板不一致')
    normalized, ref, scale = utils.normalize_cameras(cameras, return_meta=True)
    expected = utils.normalize_cameras(reference)
    dense = utils.sample_from_dense_cameras(cameras[0], torch.linspace(0, 1, 346)).unsqueeze(0)
    rendered = utils.normalize_cameras(dense, ref_w2c=ref, T_norm=scale)
    if not torch.allclose(normalized, expected, atol=2e-5, rtol=0):
        raise RuntimeError('归一化结果与官方 studio 不一致')
    if not torch.allclose(rendered[:, ::15], normalized, atol=2e-5, rtol=0):
        raise RuntimeError('视频与生成锚点不一致')
    anchor = normalized[:, data['image_index']:data['image_index']+1]
    for name, poses in (('generation', normalized), ('render', rendered)):
        distance = (poses[..., 4:7]-anchor[..., 4:7]).norm(dim=-1).max().item()
        dot = (torch.nn.functional.normalize(poses[..., :4], dim=-1) *
               torch.nn.functional.normalize(anchor[..., :4], dim=-1)).sum(-1).abs().clamp(0, 1)
        angle = (2*torch.acos(dot)*180/math.pi).max().item()
        if not torch.isfinite(poses).all() or not (26 < angle < 28 and .55 < distance < .57):
            raise RuntimeError(f'{name} studio 模板范围异常: {angle}, {distance}')
        print('STUDIO_CAMERA_MATCH_OK', name, 'angle_deg=', angle, 'translation=', distance, flush=True)
    if not torch.isfinite(scale).all() or scale.item() <= 0:
        raise RuntimeError('导出尺度必须有限且为正')
    print('STUDIO_EXPORT_SCALE_OK', scale.item(), 'input_anchor_seconds=', data['image_index'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'prepare'])
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    source_check()
    data = build(args.assets)
    if args.runtime:
        runtime_check(data)
    if args.command == 'prepare':
        if args.output is None:
            parser.error('prepare requires --output')
        args.output.mkdir(parents=True, exist_ok=False)
        write_json(args.output/'kitchen-studio.json', data)
    print('STUDIOVIEW_INPUT_OK', data['_studio_view'], flush=True)


if __name__ == '__main__':
    main()
