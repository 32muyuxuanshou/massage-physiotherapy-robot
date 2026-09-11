import json, re
from pathlib import Path
import numpy as np

def sequence_date(sequence):
    m=re.match(r'^(Date\d{2})_',Path(sequence).name)
    if not m: raise ValueError(f'Cannot parse DateXX from {sequence}')
    return m.group(1)

def read_camera(calib_root, sequence, kid):
    """Load the date-specific BEHAVE K0..K3 intrinsics and local-to-world pose."""
    date=sequence_date(sequence); root=Path(calib_root)
    ip=root/'intrinsics'/str(kid)/'calibration.json'
    tp=root/'intrinsics'/str(kid)/'pointcloud_table.npy'
    ep=root/date/'config'/str(kid)/'config.json'
    c=json.loads(ip.read_text())['color']; e=json.loads(ep.read_text())
    K=np.array([[c['fx'],0,c['cx']],[0,c['fy'],c['cy']],[0,0,1.]],float)
    return {'date':date,'kid':kid,'K':K,'dist':np.asarray(c['opencv'][4:],float),'pointcloud_table':np.load(tp),'R_local_to_world':np.asarray(e['rotation'],float).reshape(3,3),'t_local_to_world_m':np.asarray(e['translation'],float),'provenance':[str(ip),str(tp),str(ep)]}

def local_to_world(points, camera):
    return np.asarray(points)@camera['R_local_to_world'].T+camera['t_local_to_world_m']

def world_to_local(points, camera):
    return (np.asarray(points)-camera['t_local_to_world_m'])@camera['R_local_to_world']

def transform_between(points, source, target):
    if source['date']!=target['date']: raise ValueError('Cross-date camera transform is invalid')
    return world_to_local(local_to_world(points,source),target)

def geometry_qa(camera):
    pts=np.array([[0.,0.,1.],[.2,-.1,2.],[-.3,.25,3.]])
    back=world_to_local(local_to_world(pts,camera),camera)
    return {'date':camera['date'],'kid':camera['kid'],'roundtrip_max_m':float(np.abs(back-pts).max()),'positive_depth':bool(np.all(pts[:,2]>0)),'pass':bool(np.abs(back-pts).max()<1e-9)}
