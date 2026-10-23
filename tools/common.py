"""Standard-library helpers for immutable experiment provenance."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def lock():
    return json.loads((ROOT / 'configs/versions.lock.json').read_text())


def source_check():
    spec = lock()['upstream']
    root = ROOT / 'upstream/FlashWorld'
    for name, expected in spec['files'].items():
        p = root / name
        if not p.is_file() or sha256(p) != expected:
            raise RuntimeError('上游文件缺失或偏离锁定版本: ' + name)


def project_identity():
    release = ROOT / 'RELEASE.json'
    if release.exists():
        data = json.loads(release.read_text())
        for name, expected in data['files'].items():
            if not (ROOT / name).is_file() or sha256(ROOT / name) != expected:
                raise RuntimeError('发布包文件校验失败: ' + name)
        return {k: data[k] for k in ['version', 'commit', 'upstream_commit']}
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True)
    if dirty:
        raise RuntimeError('工作区有未提交改动；先测试并提交，再启动正式实验。')
    return {'version': (ROOT/'VERSION').read_text().strip(), 'commit': commit,
            'upstream_commit': lock()['upstream']['commit']}


def safe_name(value):
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', value):
        raise ValueError('名称只允许字母、数字、下划线、点和短横线，且不得以点开头')
    return value
