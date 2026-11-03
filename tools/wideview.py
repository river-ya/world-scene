"""Expand remaining gallery views with fixed, scene-specific horizontal turns."""
import argparse
import copy
import math
from pathlib import Path
import sys

from common import ROOT, sha256, source_check, write_json
from camera_control import POLICY, fixed_camera_scale
from camera_paths import multiply, unit
import gallery
import showcase


PROTOCOL = 'gallery-wide-horizontal-v1'
# Signed anchor-local OpenGL yaw: positive turns left, negative turns right.
# These are development showcase choices, not calibrated camera measurements.
PROFILES = {
    4: ('hallway', 55),
    5: ('library', -60),
    6: ('office', -65),
    7: ('kitchen', 60),
    8: ('room', -55),
    9: ('studio', 65),
}


def case_name(index):
    if type(index) is not int or index not in PROFILES:
        raise ValueError('wideview 仅接受索引 4–9；客厅三档复用既有结果')
    return f'wideview-{index:02d}'


def task_indices(value):
    indices = showcase.task_indices(value)
    for index in indices:
        case_name(index)
    return indices


def build(index, assets):
    name = case_name(index)
    scene, signed_yaw = PROFILES[index]
    original = gallery.build(index, assets)
    data = copy.deepcopy(original)
    anchor = original['cameras'][original['image_index']]
    q = unit(anchor['quaternion'])
    count = len(original['cameras'])
    cameras = []
    for frame in range(count):
        camera = copy.deepcopy(anchor)
        yaw = math.radians(signed_yaw*frame/(count-1))
        camera['quaternion'] = unit(multiply(q, [math.cos(yaw/2), 0., math.sin(yaw/2), 0.]))
        cameras.append(camera)
    cameras[0] = copy.deepcopy(anchor)
    data.update(cameras=cameras, image_index=0)
    previous = data.pop('_gallery')
    data['_showcase'].update(
        campaign=PROTOCOL, kind='wide_camera_variant',
        camera_policy='fixed_center_anchor_local_horizontal_yaw',
        camera_calibrated=False, camera_template_image_index=0,
        variation='camera_condition_variant_of_gallery; original_text_retained',
        recipe_file_sha256=sha256(Path(__file__)),
    )
    data['_camera_control'] = {
        'policy': POLICY,
        'reference_scale': previous['camera_profile_stats']['export_scale'],
    }
    data['_wideview'] = {
        'protocol': PROTOCOL, 'index': index, 'scene': scene, 'case_name': name,
        'signed_yaw_deg': signed_yaw,
        'yaw_direction': 'left' if signed_yaw > 0 else 'right',
        'max_rotation_deg': abs(signed_yaw), 'translation_model_units': 0,
        'image_anchor_index': 0, 'input_anchor_video_seconds': 0,
        'reference_run': f'gallery-{index:02d}-71013-{index}',
        'reference_gallery_profile': previous['camera_profile'],
        'reference_scale_source': 'same_gallery_profile_export_scale',
        'recipe_file_sha256': sha256(Path(__file__)),
        'source_gallery_recipe_sha256': sha256(ROOT/'tools/gallery.py'),
        'seed': 0, 'gpu_visual_validation': 'pending',
        'comparison': 'same_image_and_text; new_camera_protocol; not_single_factor_yaw_ablation_against_old_gallery',
        'text_variant_warning': 'index_9_is_not_text_only_comparison_against_original_studio',
    }
    from experiment import validate_input
    validate_input(data)
    return data


def runtime_check(data):
    """Verify signed yaw and fixed center through actual upstream CPU math."""
    import torch
    sys.path.insert(0, str(ROOT/'upstream/FlashWorld'))
    import utils
    index = data['_wideview']['index']
    case_name(index)
    target = PROFILES[index][1]
    if data['image_index'] != 0 or data['_wideview']['signed_yaw_deg'] != target:
        raise RuntimeError('wideview 锚点或已声明的转角与固定方案不一致')
    _, h, w = data['resolution']
    if data['resolution'] != [24, 480, 704] or len(data['cameras']) != 24:
        raise RuntimeError('wideview 要求 24 个相机、704×480')
    crop = data['_showcase']['crop']
    s = crop['scale']; x, y = crop['crop_xywh'][:2]
    values = [c['quaternion'] + c['position'] +
              [c['fx']*s/w, c['fy']*s/h, (c['cx']-x)*s/w, (c['cy']-y)*s/h]
              for c in data['cameras']]
    cameras = torch.tensor(values, dtype=torch.float32).unsqueeze(0)
    dense = utils.sample_from_dense_cameras(cameras[0], torch.linspace(0, 1, 346)).unsqueeze(0)
    with fixed_camera_scale(data['_camera_control'], module=utils):
        normalized, ref, scale = utils.normalize_cameras(cameras, return_meta=True)
        rendered = utils.normalize_cameras(dense, ref_w2c=ref, T_norm=scale)
    for name, poses in [('generation', normalized), ('render', rendered)]:
        rotation = utils.quaternion_to_matrix(poses[0, :, :4])
        forward = -rotation[..., :, 2]
        yaw = torch.atan2(-forward[:, 0], -forward[:, 2])*180/math.pi
        up = rotation[..., :, 1]
        distance = poses[0, :, 4:7].norm(dim=-1).max().item()
        if (not torch.isfinite(poses).all() or distance > 2e-5
                or not torch.allclose(yaw, torch.linspace(0, target, len(yaw)), atol=2e-3, rtol=0)
                or not torch.allclose(up, torch.tensor([0., 1., 0.]).expand_as(up), atol=2e-5, rtol=0)
                or not torch.allclose(poses[..., 7:], cameras[:, :1, 7:].expand_as(poses[..., 7:]), atol=2e-6, rtol=0)):
            raise RuntimeError(f'{name} 实际转角/方向、平移、竖直轴或内参偏离固定方案')
        print('WIDEVIEW_CAMERA_OK', index, name, 'signed_yaw_deg=', yaw[-1].item(),
              'max_translation=', distance, flush=True)
    if scale.item() <= 0 or not math.isclose(scale.item(), data['_camera_control']['reference_scale'], rel_tol=1e-6):
        raise RuntimeError('纯旋转导出参考尺度必须保持为指定正数')
    if not torch.allclose(rendered[:, ::15], normalized, atol=2e-5, rtol=0):
        raise RuntimeError('生成和视频相机不一致')
    _, rays = utils.create_rays(normalized, 2, 2)
    delta_x = (rays[0, -1, ..., 0].mean()-rays[0, 0, ..., 0].mean()).item()
    if not torch.isfinite(rays).all() or delta_x*target >= 0:
        raise RuntimeError('实际光线未朝指定侧面展开')
    print('WIDEVIEW_EXPORT_SCALE_OK', index, scale.item(), flush=True)


def prepare(assets, index, output, runtime=False):
    data = build(index, assets)
    if runtime:
        runtime_check(data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/(case_name(index)+'.json'), data)
    print('WIDEVIEW_PREPARED', case_name(index), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('verify'); check.add_argument('--array', default='4-9%1')
    prep = sub.add_parser('prepare')
    prep.add_argument('--index', type=int, required=True)
    prep.add_argument('--output', type=Path, required=True)
    for cmd in [check, prep]:
        cmd.add_argument('--assets', type=Path, required=True)
        cmd.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    source_check()
    if args.command == 'prepare':
        prepare(args.assets, args.index, args.output, args.runtime)
    else:
        for index in task_indices(args.array):
            data = build(index, args.assets)
            if args.runtime:
                runtime_check(data)
            print('WIDEVIEW_INPUT_OK', case_name(index), data['_wideview']['signed_yaw_deg'], flush=True)


if __name__ == '__main__':
    main()
