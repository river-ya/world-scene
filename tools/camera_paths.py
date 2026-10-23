"""Deterministic camera diversity from pinned official trajectories, not calibration."""
import copy
import math
import sys

from common import ROOT
import showcase
from viewcheck import quaternion_product as multiply, unit


ASSIGNMENTS = {3: 'room_short', 4: 'studio', 5: 'studio_mirrored',
               6: 'room_short', 7: 'studio_mirrored', 8: 'studio', 9: 'studio'}


def inverse(q):
    q = unit(q)
    return [q[0], -q[1], -q[2], -q[3]]


def rotate(q, vector):
    q = unit(q)
    return multiply(multiply(q, [0.] + list(vector)), inverse(q))[1:]


def slerp(a, b, fraction):
    a, b = unit(a), unit(b)
    dot = sum(x*y for x, y in zip(a, b))
    if dot < 0:
        b, dot = [-x for x in b], -dot
    if dot > .9995:
        return unit([x + fraction*(y-x) for x, y in zip(a, b)])
    angle = math.acos(min(1, dot))
    return unit([(math.sin((1-fraction)*angle)*x + math.sin(fraction*angle)*y)/math.sin(angle)
                 for x, y in zip(a, b)])


def mirror(cameras, anchor_index):
    """Reflect poses in the anchor camera's yz plane; keep the RGB unchanged.

    For S=diag(-1,1,1), local rotation becomes S R S (still det=+1),
    represented by quaternion (w,x,-y,-z). This is not a video reversal.
    """
    result = copy.deepcopy(cameras)
    anchor = cameras[anchor_index]
    q = unit(anchor['quaternion'])
    for target, source in zip(result, cameras):
        local = rotate(inverse(q), [a-b for a,b in zip(source['position'], anchor['position'])])
        local[0] = -local[0]
        target['position'] = [a+b for a,b in zip(anchor['position'], rotate(q, local))]
        relative = multiply(inverse(q), unit(source['quaternion']))
        reflected = [relative[0], relative[1], -relative[2], -relative[3]]
        target['quaternion'] = unit(multiply(q, reflected))
    result[anchor_index] = copy.deepcopy(anchor)
    return result


def template(profile):
    if profile in ('studio', 'studio_mirrored'):
        data = showcase.official(5)
        if profile == 'studio_mirrored':
            data['cameras'] = mirror(data['cameras'], data['image_index'])
        return data
    if profile != 'room_short':
        raise ValueError('未知相机轨迹: ' + str(profile))
    data = showcase.official(3)
    source = data['cameras'][:12]  # Exclude the large turn later in the full room path.
    cameras = []
    for i in range(24):
        t = i/9*3 if i <= 9 else 3 + (i-9)/14*8
        left = min(int(t), 10)
        fraction = t-left
        a, b = source[left], source[left+1]
        c = copy.deepcopy(a)
        c['quaternion'] = slerp(a['quaternion'], b['quaternion'], fraction)
        c['position'] = [x+(y-x)*fraction for x,y in zip(a['position'], b['position'])]
        for key in ('fx', 'fy', 'cx', 'cy'):
            c[key] = a[key]+(b[key]-a[key])*fraction
        cameras.append(c)
    cameras[9] = copy.deepcopy(source[3])
    data.update(cameras=cameras, image_index=9)
    return data


def stats(data):
    cameras = data['cameras']
    anchor = cameras[data['image_index']]
    scale = max(math.dist(c['position'], cameras[0]['position']) for c in cameras)
    q = unit(anchor['quaternion'])
    angles = [2*math.degrees(math.acos(min(1, abs(sum(a*b for a,b in zip(q, unit(c['quaternion'])))))))
              for c in cameras]
    return {'max_rotation_deg': max(angles),
            'max_translation_model_units': max(math.dist(c['position'], anchor['position']) for c in cameras)/(scale+.01),
            'export_scale': scale}


def runtime_check(data):
    """Validate effective K, native normalization, dense rendering and profile bounds."""
    import torch
    sys.path.insert(0, str(ROOT/'upstream/FlashWorld'))
    import utils
    profile = data['_gallery']['camera_profile']
    expected = template(profile)
    bounds = stats(expected)
    crop = data['_showcase']['crop']
    effective = copy.deepcopy(data['cameras'])
    for c in effective:
        c['fx'] *= crop['scale']; c['fy'] *= crop['scale']
        c['cx'] = (c['cx']-crop['crop_xywh'][0])*crop['scale']
        c['cy'] = (c['cy']-crop['crop_xywh'][1])*crop['scale']
    def tensor(cameras):
        height,width = data['resolution'][1:]
        return torch.tensor([c['quaternion']+c['position']+
                             [c['fx']/width,c['fy']/height,c['cx']/width,c['cy']/height]
                             for c in cameras],dtype=torch.float32).unsqueeze(0)
    cameras = tensor(effective)
    if data['image_index'] != 9 or not torch.allclose(cameras,tensor(expected['cameras']),atol=1e-6,rtol=0):
        raise RuntimeError('有效相机与选定轨迹不一致')
    normalized, ref, scale = utils.normalize_cameras(cameras,return_meta=True)
    dense = utils.sample_from_dense_cameras(cameras[0],torch.linspace(0,1,346)).unsqueeze(0)
    rendered = utils.normalize_cameras(dense,ref_w2c=ref,T_norm=scale)
    if not torch.allclose(rendered[:,::15],normalized,atol=2e-5,rtol=0):
        raise RuntimeError('视频与生成锚点不一致')
    anchor = normalized[:,9:10]
    for name,poses in (('generation',normalized),('render',rendered)):
        distance = (poses[...,4:7]-anchor[...,4:7]).norm(dim=-1).max().item()
        dot = (torch.nn.functional.normalize(poses[...,:4],dim=-1)*torch.nn.functional.normalize(anchor[...,:4],dim=-1)).sum(-1).abs().clamp(0,1)
        angle = (2*torch.acos(dot)*180/math.pi).max().item()
        if (not torch.isfinite(poses).all() or distance > bounds['max_translation_model_units']+.0001
                or angle > bounds['max_rotation_deg']+.03):
            raise RuntimeError(f'{profile} {name} 超出轨迹边界: {angle}, {distance}')
        print('CAMERA_PROFILE_OK',profile,name,'angle_deg=',angle,'translation=',distance,flush=True)
    if not math.isclose(scale.item(),bounds['export_scale'],rel_tol=1e-5) or scale.item() <= 0:
        raise RuntimeError('导出尺度错误')
