"""Match the three finished packages to their manifests and actual Git blobs."""
import hashlib,json,subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[5]
HANDOFF=REPO/'docs/handoffs/real-scene-2026-10-04'
PACKAGES=['back-reference-extraction-v1','prone-reference-mesh-interface-v1','bounded-reference-correspondence-v1']

def main():
    results=[]
    for package in PACKAGES:
        root=HANDOFF/package;manifest=json.loads((root/'FILES_MANIFEST.json').read_text(encoding='utf-8-sig'))
        assert manifest['file_count']==len(manifest['rows'])
        rel=root.relative_to(REPO).as_posix()
        tree=subprocess.check_output(['git','ls-tree','-r','-z','HEAD','--',rel],cwd=REPO)
        blobs={}
        for entry in tree.split(b'\0'):
            if not entry:continue
            meta,path=entry.split(b'\t',1);blobs[path.decode('utf-8')]=meta.split()[2].decode()
        wanted=[r['path'] for r in manifest['rows']]+['FILES_MANIFEST.json']
        requests=[blobs[f'{rel}/{name}'] for name in wanted]
        data=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(requests)+'\n').encode(),cwd=REPO)
        cursor=0;identity=[]
        for name in wanted:
            end=data.index(b'\n',cursor);header=data[cursor:end].split();length=int(header[2]);cursor=end+1
            content=data[cursor:cursor+length];cursor+=length+1
            local=(root/name).read_bytes();assert content==local,(package,name,'GIT_WORKTREE_DIFFERENCE')
            digest=hashlib.sha256(local).hexdigest()
            if name!='FILES_MANIFEST.json':
                row=next(r for r in manifest['rows'] if r['path']==name)
                assert digest==row['sha256'] and len(local)==row['bytes'],(package,name,'MANIFEST_MISMATCH')
            identity.append(dict(path=name,sha256=digest,git_blob=blobs[f'{rel}/{name}']))
        results.append(dict(package=package,status='PASS',manifest_files=len(manifest['rows']),
            committed_files_verified=len(wanted),manifest_sha256=hashlib.sha256((root/'FILES_MANIFEST.json').read_bytes()).hexdigest(),
            all_listed_files_match_worktree_and_git=True))
    out=HANDOFF/'continuous-execution-summary-v1/DELIVERY_VERIFICATION.json'
    out.write_bytes((json.dumps(dict(status='PASS',reviewed_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip(),
        packages=results,total_files_verified=sum(r['committed_files_verified'] for r in results)),indent=2)+'\n').encode())
    print(out.read_text())

if __name__=='__main__':main()
