"""Read actual author remeshing/vts assets and preserve a private template preview."""
import json,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')


def load_off(path):
    with path.open() as f:
        assert f.readline().strip()=='OFF'
        n,m,_=map(int,f.readline().split())
        v=np.array([list(map(float,f.readline().split())) for _ in range(n)])
        faces=np.array([list(map(int,f.readline().split()))[1:] for _ in range(m)])
    return v,faces


def main():
    rows=[]
    for dataset in ['faust','scape']:
        for p in sorted((ROOT/dataset/'off_2').glob('*.off')):
            v,f=load_off(p);vp=ROOT/dataset/'corres'/(p.stem+'.vts');ids=np.loadtxt(vp,dtype=int)-1
            assert ids.min()>=0 and ids.max()<len(v)
            rows.append(dict(dataset=dataset,name=p.stem,vertices=len(v),faces=len(f),vts_count=len(ids),
                unique_vts_vertices=len(np.unique(ids)),bbox_native=[v.min(0).tolist(),v.max(0).tolist()],
                mesh_path=str(p),mesh_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                vts_path=str(vp),vts_sha256=hashlib.sha256(vp.read_bytes()).hexdigest()))
    report=dict(status='PASS',meshes=rows,vts_semantics='1-based vertex index per shared reference sample; NOT a vertex-ID map to MHR',
                source_loader='https://raw.githubusercontent.com/nmwsharp/diffusion-net/master/experiments/functional_correspondence/faust_scape_dataset.py',
                unit='native scan coordinates, meter-scale but no original precision claimed',
                subject_identity_verified=False,clinical_labels=False)
    (ROOT/'DATA_INVENTORY.json').write_text(json.dumps(report,indent=2)+'\n')
    v,_=load_off(ROOT/'faust/off_2/tr_reg_000.off')
    fig,axes=plt.subplots(1,3,figsize=(12,7))
    for ax,(x,y,name) in zip(axes,[(0,1,'XY'),(0,2,'XZ'),(2,1,'ZY')]):
        ax.scatter(v[:,x],v[:,y],s=2,c=v[:,2],cmap='coolwarm');ax.set_aspect('equal');ax.set_title('Template000 '+name)
    fig.tight_layout();fig.savefig(ROOT/'PRIVATE_TEMPLATE_PREVIEW.png',dpi=100);plt.close(fig)
    print('INVENTORY_PASS',len(rows),{d:sum(r['dataset']==d for r in rows) for d in ['faust','scape']},flush=True)


if __name__=='__main__':main()
