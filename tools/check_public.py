"""Offline source-package checks; does not read Git history or contact a service."""
from pathlib import Path
import re
from common import ROOT, sha256, source_check


def check(root=ROOT):
    problems = []
    files = []
    forbidden_suffixes = {'.ckpt', '.safetensors', '.pth', '.pt', '.ply', '.spz', '.mp4', '.bundle'}
    secrets = [re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
               re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
               re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
               re.compile(rb'hf_[A-Za-z0-9]{30,}')]
    personal_path = re.compile(rb'/data-nfs/gpu[0-9]+/[A-Za-z0-9_-]+')
    for p in sorted(Path(root).rglob('*')):
        rel = p.relative_to(root)
        if '.git' in rel.parts:
            continue
        if p.is_symlink():
            problems.append(f'external link: {rel}')
            continue
        if not p.is_file():
            continue
        files.append(p)
        if p.name in {'local.env', 'lucid.env', '.env', '.DS_Store'} or p.suffix in forbidden_suffixes or '__pycache__' in rel.parts:
            problems.append(f'local/runtime artifact: {rel}')
        if p.stat().st_size > 10*1024*1024:
            problems.append(f'file exceeds source-package budget (10 MiB): {rel}')
        data = p.read_bytes()
        if any(pattern.search(data) for pattern in secrets):
            problems.append(f'possible credential: {rel}')
        if personal_path.search(data):
            problems.append(f'personal cluster path: {rel}')
    if problems:
        raise RuntimeError('\n'.join(problems))
    return files


def main():
    import json
    source_check()
    from lucid_assets import source_check as lucid_source_check
    lucid_source_check()
    meta = json.loads((ROOT/'configs/publication.json').read_text())['additional_license']
    if sha256(ROOT/meta['path']) != meta['sha256']:
        raise RuntimeError('additional upstream license checksum mismatch')
    files = check()
    print('PUBLIC_SOURCE_CHECK_OK', len(files), 'files', sum(p.stat().st_size for p in files), 'bytes')
    print('Pattern checks are not a guarantee that every possible secret was detected.')


if __name__ == '__main__':
    main()
