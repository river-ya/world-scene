"""Scene-specific, fixed-center yaw paths for LucidDreamer generation/rendering.

The author supports rotation-only point-cloud generation (generate_seed). Exact
angles below are development presentation choices, not paper recommendations or
measured calibration. Positive anchor-local OpenGL yaw turns the view left.
"""
import copy
import math
from pathlib import Path

from camera_control import POLICY
from camera_paths import inverse, multiply, rotate, unit
from common import sha256


PROTOCOL = 'lucid-varied-yaw-v1'
PROFILES = {
    0: ('room', 40),
    1: ('studio', -50),
    2: ('kitchen_first', 45),
    3: ('living_dining', 65),
    4: ('hallway', 35),
    5: ('library', -60),
    6: ('office', -55),
    7: ('kitchen_second', 48),
    8: ('room_camera_variant', -58),
    9: ('studio_text_and_camera_variant', 52),
}


def yaw_at(index, frame, count=24):
    """Cubic easing slows both ends without changing the selected coverage."""
    if type(index) is not int or index not in PROFILES:
        raise ValueError('LucidDreamer 相机索引必须在 0–9')
    t = frame / (count - 1)
    return PROFILES[index][1] * t * t * (3 - 2*t)


def build(index, original):
    yaw_at(index, 0)  # Validate before dictionary indexing (bool is not an index).
    if original['resolution'] != [24, 480, 704] or len(original['cameras']) != 24:
        raise ValueError('新相机协议要求 24 个视角、704×480')
    data = copy.deepcopy(original)
    source_cameras = original['cameras']
    anchor_index = original['image_index']
    anchor = source_cameras[anchor_index]
    reference = max(math.dist(c['position'], source_cameras[0]['position'])
                    for c in source_cameras)
    if not math.isfinite(reference) or reference <= 0:
        raise ValueError('原轨迹参考尺度必须有限且为正')
    cameras = []
    for frame in range(24):
        c = copy.deepcopy(anchor)
        yaw = math.radians(yaw_at(index, frame))
        c['quaternion'] = unit(multiply(anchor['quaternion'],
                              [math.cos(yaw/2), 0., math.sin(yaw/2), 0.]))
        cameras.append(c)
    cameras[0] = copy.deepcopy(anchor)
    data.update(cameras=cameras, image_index=0)
    # Keep the historical source recipe as provenance, not an active gallery
    # declaration: the new cameras are no longer gallery's template.
    previous = data.pop('_gallery', None)
    showcase = data.setdefault('_showcase', {})
    showcase.update(source_camera_policy=showcase.get('camera_policy'),
                    campaign=PROTOCOL,
                    camera_policy='fixed_center_anchor_local_horizontal_yaw',
                    camera_calibrated=False, camera_template_image_index=0)
    if index == 9:
        showcase['variation'] = 'text_and_camera_variant; not_text_only_ablation'
    data['_camera_control'] = {'policy': POLICY, 'reference_scale': reference}
    scene, target = PROFILES[index]
    data['_lucid_camera'] = {
        'protocol': PROTOCOL, 'index': index, 'scene': scene,
        'signed_yaw_deg': target, 'direction': 'left' if target > 0 else 'right',
        'motion': 'fixed_center_anchor_local_horizontal_yaw',
        'easing': 'smoothstep_3t2_minus_2t3_at_24_keyframes; dense_slerp',
        'source_image_index': anchor_index, 'image_anchor_index': 0,
        'input_anchor_video_seconds': 0, 'translation_model_units': 0,
        'max_keyframe_step_deg': max(abs(yaw_at(index, i+1)-yaw_at(index, i))
                                     for i in range(23)),
        'reference_scale_source': 'unchanged_legacy_case_translation_extent',
        'reference_scale': reference,
        'source_gallery_profile': previous['camera_profile'] if previous else None,
        'recipe_file_sha256': sha256(Path(__file__)),
        'angle_basis': 'development_showcase_choice; not calibrated or paper-prescribed',
        'visual_validation': 'pending_4090_generation_and_review',
        'comparison': 'new_camera_protocol; use_saved_flashworld_json_for_matched_rerun',
        'text_variant_warning': 'case_9_also_changes_camera_vs_case_1; not_text_only_ablation',
    }
    return data


def validate_protocol(protocol):
    """Check the actual generation AND dense render poses before GPU loading."""
    info = protocol['camera_profile']
    index = info['index']
    yaw_at(index, 0)
    target = PROFILES[index][1]
    if (info['protocol'] != PROTOCOL or info['signed_yaw_deg'] != target
            or info['direction'] != ('left' if target > 0 else 'right')
            or protocol['resolution'] != [24, 480, 704]
            or protocol['image_index'] != 0 or protocol['fps'] != 15
            or protocol['generation_order'] != list(range(24))):
        raise ValueError('LucidDreamer 相机协议、方向、锚点或生成顺序错误')
    control = protocol['camera_control']
    scale = control['reference_scale']
    if (control['policy'] != POLICY or type(scale) not in (int, float)
            or not math.isfinite(scale) or scale <= 0
            or scale != info['reference_scale']
            or not math.isclose(protocol['translation_denominator'], scale+.01)):
        raise ValueError('纯旋转轨迹必须使用正参考尺度')
    keyframes, dense = protocol['cameras'], protocol['render_cameras']
    if len(keyframes) != 24 or len(dense) != 346:
        raise ValueError('生成或视频相机数错误')
    anchor = keyframes[0]
    largest_step = 0.
    previous = 0.
    for name, cameras, fps in (('generation', keyframes, 1), ('render', dense, 15)):
        for frame, c in enumerate(cameras):
            values = c['quaternion'] + c['position'] + [c[k] for k in ('fx','fy','cx','cy')]
            if (not all(math.isfinite(v) for v in values)
                    or abs(sum(v*v for v in c['quaternion'])-1) > 1e-6
                    or max(abs(v) for v in c['position']) > 1e-7
                    or c['fx'] <= 0 or c['fy'] <= 0
                    or any(abs(c[k]-anchor[k]) > 1e-6 for k in ('fx','fy','cx','cy'))):
                raise ValueError('非有限相机、平移、变焦或非单位旋转')
            relative = multiply(inverse(anchor['quaternion']), c['quaternion'])
            forward, up = rotate(relative, [0,0,-1]), rotate(relative, [0,1,0])
            actual = math.degrees(math.atan2(-forward[0], -forward[2]))
            left = min(frame//fps, 22)
            fraction = (frame-left*fps)/fps
            expected = yaw_at(index, left)*(1-fraction) + yaw_at(index, left+1)*fraction
            # camera_paths.slerp uses normalized lerp for very close poses.
            if (abs(actual-expected) > 2e-4 or abs(forward[1]) > 1e-7
                    or max(abs(a-b) for a,b in zip(up, [0,1,0])) > 1e-7):
                raise ValueError(f'{name} 实际光线方向与声明的水平转角不一致')
            if name == 'generation':
                largest_step = max(largest_step, abs(actual-previous))
                previous = actual
    if largest_step > 5 or not math.isclose(largest_step, info['max_keyframe_step_deg'], abs_tol=1e-5):
        raise ValueError('相邻生成视角转动过大或步长记录错误')
    if max(abs(a-b) for a,b in zip(anchor['quaternion'], [1,0,0,0])) > 1e-6:
        raise ValueError('输入锚点必须是局部坐标原点的单位旋转')
    print('LUCID_CAMERA_OK', index, info['direction'], abs(target),
          'deg; max_step=', round(largest_step, 4), 'frames=24/346', flush=True)
