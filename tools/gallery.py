"""Remaining seven showcases with explicit, reproducible camera diversity."""
import argparse
import base64
import copy
from pathlib import Path

from common import ROOT, sha256, source_check, write_json
import showcase
from camera_paths import ASSIGNMENTS, runtime_check, stats, template


CAMPAIGN = 'indoor-showcase-varied-v3'


def task_indices(value):
    indices = showcase.task_indices(value)
    if any(index < 3 for index in indices):
        raise ValueError('gallery 仅接受 3–9；0、1、2 复用已完成结果')
    return indices


def build(index, assets):
    if type(index) is not int or not 3 <= index <= 9:
        raise ValueError('gallery 索引必须在 3–9 之间')
    original = showcase.build(index, assets)
    data = copy.deepcopy(original)
    profile = ASSIGNMENTS[index]
    cameras = template(profile)
    if data['resolution'] != cameras['resolution']:
        raise ValueError('展示与相机模板分辨率不一致')
    raw = base64.b64decode(data['image_prompt'].split(',')[-1])
    data['cameras'], crop = showcase.transfer_intrinsics(cameras['cameras'], showcase.image_size(raw))
    data['image_index'] = cameras['image_index']
    data['_showcase'].update(
        campaign=CAMPAIGN, crop=crop,
        camera_policy=profile + '_with_inverse_crop_intrinsics',
        camera_template_image_index=9,
        recipe_file_sha256=sha256(Path(__file__)),
    )
    if index != 9:
        data['_showcase']['camera_calibrated'] = False
    if index == 8:
        data['_showcase']['variation'] = 'regenerate_with_complete_studio_camera_template; not asset_rerender'
    data['_gallery'] = {
        'campaign': CAMPAIGN, 'index': index, 'seed': 0,
        'source_recipe_file_sha256': original['_showcase']['recipe_file_sha256'],
        'camera_profile': profile,
        'camera_profile_stats': stats(cameras),
        'camera_recipe_file_sha256': sha256(ROOT/'tools/camera_paths.py'),
        'camera_template_sha256': sha256(ROOT/('upstream/FlashWorld/examples/3.json' if profile == 'room_short' else 'upstream/FlashWorld/examples/5.json')),
        'profile_gpu_validation': 'studio_template_only; transformed_profiles_pending',
        'normalization': 'upstream_per_trajectory',
        'input_anchor_video_seconds': 9,
        'comparison': ('complete_camera_template_variant_of_room_b1' if index == 8
                       else 'text_only_variant_of_studio_b1' if index == 9
                       else 'frozen_development_image_with_assigned_camera_profile'),
    }
    from experiment import validate_input
    validate_input(data)
    return data


def verify(assets, array, runtime=False):
    for index in task_indices(array):
        data = build(index, assets)
        if runtime:
            runtime_check(data)
        print('GALLERY_CASE_OK', index, showcase.cases()[index]['source'], flush=True)
    print('GALLERY_INPUTS_OK', CAMPAIGN, array, flush=True)


def prepare(assets, index, output, runtime=False):
    data = build(index, assets)
    if runtime:
        runtime_check(data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/f'gallery-{index:02d}.json', data)
    print('GALLERY_PREPARED', index, showcase.cases()[index]['source'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('verify')
    check.add_argument('--array', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--index', type=int, required=True)
    prep.add_argument('--output', type=Path, required=True)
    for command in (check, prep):
        command.add_argument('--assets', type=Path, required=True)
        command.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    source_check()
    if args.command == 'verify':
        verify(args.assets, args.array, args.runtime)
    else:
        prepare(args.assets, args.index, args.output, args.runtime)


if __name__ == '__main__':
    main()
