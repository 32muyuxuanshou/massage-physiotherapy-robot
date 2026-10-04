"""Local raster/block-removal positive path, independent of GPU/server paths."""
import json
from pathlib import Path
import numpy as np
from data_line import features,drop_blocks

def main():
    x,y=np.meshgrid(np.linspace(-.15,.15,151),np.linspace(-.2,.2,201))
    points=np.column_stack([x.ravel(),y.ravel(),(1+.1*x*x+.01*y).ravel()])
    xs=np.linspace(-.15,.15,128);ys=np.linspace(-.2,.2,128)
    tensor,valid=features(points,xs,ys)
    assert tensor.shape==(4,128,128) and valid.all() and np.isfinite(tensor).all()
    visible,indices=drop_blocks(points,0);again,index_again=drop_blocks(points,0)
    assert np.array_equal(visible,points[indices]) and np.array_equal(indices,index_again)
    assert 0<len(visible)<len(points)
    blocked,mask=features(visible,xs,ys)
    assert not mask.all() and np.isfinite(blocked).all()
    assert np.all(blocked[0,~mask]==0) and np.array_equal(blocked[1].astype(bool),mask)
    result=dict(status='PASS',geometry='analytic XY surface; pipeline sanity only',points=len(points),
        visible_points=len(visible),grid_shape=list(tensor.shape),full_valid_fraction=float(valid.mean()),
        missing_valid_fraction=float(mask.mean()),model_forward_backward_verified=False,real_training_executed=False)
    out=Path(__file__).resolve().parents[1]/'LOCAL_DATA_SANITY.json'
    out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result))

if __name__=='__main__':main()
