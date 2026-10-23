"""One frozen living-room image, three monotonic horizontal yaw conditions."""
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


ANGLES = (30, 45, 75)
PROTOCOL = 'living-room-left-yaw-v1'


def task_indices(value):
    indices = showcase.task_indices(value)
    if any(index not in range(len(ANGLES)) for index in indices):
        raise ValueError('ANGLES_ARRAY 只接受 0–2，例如 0-2%1 或 1,2%1')
    return indices


def case_name(index):
    if type(index) is not int or index not in range(len(ANGLES)):
        raise ValueError('角度任务索引必须为 0、1、2')
    return f'angles-living-left-{ANGLES[index]:02d}'


def build(index, assets):
    name = case_name(index)
    original = gallery.build(3, assets)
    data = copy.deepcopy(original)
    anchor = original['cameras'][original['image_index']]
    q = unit(anchor['quaternion'])
    count = len(original['cameras'])
    scale = original['_gallery']['camera_profile_stats']['export_scale']
    cameras = []
    for frame in range(count):
        camera = copy.deepcopy(anchor)
        angle = math.radians(ANGLES[index] * frame/(count-1))
        # GL c2w: forward is -Z. Positive local Y yaw turns towards local -X (left).
        camera['quaternion'] = unit(multiply(q, [math.cos(angle/2), 0., math.sin(angle/2), 0.]))
        cameras.append(camera)
    cameras[0] = copy.deepcopy(anchor)
    data.update(cameras=cameras, image_index=0)
    data.pop('_gallery')
    data['_showcase'].update(
        campaign=PROTOCOL, camera_policy='fixed_center_anchor_local_left_yaw',
        camera_template_image_index=0, recipe_file_sha256=sha256(Path(__file__)),
    )
    # Pure rotation has no measured translation extent. Keep a fixed positive
    # reference for both normalization and Gaussian export, never a zero scale.
    data['_camera_control'] = {'policy': POLICY, 'reference_scale': scale}
    data['_angles'] = {
        'protocol': PROTOCOL, 'task_index': index, 'case_name': name,
        'source_gallery_index': 3, 'reference_run': 'gallery-03-71013-3',
        'source_gallery_recipe_sha256': sha256(ROOT/'tools/gallery.py'),
        'recipe_file_sha256': sha256(Path(__file__)),
        'yaw_direction': 'anchor_local_left', 'max_yaw_deg': ANGLES[index],
        'translation_model_units': 0, 'image_anchor_index': 0,
        'input_anchor_video_seconds': 0, 'seed': 0,
        'reference_scale_source': 'gallery_03_room_short_export_scale',
        'comparison': 'only_yaw_amplitude_between_angles_conditions; old_gallery_is_context_only',
        'camera_calibrated': False, 'gpu_visual_validation': 'pending',
    }
    from experiment import validate_input
    validate_input(data)
    return data


def runtime_check(data):
    """Check actual pinned normalization, dense interpolation and ray direction on CPU."""
    import torch
    sys.path.insert(0, str(ROOT/'upstream/FlashWorld'))
    import utils
    crop = data['_showcase']['crop']
    x, y = crop['crop_xywh'][:2]
    s = crop['scale']
    _, h, w = data['resolution']
    values = [c['quaternion'] + c['position'] +
              [c['fx']*s/w, c['fy']*s/h, (c['cx']-x)*s/w, (c['cy']-y)*s/h]
              for c in data['cameras']]
    cameras = torch.tensor(values, dtype=torch.float32).unsqueeze(0)
    dense = utils.sample_from_dense_cameras(cameras[0], torch.linspace(0, 1, 346)).unsqueeze(0)
    with fixed_camera_scale(data['_camera_control'], module=utils):
        normalized, ref, scale = utils.normalize_cameras(cameras, return_meta=True)
        rendered = utils.normalize_cameras(dense, ref_w2c=ref, T_norm=scale)
    expected_max = data['_angles']['max_yaw_deg']
    for name, poses in [('generation', normalized), ('render', rendered)]:
        rot = utils.quaternion_to_matrix(poses[0, :, :4])
        forward = -rot[..., :, 2]
        yaw = torch.atan2(-forward[:, 0], -forward[:, 2])*180/math.pi
        expected = torch.linspace(0, expected_max, len(yaw))
        distance = poses[0, :, 4:7].norm(dim=-1).max().item()
        up = rot[..., :, 1]
        if (not torch.isfinite(poses).all() or distance > 2e-5
                or not torch.allclose(yaw, expected, atol=2e-3)
                or not torch.allclose(up, torch.tensor([0., 1., 0.]).expand_as(up), atol=2e-5)
                or not torch.allclose(poses[..., 7:], cameras[:, :1, 7:].expand_as(poses[..., 7:]), atol=2e-6)):
            raise RuntimeError(f'{name} 相机方向、幅度、平移或内参错误')
        print('ANGLES_CAMERA_OK', name, 'left_yaw_deg=', yaw[-1].item(),
              'max_translation=', distance, flush=True)
    if not math.isclose(scale.item(), data['_camera_control']['reference_scale'], rel_tol=1e-6) or scale.item() <= 0:
        raise RuntimeError('纯旋转路径导出参考尺度错误')
    if not torch.allclose(rendered[:, ::15], normalized, atol=2e-5):
        raise RuntimeError('生成与视频的相机不一致')
    # Exercise actual upstream ray construction; image center must turn left.
    _, rays = utils.create_rays(normalized, 2, 2)
    if not torch.isfinite(rays).all() or rays[0, -1, ..., 0].mean() >= rays[0, 0, ..., 0].mean():
        raise RuntimeError('实际光线未向输入相机左侧展开')
    print('ANGLES_EXPORT_SCALE_OK', scale.item(), flush=True)


def prepare(assets, index, output, runtime=False):
    data = build(index, assets)
    if runtime:
        runtime_check(data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/(case_name(index)+'.json'), data)
    print('ANGLES_PREPARED', case_name(index), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--array', default='0-2%1')
    prep = sub.add_parser('prepare')
    prep.add_argument('--index', type=int, required=True)
    prep.add_argument('--output', type=Path, required=True)
    for command in [verify, prep]:
        command.add_argument('--assets', type=Path, required=True)
        command.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    source_check()
    if args.command == 'prepare':
        prepare(args.assets, args.index, args.output, args.runtime)
    else:
        for index in task_indices(args.array):
            data = build(index, args.assets)
            if args.runtime:
                runtime_check(data)
            print('ANGLES_INPUT_OK', case_name(index), flush=True)


if __name__ == '__main__':
    main()
