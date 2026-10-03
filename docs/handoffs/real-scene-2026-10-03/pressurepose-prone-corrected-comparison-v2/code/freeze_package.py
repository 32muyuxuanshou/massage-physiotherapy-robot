"""Freeze every reviewable delivery file; call only after writing the handoff."""
from pathlib import Path
from data_v2 import sha,save_json


def main():
    root=Path(__file__).resolve().parents[1]
    files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name=='FILES_MANIFEST.json':continue
        files.append(dict(path=str(p.relative_to(root)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)))
    save_json(root/'FILES_MANIFEST.json',dict(status='REVIEWABLE_LOCAL_PREPARATION_FORMAL_PENDING',files=files))
    print(len(files),'files frozen')


if __name__=='__main__':main()
