"""Bridge official public HuMMan URLs to server-only streaming downloads.

The AutoDL host can reach the official CDN but not huggingface.co. The local
controller obtains fresh signed redirects without downloading the archive body.
SSH password comes from AUTODL_SSH_PASSWORD, never a source/config file.
"""
import argparse
import json
import os
from pathlib import Path
import time
import paramiko
import requests


FILES = ['point_cameras.7z', 'smpl_params.7z', 'point_kinect_mask.7z',
         'point_kinect_depth_part_11.7z', 'point_kinect_color_part_02.7z']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--host', required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--root', default='/root/autodl-tmp/rgbd_sam3d')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    api = requests.get('https://huggingface.co/api/datasets/caizhongang/HuMMan', timeout=30)
    api.raise_for_status()
    revision = api.json()['sha']
    tree = requests.get(f'https://huggingface.co/api/datasets/caizhongang/HuMMan/tree/{revision}/humman_release_v1.0_point', timeout=30)
    tree.raise_for_status()
    indexed = {Path(x['path']).name: x for x in tree.json() if x['type']=='file'}
    total = sum(indexed[f]['size'] for f in FILES)
    # Budget is for this subset, not full release. Extraction is selective later.
    state = dict(status='RUNNING', source_revision=revision, archive_bytes=total,
                 files=FILES, receipts=[])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(args.host, port=args.port, username='root', password=os.environ['AUTODL_SSH_PASSWORD'], timeout=20)
    s = c.open_sftp()
    s.put(str(Path(__file__).with_name('download_one.py')), args.root+'/runs/download_one.py')
    for name in FILES:
        row = indexed[name]
        canonical = f'https://huggingface.co/datasets/caizhongang/HuMMan/resolve/{revision}/{row["path"]}'
        with requests.get(canonical, stream=True, timeout=30) as response:
            response.raise_for_status()
            signed_url = response.url
        target = args.root+'/datasets/raw/'+name
        job_path = args.root+'/runs/download_current.private.json'
        with s.file(job_path, 'w') as stream:
            stream.write(json.dumps(dict(url=signed_url,destination=target,size=row['size'],
                sha256=row['lfs']['oid'],revision=revision,source_path=row['path'])))
        s.chmod(job_path, 0o600)
        command = f'nohup /root/miniconda3/bin/python {args.root}/runs/download_one.py {job_path} > {target}.download.log 2>&1 < /dev/null & echo $!'
        _, stdout, stderr = c.exec_command(command)
        pid = int(stdout.read().decode().strip())
        state.update(current_file=name, current_pid=pid)
        args.out.write_text(json.dumps(state, indent=2))
        print(json.dumps({'file':name,'pid':pid,'expected_bytes':row['size']}), flush=True)
        while True:
            try:
                with s.file(target+'.receipt.json') as stream:
                    receipt=json.loads(stream.read())
                break
            except FileNotFoundError:
                _, o, e = c.exec_command(f'kill -0 {pid} 2>/dev/null')
                if o.channel.recv_exit_status()!=0:
                    raise RuntimeError(f'Download stopped: {name}; inspect {target}.download.log')
                time.sleep(10)
        state['receipts'].append(receipt)
        args.out.write_text(json.dumps(state, indent=2))
        print(json.dumps(receipt), flush=True)
    state['status']='COMPLETE_VERIFIED'
    args.out.write_text(json.dumps(state, indent=2))
    s.close();c.close()


if __name__ == '__main__':
    main()
