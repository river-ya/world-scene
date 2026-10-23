"""Ten reproducible showcase cases; synthetic cameras are not calibration."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import re
import struct
from pathlib import Path

from common import ROOT, sha256, source_check, write_json


CAMPAIGN = "indoor-showcase-v1"
VARIANT_TEXT = (
    "A room with sound equipment. Keep the visible sound equipment and room "
    "layout unchanged. Extend warm wooden acoustic wall panels into newly "
    "revealed areas while keeping the floor space unobstructed."
)


def cases():
    result = [
        {"index": 0, "source": "official-3", "kind": "baseline",
         "reuse_run": "room_b1-70288-0"},
        {"index": 1, "source": "official-5", "kind": "baseline",
         "reuse_run": "studio_b1-70387-3"},
    ]
    result += [{"index": i + 2, "source": f"ws-indoor-{i:03d}",
                "kind": "baseline"} for i in range(6)]
    result += [
        {"index": 8, "source": "official-3", "kind": "camera_variant",
         "parent_index": 0},
        {"index": 9, "source": "official-5", "kind": "text_variant",
         "parent_index": 1},
    ]
    return result


def task_indices(value):
    """Validate Slurm's subset syntax before submitting any GPU job."""
    if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*%[1-4]", value):
        raise ValueError("SHOWCASE_ARRAY 必须类似 2%1、3-9%1 或 2,4,8%1")
    indices = []
    for item in value.split("%")[0].split(","):
        ends = [int(x) for x in item.split("-")]
        lo, hi = ends[0], ends[-1]
        if not 0 <= lo <= hi <= 9:
            raise ValueError("展示索引必须在 0–9 之间")
        indices.extend(range(lo, hi + 1))
    if len(set(indices)) != len(indices):
        raise ValueError("展示索引重复")
    return indices


def image_size(raw):
    """Read dimensions only; leave image bytes unchanged for upstream cropping."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and raw[12:16] == b"IHDR":
        width, height = struct.unpack(">II", raw[16:24])
    elif raw.startswith(b"\xff\xd8"):
        pos = 2
        while pos < len(raw):
            if raw[pos] != 0xFF:
                raise ValueError("JPEG marker 错误")
            while pos < len(raw) and raw[pos] == 0xFF:
                pos += 1
            marker = raw[pos]
            pos += 1
            if marker in (0xD9, 0xDA):
                raise ValueError("JPEG 缺少 SOF 尺寸")
            if marker in (0x01, *range(0xD0, 0xD9)):
                continue
            length = int.from_bytes(raw[pos:pos + 2], "big")
            if length < 2 or pos + length > len(raw):
                raise ValueError("JPEG segment 截断")
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", raw[pos + 3:pos + 7])
                break
            pos += length
        else:
            raise ValueError("无法读取 JPEG 尺寸")
    else:
        raise ValueError("展示输入仅接受已锁定的 PNG/JPEG")
    if width <= 0 or height <= 0:
        raise ValueError("无效图片尺寸")
    return width, height


def subset():
    return json.loads((ROOT / "configs/data/worldscore-indoor-v1.json").read_text())


def official(index):
    return json.loads((ROOT / f"upstream/FlashWorld/examples/{index}.json").read_text())


def transfer_intrinsics(cameras, size, output_size=(704, 480)):
    """Invert the pinned CLI crop/resize so final K equals the camera template."""
    width, height = size
    out_w, out_h = output_size
    scale = max(out_h / height, out_w / width)
    crop_h, crop_w = int(out_h / scale), int(out_w / scale)
    left, top = (width - crop_w) // 2, (height - crop_h) // 2
    result = copy.deepcopy(cameras)
    for camera in result:
        camera["fx"] /= scale
        camera["fy"] /= scale
        camera["cx"] = camera["cx"] / scale + left
        camera["cy"] = camera["cy"] / scale + top
    return result, {
        "original_size_wh": list(size), "output_size_wh": list(output_size),
        "scale": scale, "crop_xywh": [left, top, crop_w, crop_h],
        "policy": "pinned_cli_center_crop; inverse_intrinsics_transfer",
    }


def build(index, assets):
    if not 0 <= index < 10:
        raise ValueError("展示索引必须在 0–9 之间")
    spec = cases()[index]
    provenance = {
        "campaign": CAMPAIGN, **spec, "seed": 0,
        "protocol": "qualitative_development_showcase; not official WorldScore",
        "distinct_input_id": spec["source"],
    }
    if 2 <= index <= 7:
        frozen = subset()
        row = next(r for r in frozen["samples"] if r["id"] == spec["source"])
        if row["split"] != "dev":
            raise ValueError("展示开发不得使用保留测试样本")
        path = Path(assets) / "data/worldscore-indoor-v1" / row["local_image"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["image_sha256"]:
            raise ValueError("开发图片摘要变化: " + str(path))
        data = official(3)
        data["cameras"], crop = transfer_intrinsics(data["cameras"], image_size(raw))
        mime = "image/png" if raw.startswith(b"\x89PNG") else "image/jpeg"
        data["image_prompt"] = f"data:{mime};base64," + base64.b64encode(raw).decode()
        data["text_prompt"] = row["text"]
        provenance.update(
            source_revision=frozen["revision"], source_image=row["source_scene"],
            image_sha256=row["image_sha256"], split="dev", crop=crop,
            camera_policy="official_3_trajectory_and_target_K_as_synthetic_template",
            camera_calibrated=False, camera_template_image_index=3,
            source_camera_commands=row["original"]["camera_path"],
            source_camera_commands_executed=False,
        )
    else:
        source = 3 if index in (0, 8) else 5
        data = official(source)
        provenance.update(camera_policy=f"official_{source}_unchanged")
        if index == 8:
            other = official(5)
            # Change trajectory and anchor index only; keep the room's target K.
            intrinsics = [
                {key: c[key] for key in ("fx", "fy", "cx", "cy")}
                for c in data["cameras"]
            ]
            data["cameras"] = other["cameras"]
            for c, k in zip(data["cameras"], intrinsics):
                c.update(k)
            data["image_index"] = other["image_index"]
            provenance.update(
                camera_policy="official_5_trajectory_with_official_3_intrinsics",
                camera_calibrated=False,
                variation="regenerate_with_alternate_trajectory; not asset_rerender",
            )
        if index == 9:
            provenance["original_text"] = data["text_prompt"]
            provenance["variation"] = "unseen_region_text_request; not guaranteed editing"
            data["text_prompt"] = VARIANT_TEXT
    provenance["recipe_file_sha256"] = sha256(Path(__file__))
    data["_showcase"] = provenance
    from experiment import validate_input
    validate_input(data)
    return data


def verify(assets, array):
    indices = task_indices(array)
    for index in indices:
        build(index, assets)
    print("SHOWCASE_INPUTS_OK", CAMPAIGN, indices)
    if any(2 <= i <= 8 for i in indices):
        print("相机为展示用假设轨迹；未执行 WorldScore 原始符号动作，不是标定相机。")


def prepare(assets, index, output):
    data = build(index, assets)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / f"showcase-{index:02d}.json", data)
    print("展示输入:", index, cases()[index]["source"], cases()[index]["kind"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--assets", type=Path, required=True)
    check.add_argument("--array", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--assets", type=Path, required=True)
    prep.add_argument("--index", type=int, required=True)
    prep.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_check()
    if args.command == "verify":
        verify(args.assets, args.array)
    else:
        prepare(args.assets, args.index, args.output)


if __name__ == "__main__":
    main()
