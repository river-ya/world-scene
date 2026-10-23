"""Only clean abandoned job temp directories; dry-run by default."""
import argparse
import getpass
from pathlib import Path
import re
import shutil
import subprocess


def candidates(root, active):
    root=Path(root)
    if not root.exists():return []
    result=[]
    for p in root.iterdir():
        m=re.fullmatch(r'job-([0-9]+)\.[A-Za-z0-9]+',p.name)
        if m and p.is_dir() and not p.is_symlink() and m[1] not in active:result.append(p)
    return sorted(result)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    # Fail closed if scheduler cannot be queried. %i identifies array elements too.
    user=getpass.getuser()
    output=subprocess.check_output(['squeue','--user',user,'--noheader','--format=%i'],text=True)
    active=set()
    for line in output.splitlines():
        value=line.strip();active.add(value);active.add(value.split('_')[0])
    # Array job temp dirs use SLURM_JOB_ID; query individual job IDs in JSON-free format.
    job_output=subprocess.check_output(['squeue','--user',user,'--noheader','--array','--format=%F %i'],text=True)
    for line in job_output.splitlines():active.update(line.split())
    paths=candidates(a.assets.resolve()/'tmp',active)
    if a.apply and active:
        raise RuntimeError('当前用户仍有排队/运行作业；为避免数组内部 job ID 歧义，本工具此时不执行删除。')
    for path in paths:
        print('删除' if a.apply else '候选（未删除）',path)
        if a.apply:shutil.rmtree(path)
    print('不清理权重、数据、断点下载、实验结果或历史版本。')


if __name__=='__main__':main()
