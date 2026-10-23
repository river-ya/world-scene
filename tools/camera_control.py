"""Scoped, explicit reference scale for a camera-only diagnostic protocol."""
from contextlib import contextmanager
from functools import wraps
import importlib
import json
import math
from pathlib import Path
import sys


POLICY = 'fixed_reference_translation_scale_v1'


def input_control(inputs):
    controls = [json.loads(p.read_text()).get('_camera_control')
                for p in sorted(Path(inputs).glob('*.json'))]
    if not controls:
        raise ValueError('无输入 JSON')
    first = controls[0]
    if any(item != first for item in controls):
        raise ValueError('同一进程不能混用相机归一化协议')
    if first is None:
        return None
    if not isinstance(first, dict) or set(first) != {'policy', 'reference_scale'}:
        raise ValueError('相机归一化协议字段错误')
    scale = first['reference_scale']
    if (first['policy'] != POLICY or type(scale) not in (int, float)
            or not math.isfinite(scale) or scale <= 0):
        raise ValueError('相机参考尺度必须有限且为正，协议必须受支持')
    return first


@contextmanager
def fixed_camera_scale(control, module=None):
    """Keep native math/export scaling; only supply an explicit positive T_norm.

    Enter before app.py imports utils.*. Render calls already carrying T_norm
    retain it, so generation, dense rendering and export share the same scale.
    """
    if control is None:
        yield
        return
    scale = control['reference_scale']
    if control['policy'] != POLICY or not math.isfinite(scale) or scale <= 0:
        raise ValueError('无效相机参考尺度')
    module = module if module is not None else importlib.import_module('utils')
    original = module.normalize_cameras

    @wraps(original)
    def normalized(cameras, return_meta=False, ref_w2c=None, T_norm=None, n_frame=None):
        if T_norm is None:
            T_norm = cameras.new_full((cameras.shape[0], 1, 1), scale)
        return original(cameras, return_meta=return_meta, ref_w2c=ref_w2c,
                        T_norm=T_norm, n_frame=n_frame)

    module.normalize_cameras = normalized
    try:
        yield
    finally:
        module.normalize_cameras = original
        # app imports utils with a star import; restore that copied binding too.
        app = sys.modules.get('app')
        if app is not None and getattr(app, 'normalize_cameras', None) is normalized:
            app.normalize_cameras = original
