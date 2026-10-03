"""Read both retained batches to check the diagnostic-only fix changed no fit."""
import numpy as np
from common import ROOT,write

def main():
    before=ROOT/'c_pressure_normal_attempt1/meshes';after=ROOT/'c_pressure_normal/meshes';rows=[]
    for p in sorted(before.glob('*/*/Official_Rigid_D_normal.npz')):
        q=after/p.relative_to(before);a=np.load(p);b=np.load(q)
        difference=float(np.linalg.norm(a['vertices_m']-b['vertices_m'],axis=1).max()*1000)
        assert difference==0 and np.array_equal(a['normal_scalar_m'],b['normal_scalar_m'])
        rows.append(dict(subject=p.parts[-3],seed=p.parts[-2],final_vertices_exact_equal=True,
            scalar_variables_exact_equal=True,max_vertex_difference_mm=difference))
    assert len(rows)==57
    write(ROOT/'c_pressure_normal/DIAGNOSTIC_FIX_RERUN_AGREEMENT.json',dict(status='PASS',
        repeated_successful_fits_checked=57,comparison='actual vertices and scalar variables; metadata diagnostic intentionally changed',rows=rows))
    print('RERUN_AGREEMENT_PASS',len(rows),flush=True)

if __name__=='__main__':main()
