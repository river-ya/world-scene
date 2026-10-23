"""Pinned, resumable HF downloads without pip; never downloads gated DL3DV."""
from __future__ import annotations
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.parse
import urllib.request
from common import ROOT, lock, now, sha256, write_json


def selected(group):
    return [a for a in lock()['assets'] if group == 'all' or a['group'] == group]


def repository_dir(root, repo):
    prefix = 'models' if repo['kind'] == 'model' else 'datasets'
    return Path(root) / 'hf/hub' / (prefix + '--' + repo['repo'].replace('/', '--'))


def blob_path(root, repo, entry):
    return repository_dir(root, repo) / 'blobs' / entry['digest']


def file_digest(path, entry):
    h = hashlib.sha256() if entry['algorithm'] == 'sha256' else hashlib.sha1()
    if entry['algorithm'] == 'git-sha1':
        h.update(('blob ' + str(entry['size']) + '\0').encode())
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def valid(path, entry):
    return path.is_file() and path.stat().st_size == entry['size'] and file_digest(path, entry) == entry['digest']


def download_file(url, dest, entry, timeout=60):
    """Only publish a file after its size and upstream digest match."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if valid(dest, entry):
            return
        raise RuntimeError('已有文件校验失败，请检查后移走损坏文件: ' + str(dest))
    partial = dest.with_name(dest.name + '.part')
    for attempt in range(4):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > entry['size']:
            raise RuntimeError('断点文件超出预期大小: ' + str(partial))
        if offset == entry['size']:
            break
        headers = {'User-Agent': 'world-scene-repro/0.1.0', 'Accept-Encoding': 'identity'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        try:
            # Fresh redirect avoids stale signed object-storage URLs on retry.
            sep = '&' if '?' in url else '?'
            req = urllib.request.Request(url + sep + 'download=true&repro_attempt=' + str(time.time_ns()), headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = response.status
                if status == 206:
                    content_range = response.headers.get('Content-Range', '')
                    if not content_range.startswith(f'bytes {offset}-'):
                        raise RuntimeError('服务器返回错误的断点范围')
                    mode = 'ab'
                elif status == 200:
                    mode = 'wb'  # server ignored Range: restart, never concatenate
                else:
                    raise RuntimeError(f'不支持的 HTTP 状态: {status}')
                with partial.open(mode) as f:
                    while True:
                        chunk = response.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            if partial.stat().st_size == entry['size']:
                break
        except (OSError, TimeoutError) as exc:
            if attempt == 3:
                raise RuntimeError(f'下载失败，保留断点: {dest.name}; {type(exc).__name__}') from exc
        time.sleep(min(2 ** attempt, 8))
    if not valid(partial, entry):
        raise RuntimeError('下载未完成或摘要不匹配，未发布文件: ' + str(partial))
    os.replace(partial, dest)


def link_snapshot(root, repo):
    directory = repository_dir(root, repo)
    for entry in repo['files']:
        blob = blob_path(root, repo, entry)
        target = directory / 'snapshots' / repo['revision'] / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        relative = os.path.relpath(blob, target.parent)
        if target.is_symlink():
            if os.readlink(target) != relative:
                raise RuntimeError('快照链接不一致: ' + str(target))
        elif target.exists():
            raise RuntimeError('快照位置已有普通文件: ' + str(target))
        else:
            target.symlink_to(relative)
    refs = directory / 'refs'
    refs.mkdir(exist_ok=True)
    (refs/'main').write_text(repo['revision'])


def receipt_path(root, group):
    return Path(root) / f'verified-{group}.json'


def verify(root, group, quick=False):
    previous = None
    if quick:
        previous = json.loads(receipt_path(root, group).read_text())
        if previous['lock_sha256'] != sha256(ROOT/'configs/versions.lock.json'):
            raise RuntimeError('资产锁定文件变化，需要重新完整校验')
    records = {}
    for repo in selected(group):
        directory = repository_dir(root, repo)
        if (directory/'refs/main').read_text().strip() != repo['revision']:
            raise RuntimeError('缓存 main 没有指向固定 revision')
        for e in repo['files']:
            p = blob_path(root, repo, e)
            target = directory/'snapshots'/repo['revision']/e['path']
            if target.resolve() != p.resolve() or not p.is_file() or p.stat().st_size != e['size']:
                raise RuntimeError('文件/快照不完整: ' + e['path'])
            key = str(p.relative_to(root))
            stat = {'size': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns, 'digest': e['digest']}
            if quick:
                if previous['files'].get(key) != stat:
                    raise RuntimeError('资产在校验后变化，需重新完整校验: ' + key)
            elif file_digest(p, e) != e['digest']:
                raise RuntimeError('文件摘要不符: ' + key)
            records[key] = stat
    if not quick:
        write_json(receipt_path(root, group), {'verified_at': now(), 'lock_sha256': sha256(ROOT/'configs/versions.lock.json'), 'files': records})
    print(f'资产校验通过: {group}, {len(records)} files, quick={quick}', flush=True)


def download(root, group, workers):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root/'.download.lock').open('w') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        repos = selected(group)
        work = [(r, e) for r in repos for e in r['files']]
        work.sort(key=lambda re: re[1]['size'])
        needed = sum(max(0, e['size'] - (blob_path(root,r,e).stat().st_size if blob_path(root,r,e).exists() else 0)) for r,e in work)
        if shutil.disk_usage(root).free < needed + 5 * 1024**3:
            raise RuntimeError('磁盘空间不足；需要下载大小外再留 5GiB 余量')
        state = root/'download-status.json'
        write_json(state, {'status':'running','started_at':now(),'group':group,'expected_files':len(work)})
        def one(item):
            repo, entry = item
            prefix = 'datasets/' if repo['kind']=='dataset' else ''
            url = 'https://huggingface.co/' + prefix + repo['repo'] + '/resolve/' + repo['revision'] + '/' + urllib.parse.quote(entry['path'])
            print('下载/校验:', repo['repo'], entry['path'], entry['size'], flush=True)
            download_file(url, blob_path(root,repo,entry), entry)
            print('完成:', repo['repo'], entry['path'], flush=True)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures=[pool.submit(one,item) for item in work]
                for f in concurrent.futures.as_completed(futures):f.result()
            for repo in repos:link_snapshot(root,repo)
            for subgroup in sorted({r['group'] for r in repos}):verify(root,subgroup)
            write_json(state, {'status':'complete','finished_at':now(),'group':group,'files':len(work)})
        except BaseException as exc:
            write_json(state, {'status':'incomplete','updated_at':now(),'group':group,'error_type':type(exc).__name__})
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['download','verify','status'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--group',choices=['models','worldscore','all'],default='models')
    p.add_argument('--workers',type=int,default=3)
    p.add_argument('--quick',action='store_true')
    a=p.parse_args();a.root=a.root.resolve()
    if not 1 <= a.workers <= 4:p.error('workers must be 1..4')
    if a.command=='download':download(a.root,a.group,a.workers)
    elif a.command=='verify':
        for g in ['models','worldscore'] if a.group=='all' else [a.group]:verify(a.root,g,a.quick)
    else:
        for repo in selected(a.group):
            files=repo['files'];complete=sum(blob_path(a.root,repo,e).exists() for e in files)
            partial_bytes=sum(p.stat().st_size for e in files if (p:=blob_path(a.root,repo,e).with_name(e['digest']+'.part')).exists())
            print(repo['repo'],f'{complete}/{len(files)} complete',f'{partial_bytes/1e9:.3f} GB partial')


if __name__=='__main__':main()
