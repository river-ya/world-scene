import base64
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import showcase


class ShowcaseTests(unittest.TestCase):
    def test_array_selection_and_duplicates(self):
        self.assertEqual(showcase.task_indices("2-9%1"), list(range(2, 10)))
        self.assertEqual(showcase.task_indices("3,8-9%2"), [3, 8, 9])
        for value in ("", "2-10%1", "9-2%1", "2,2%1", "2-4,4%1",
                      "2-9%0", "2-9%5", "2;echo x", "-1%1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                showcase.task_indices(value)

    def test_dimensions_and_inverse_crop_intrinsics(self):
        for width, height in ((1080, 721), (640, 480), (1001, 1400)):
            png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", width, height)
            self.assertEqual(showcase.image_size(png), (width, height))
            payload = bytes([8]) + struct.pack(">HH", height, width) + b"\x03"
            jpeg = b"\xff\xd8\xff\xc0" + struct.pack(">H", len(payload) + 2) + payload
            self.assertEqual(showcase.image_size(jpeg), (width, height))
            original = showcase.official(3)["cameras"]
            before = copy.deepcopy(original)
            cameras, crop = showcase.transfer_intrinsics(original, (width, height))
            scale = max(480 / height, 704 / width)
            left = (width - int(704 / scale)) // 2
            top = (height - int(480 / scale)) // 2
            for old, new in zip(original, cameras):
                self.assertAlmostEqual(new["fx"] * scale, old["fx"])
                self.assertAlmostEqual(new["fy"] * scale, old["fy"])
                self.assertAlmostEqual((new["cx"] - left) * scale, old["cx"])
                self.assertAlmostEqual((new["cy"] - top) * scale, old["cy"])
                self.assertEqual(new["position"], old["position"])
            self.assertEqual(original, before)
            self.assertEqual(crop["crop_xywh"][:2], [left, top])

    def test_development_hash_split_and_provenance(self):
        raw = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 640, 480)
        row = {
            "id": "ws-indoor-000", "split": "dev", "local_image": "images/000.png",
            "image_sha256": hashlib.sha256(raw).hexdigest(),
            "source_scene": "static/example.png", "text": "An indoor room.",
            "original": {"camera_path": ["orbit_right"]},
        }
        frozen = {"revision": "fixed", "samples": [row]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(showcase, "subset", return_value=frozen):
            root = Path(tmp)
            path = root / "data/worldscore-indoor-v1/images/000.png"
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            data = showcase.build(2, root)
            self.assertEqual(base64.b64decode(data["image_prompt"].split(",")[1]), raw)
            self.assertEqual(data["text_prompt"], row["text"])
            self.assertFalse(data["_showcase"]["camera_calibrated"])
            self.assertFalse(data["_showcase"]["source_camera_commands_executed"])
            output = root / "prepared"
            showcase.prepare(root, 2, output)
            self.assertEqual(json.loads((output / "showcase-02.json").read_text()), data)
            with self.assertRaises(FileExistsError):
                showcase.prepare(root, 2, output)
            row["split"] = "test"
            with self.assertRaises(ValueError):
                showcase.build(2, root)
            row["split"] = "dev"
            path.write_bytes(raw + b"changed")
            with self.assertRaises(ValueError):
                showcase.build(2, root)

    def test_variants_change_only_intended_conditions(self):
        room, studio = showcase.official(3), showcase.official(5)
        for index, expected in ((0, room), (1, studio)):
            data = showcase.build(index, Path("/unused"))
            data.pop("_showcase")
            self.assertEqual(data, expected)
        data = showcase.build(8, Path("/unused"))
        self.assertEqual(data["image_prompt"], room["image_prompt"])
        self.assertEqual(data["text_prompt"], room["text_prompt"])
        self.assertEqual(data["resolution"], room["resolution"])
        self.assertEqual(data["image_index"], studio["image_index"])
        self.assertNotEqual(data["cameras"], room["cameras"])
        for camera, old in zip(data["cameras"], room["cameras"]):
            for key in ("fx", "fy", "cx", "cy"):
                self.assertEqual(camera[key], old[key])
        data = showcase.build(9, Path("/unused"))
        data.pop("_showcase")
        self.assertNotEqual(data["text_prompt"], studio["text_prompt"])
        data["text_prompt"] = studio["text_prompt"]
        self.assertEqual(data, studio)
        self.assertEqual(len(showcase.cases()), 10)
        self.assertEqual(len({c["source"] for c in showcase.cases()}), 8)


if __name__ == "__main__":
    unittest.main()
