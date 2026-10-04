"""Emit geometry targets from an existing binding cache without refitting."""
import argparse,json
from pathlib import Path
import numpy as np


def main(cache,out):
    z=np.load(cache)
    points=[]
    for i in range(len(z['xyz_m'])):
        points.append(dict(id=f'ENG_CURVE_{i+1:02d}',xyz_m=z['xyz_m'][i].tolist(),face_id=int(z['face_id'][i]),
            barycentric=z['barycentric'][i].tolist(),normal=z['normals'][i].tolist(),
            input_query_m=z['query_m'][i].tolist(),surface_projection_distance_m=float(z['projection_distance_m'][i]),
            longitudinal_fraction=float(z['probe_fraction'][i]),medical_label=None))
    result=dict(units='metres',coordinate_frame='historical_approximate_camera',
        purpose='offline engineering reference-to-Mesh interface',clinical_target_validated=False,
        robot_transform_validated=False,mesh_sha256=str(z['mesh_sha256']),points=points)
    out.write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'));print('EXPORTED',len(points),out)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();main(args.cache,args.out)
