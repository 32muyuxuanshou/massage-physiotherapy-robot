"""Check an observed-region binding from the retained planar cache; no refit."""
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import ROOT,BASE,write,sha
sys.path.insert(0,str(BASE/'delivery/code'))
from surface_metrics import point_to_triangle_distances
from metrics_v2 import ray_depth_residual

def main():
    z=np.load(ROOT/'planar_witness.npz');F=z['faces'];V=z['reference_vertices_m'];obs=z['observed_points_m']
    center=V[F].mean(1);face_id=int(np.argmin(np.linalg.norm(center[:,:2],axis=1)))
    face=F[face_id];b=np.full(3,1/3);reference=(V[face]*b[:,None]).sum(0);rows=[]
    lo=obs[:,:2].min(0);hi=obs[:,:2].max(0)
    assert np.all(reference[:2]>lo) and np.all(reference[:2]<hi)
    for method,name in [('INITIAL','initial_vertices_m'),('D_VECTOR','vector_vertices_m'),('D_NORMAL','normal_vertices_m')]:
        final=z[name];p=(final[face]*b[:,None]).sum(0)
        assert np.all(p[:2]>lo) and np.all(p[:2]<hi)
        d=point_to_triangle_distances(obs[::50],final,F);ray,hit=ray_depth_residual(obs[::50],final,F)
        error=float(np.linalg.norm(p-reference)*1000)
        assert d.max()<1e-10 and hit.all() and np.abs(ray).max()<1e-10 and abs(error-20)<1e-8
        rows.append(dict(method=method,known_probe_xyz_m=reference.tolist(),predicted_probe_xyz_m=p.tolist(),
            both_probe_projections_inside_observed_patch=True,binding_error_mm=error,
            surface_max_mm=float(d.max()*1000),ray_max_mm=float(np.abs(ray).max()*1000)))
    write(ROOT/'PLANAR_OBSERVED_BINDING_CHECK.json',dict(status='PASS',script_sha256=sha(__file__),
        cached_fixture_sha256=sha(ROOT/'planar_witness.npz'),face_id=face_id,vertex_ids=face.tolist(),barycentric=b.tolist(),
        original_probe_inside_observed_patch=bool(np.all(z['target_probe_m'][:2]>lo) and np.all(z['target_probe_m'][:2]<hi)),
        rows=rows,refits=0,formal_human_case_changes=0,
        explanation='Original retained witness bound a point outside the observed patch. This follow-up uses the same frozen fitted plane and verifies a binding inside the observed region.'))
    p=np.asarray(rows[0]['predicted_probe_xyz_m']);fig,ax=plt.subplots(figsize=(7,5))
    ax.scatter(obs[:,0]*1000,obs[:,1]*1000,s=1,c='lightgray',label='observed planar patch: same Z')
    ax.scatter(reference[0]*1000,reference[1]*1000,c='blue',s=70,label='known binding inside observed patch')
    ax.scatter(p[0]*1000,p[1]*1000,c='red',s=70,label='shifted same binding')
    ax.annotate('',xy=p[:2]*1000,xytext=reference[:2]*1000,arrowprops=dict(arrowstyle='->',color='black'))
    ax.set_aspect('equal');ax.set_xlabel('X (mm)');ax.set_ylabel('Y (mm)');ax.set_title('Observed region: surface/depth ~0; binding error 20 mm');ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(ROOT/'figures/PLANAR_OBSERVED_BINDING_WITNESS.png',dpi=150);plt.close(fig)
    print('OBSERVED_PLANAR_BINDING_CHECK_PASS',rows,flush=True)

if __name__=='__main__':main()
