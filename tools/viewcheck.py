"""Same kitchen as job 70462, bounded poses with a frozen reference scale."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

from camera_control import POLICY, fixed_camera_scale
from common import ROOT, sha256, source_check, write_json
import showcase


BASELINE_INPUT_SHA256 = 'e182b94ad596843bab13219695daf6d56289d7fe3e37f3028a19b1f122583369'
MAX_ANGLE_DEG = 5.0
MAX_TRANSLATION = 0.1


def quaternion_product(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return [w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j,
            w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v]


def unit(q):
    length = math.sqrt(sum(x*x for x in q))
    return [x/length for x in q]


def reference_scale():
    cameras = showcase.official(3)['cameras']
    return max(math.dist(c['position'], cameras[0]['position']) for c in cameras)


def build(assets):
    baseline = showcase.build(2, assets)
    payload = (json.dumps(baseline, ensure_ascii=False, indent=2) + '\n').encode()
    if hashlib.sha256(payload).hexdigest() != BASELINE_INPUT_SHA256:
        raise ValueError('基线输入不再与 70462 一致，拒绝隐式改变对照')
    data = copy.deepcopy(baseline)
    anchor_index = data['image_index']
    anchor = baseline['cameras'][anchor_index]
    q = unit(anchor['quaternion'])
    # Camera-local horizontal axis expressed in the original world coordinates.
    right = quaternion_product(quaternion_product(q, [0., 1., 0., 0.]),
                               [q[0], -q[1], -q[2], -q[3]])[1:]
    scale = reference_scale()
    for index, camera in enumerate(data['cameras']):
        fraction = ((index-anchor_index)/anchor_index if index <= anchor_index
                    else (index-anchor_index)/(len(data['cameras'])-1-anchor_index))
        angle = math.radians(MAX_ANGLE_DEG * fraction)
        camera['quaternion'] = unit(quaternion_product(q, [math.cos(angle/2), 0., math.sin(angle/2), 0.]))
        # The pinned normalizer divides by T_norm + 0.01, not T_norm alone.
        delta = MAX_TRANSLATION * fraction * (scale + 0.01)
        camera['position'] = [p + delta*r for p, r in zip(anchor['position'], right)]
    data['cameras'][anchor_index] = copy.deepcopy(anchor)
    data['_showcase']['camera_policy'] = 'anchor_local_yaw5_translation0.1_fixed_reference'
    data['_camera_control'] = {'policy': POLICY, 'reference_scale': scale}
    data['_viewcheck'] = {
        'protocol': 'kitchen-small-view-v1', 'baseline_run': 'showcase-02-70462-2',
        'baseline_version': '0.2.0', 'baseline_input_sha256': BASELINE_INPUT_SHA256,
        'recipe_file_sha256': sha256(Path(__file__)),
        'max_rotation_from_input_deg': MAX_ANGLE_DEG,
        'max_translation_from_input_model_units': MAX_TRANSLATION,
        'reference_scale_source': 'official_3_max_translation_from_first_camera',
        'camera_calibrated': False, 'seed': 0,
        'changed': ['camera_poses', 'camera_normalization_reference'],
    }
    from experiment import validate_input
    validate_input(data)
    return data


def runtime_check(data):
    """CPU tensor check against actual pinned upstream math; no model weights."""
    import torch
    sys.path.insert(0, str(ROOT/'upstream/FlashWorld'))
    import utils
    values = [c['quaternion'] + c['position'] + [c[k] for k in ('fx', 'fy', 'cx', 'cy')]
              for c in data['cameras']]
    cameras = torch.tensor(values, dtype=torch.float32).unsqueeze(0)
    dense = utils.sample_from_dense_cameras(cameras[0], torch.linspace(0, 1, 346)).unsqueeze(0)
    with fixed_camera_scale(data['_camera_control']):
        normalized, ref, scale = utils.normalize_cameras(cameras, return_meta=True)
        rendered = utils.normalize_cameras(dense, ref_w2c=ref, T_norm=scale)
    anchor = normalized[:, data['image_index']:data['image_index']+1]
    for name, poses in (('generation', normalized), ('render', rendered)):
        distance = (poses[..., 4:7]-anchor[..., 4:7]).norm(dim=-1).max().item()
        dot = (torch.nn.functional.normalize(poses[..., :4], dim=-1) *
               torch.nn.functional.normalize(anchor[..., :4], dim=-1)).sum(-1).abs().clamp(0, 1)
        angle = (2*torch.acos(dot)*180/math.pi).max().item()
        if not torch.isfinite(poses).all() or distance > 0.10002 or angle > 5.02:
            raise RuntimeError(f'{name} 相机越界: translation={distance}, angle={angle}')
        print('CAMERA_BOUNDS_OK', name, 'translation=', distance, 'angle_deg=', angle, flush=True)
    if scale.item() <= 0 or not math.isclose(scale.item(), reference_scale(), rel_tol=1e-6):
        raise RuntimeError('导出尺度错误或为零')
    if not torch.allclose(rendered[:, ::15], normalized, atol=2e-5):
        raise RuntimeError('生成和视频锚点相机不一致')
    print('CAMERA_EXPORT_SCALE_OK', scale.item(), flush=True)


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
        write_json(args.output/'kitchen-small.json', data)
    print('VIEWCHECK_INPUT_OK', data['_viewcheck'], flush=True)


if __name__ == '__main__':
    main()
