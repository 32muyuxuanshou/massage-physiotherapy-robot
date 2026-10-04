"""Real XYZ rasterization and block removal; estimator input excludes labels."""
import csv,hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

QUALIFICATION=Path('/raid5/xuhd/datasets/real_back_reference_qualification_v1_20261004')

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def features(points,xs,ys):
    x,y=np.meshgrid(xs,ys);q=np.column_stack([x.ravel(),y.ravel()]);d,index=cKDTree(points[:,:2]).query(q)
    valid=(d.reshape(x.shape)<=.003);z=points[index,2].reshape(x.shape)
    median=np.median(z[valid]);depth=np.where(valid,(z-median)/.05,0.)
    tensor=np.stack([depth,valid.astype(float),(x-(xs[0]+xs[-1])/2)/.25,(y-(ys[0]+ys[-1])/2)/.25]).astype('float32')
    return tensor,valid


def drop_blocks(points,seed):
    blocks=np.floor(points/.06).astype(np.int64);unique,inverse=np.unique(blocks,axis=0,return_inverse=True)
    rng=np.random.default_rng(seed);count=int(round(.2*len(unique)));removed=rng.choice(len(unique),count,replace=False)
    keep=~np.isin(inverse,removed)
    return points[keep],np.flatnonzero(keep)


def prepare(root):
    sys.path.insert(0,str(QUALIFICATION/'code'))
    from audit_references import SOURCE,PREVIOUS,READER,load_reader
    packets=read(QUALIFICATION/'REFERENCE_PACKET_MANIFEST.json');scans={r['scan_id']:r for r in csv.DictReader((PREVIOUS/'SCAN_REFERENCE_BINDING.csv').open())}
    packets.sort(key=lambda r:r['scan_sha256']);reader=load_reader();records=[]
    geometry=Path('/raid5/xuhd/datasets/back_reference_extraction_v1_20261004')
    files=[root/'PROTOCOL.md',*(root/'code').glob('*.py'),QUALIFICATION/'code/audit_references.py',READER,
           QUALIFICATION/'REFERENCE_PACKET_MANIFEST.json',PREVIOUS/'SCAN_REFERENCE_BINDING.csv',
           geometry/'code/extract_geometry.py',geometry/'CONFIG.json']
    (root/'dataset').mkdir(exist_ok=True)
    groups=set()
    for i,p in enumerate(packets):
        source=SOURCE/scans[p['scan_id']]['path'];group=str(source.parent);assert group not in groups;groups.add(group)
        points,columns=reader.read_ply(source);assert columns==['x','y','z'];assert sha(source)==p['scan_sha256']
        annotation=Path(p['path']);assert sha(annotation)==p['sha256'];line=np.load(annotation)['line_m']
        lo,hi=np.quantile(points[:,1],[.05,.95]);xs=np.linspace(points[:,0].min(),points[:,0].max(),128);ys=np.linspace(lo,hi,128)
        tensor,valid=features(points,xs,ys)
        # Explicitly merge duplicate longitudinal labels before training interpolation.
        unique_y=np.unique(line[:,1]);target_x=np.asarray([np.mean(line[line[:,1]==y,0]) for y in unique_y])
        target=np.interp(ys,unique_y,target_x);label_valid=(ys>=unique_y.min())&(ys<=unique_y.max())
        path=root/'dataset'/(p['candidate_id']+'.npz')
        np.savez_compressed(path,points_m=points,reference_line_m=line,xs_m=xs,ys_m=ys,features=tensor,
            target_x_m=target,target_row_valid=label_valid)
        role='train' if i<20 else 'dev' if i<24 else 'consumed_evaluation'
        records.append(dict(candidate_id=p['candidate_id'],scan_id=p['scan_id'],source_group_proxy='group_'+hashlib.sha256(group.encode()).hexdigest()[:12],
            role=role,path=str(path),sha256=sha(path),scan_sha256=p['scan_sha256'],annotation_sha256=p['sha256'],points=len(points),
            label_rows=int(label_valid.sum()),clinical_acupoint_labels=False))
        files.extend([source,annotation,path])
    write(root/'DATA_MANIFEST.json',records)
    write(root/'CONFIG.json',dict(network='4ch LineNet U-Net16/32/64',epochs=120,batch=4,lr=.001,seeds=[0,1,2],
        strategies=['NO_BLOCK_AUG','BLOCK_AUG'],grid=[128,128],block_m=.06,removed_block_fraction=.2,
        group_proxy_independent_patients_verified=False,roles={'train':20,'dev':4,'consumed_evaluation':6},
        gaussian_width_m=.003,coordinate_huber_scale_m=.01,coordinate_loss_weight=.1,continuity_weight=.01,
        checkpoint_selection='4 dev scans, mean lateral error across 3 fixed20percent block removals',
        data_preparation_caches_all_annotation_roles=True,evaluation_labels_opened_by_training=False))
    files.extend([root/'CONFIG.json',root/'DATA_MANIFEST.json'])
    write(root/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in files])
    print('DATASET_READY',len(records),'role_counts',[(r,len([p for p in records if p['role']==r])) for r in ['train','dev','consumed_evaluation']],flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();prepare(args.root)
