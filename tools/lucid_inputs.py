"""Identical FlashWorld image preprocessing; explicit GL -> CV pose conversion."""
import argparse
import base64
import copy
import io
import json
import math
from pathlib import Path

from common import ROOT, sha256, source_check, write_json
from camera_paths import inverse, multiply, rotate, slerp
import showcase

PROTOCOL = 'lucid-flash-inputs-v1'


def source_input(index, assets):
    if index in (0, 1):
        return showcase.official(3 if index == 0 else 5)
    if index == 2:
        from studioview import build
        return build(assets)
    if 3 <= index <= 9:
        from gallery import build
        return build(index, assets)
    raise ValueError('案例索引必须在 0–9')


def crop_parameters(size, output_size):
    w, h = size
    ow, oh = output_size
    scale = max(oh/h, ow/w)
    nw, nh = int(ow/scale), int(oh/scale)
    return ((w-nw)//2, (h-nh)//2, nw, nh), scale


def relative_cameras(cameras, anchor_index):
    """Anchor-local OpenGL c2w; the SAME translation denominator as FlashWorld.

    This defines a numerical model-unit protocol, not a metric-scale calibration
    between learned FlashWorld geometry and ZoeDepth geometry.
    """
    anchor = cameras[anchor_index]
    scale = max(math.dist(c['position'], cameras[0]['position']) for c in cameras)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('轨迹尺度必须为正')
    result = []
    for c in cameras:
        r = copy.deepcopy(c)
        r['quaternion'] = multiply(inverse(anchor['quaternion']), c['quaternion'])
        r['position'] = [v/(scale+.01) for v in rotate(inverse(anchor['quaternion']),
                          [x-y for x,y in zip(c['position'], anchor['position'])])]
        result.append(r)
    return result, scale


def dense_cameras(cameras, fps=15):
    result = []
    for i in range((len(cameras)-1)*fps+1):
        left = min(i//fps, len(cameras)-2)
        f = (i-left*fps)/fps
        a, b = cameras[left:left+2]
        r = {'quaternion': slerp(a['quaternion'], b['quaternion'], f)}
        r['position'] = [x+(y-x)*f for x,y in zip(a['position'], b['position'])]
        for k in ('fx', 'fy', 'cx', 'cy'):
            r[k] = a[k]+(b[k]-a[k])*f
        result.append(r)
    return result


def cv_w2c(cameras):
    import numpy as np
    flip = np.diag([1., -1., -1., 1.])
    result = []
    for c in cameras:
        # Quaternion convention is wxyz, and columns are the rotated basis axes.
        m = np.eye(4)
        m[:3, :3] = np.array([rotate(c['quaternion'], v) for v in np.eye(3)]).T
        m[:3, 3] = c['position']
        result.append(np.linalg.inv(flip @ m @ flip))
    return np.asarray(result, dtype=np.float32)


def projection(camera, width, height, near=.01, far=100.):
    """CV (+Z forward), including principal point; column-vector convention.

    Gaussian rasterizer maps NDC to pixel centers as ((ndc+1)*S-1)/2.
    Here K uses FlashWorld's pixel-corner convention (ray at pixel + 0.5).
    """
    import numpy as np
    p = np.zeros((4,4), dtype=np.float32)
    p[0,0], p[1,1] = 2*camera['fx']/width, 2*camera['fy']/height
    p[0,2], p[1,2] = 2*camera['cx']/width-1, 2*camera['cy']/height-1
    p[2,2], p[2,3], p[3,2] = far/(far-near), -far*near/(far-near), 1
    return p


def prepare(index, assets, output):
    from PIL import Image
    source_check()
    data = source_input(index, assets)
    raw = base64.b64decode(data['image_prompt'].split(',')[-1])
    image = Image.open(io.BytesIO(raw)).convert('RGB')
    n, h, w = data['resolution']
    if len(data['cameras']) != n:
        raise ValueError('此版本要求相机数与生成帧数一致')
    (left, top, nw, nh), scale = crop_parameters(image.size, (w,h))
    # Explicit BICUBIC is PIL's RGB resize default used by pinned FlashWorld CLI.
    image = image.crop((left,top,left+nw,top+nh)).resize((w,h), Image.Resampling.BICUBIC)
    cameras = copy.deepcopy(data['cameras'])
    for c in cameras:
        c['fx'] *= scale; c['fy'] *= scale
        c['cx'] = (c['cx']-left)*scale; c['cy'] = (c['cy']-top)*scale
    if any(abs(c[k]-cameras[0][k]) > 1e-4 for c in cameras for k in ('fx','fy','cx','cy')):
        raise ValueError('LucidDreamer 本版不接受变焦轨迹')
    relative, translation_scale = relative_cameras(cameras, data['image_index'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'source.json', data)
    image.save(output/'input.png')
    (output/'prompt.txt').write_text(data['text_prompt']+'\n')
    anchor = data['image_index']
    # Input image MUST be at pose zero for LucidDreamer. Render keeps original order.
    order = [anchor] + list(range(anchor-1, -1, -1)) + list(range(anchor+1, n))
    protocol = {
        'protocol': PROTOCOL, 'case_index': index, 'source_sha256': sha256(output/'source.json'),
        'image_sha256': sha256(output/'input.png'), 'text_prompt': data['text_prompt'],
        'resolution': [n,h,w], 'image_index': anchor, 'fps': 15,
        'crop_xywh': [left,top,nw,nh], 'image_resize_scale': scale,
        'translation_denominator': translation_scale+.01,
        'coordinate_system': 'anchor_local_OpenGL_c2w; translations_in_FlashWorld_normalized_model_units',
        'metric_scale_alignment': 'unverified_no_ground_truth; ZoeDepth_native_depth_retained',
        'generation_order': order, 'cameras': relative,
        'render_cameras': dense_cameras(relative),
        'comparison_scope': 'qualitative_same_RGB_text_K_target_path; not calibrated metric benchmark',
    }
    write_json(output/'protocol.json', protocol)
    # This portable JSON can be run by FlashWorld if a shared-input rerun is wanted.
    flash = copy.deepcopy(data)
    flash['image_prompt'] = 'data:image/png;base64,'+base64.b64encode((output/'input.png').read_bytes()).decode()
    flash['cameras'] = cameras
    write_json(output/'flashworld.json', flash)
    print('LUCID_INPUT_OK', index, w, h, 'anchor=', anchor, flush=True)
    return protocol


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', type=int, required=True)
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args(); prepare(a.index,a.assets,a.output)


if __name__ == '__main__': main()
