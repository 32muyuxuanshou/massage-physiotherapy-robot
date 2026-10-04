import json
from pathlib import Path
import numpy as np
from reference_frame import reference_frame,local_coordinates,world_coordinates

m=np.array([[0,0,0],[0,.4,0],[.1,.4,0],[-.1,.4,0]])
f=reference_frame(m)
np.testing.assert_allclose(f['basis'],np.eye(3),atol=1e-14)
points=np.array([[.03,.2,.01],[-.04,.3,.02]])
np.testing.assert_allclose(world_coordinates(local_coordinates(points,f),f),points,atol=1e-14)
angle=.7;R=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
t=np.array([.2,-.3,1.2]);g=reference_frame(m@R.T+t)
np.testing.assert_allclose(local_coordinates(points@R.T+t,g),local_coordinates(points,f),atol=1e-14)
np.testing.assert_allclose(g['basis'].T@g['basis'],np.eye(3),atol=1e-14)
assert abs(np.linalg.det(g['basis'])-1)<1e-14
assert reference_frame(np.zeros((4,3))) is None
out=Path(__file__).resolve().parents[1]/'ANALYTIC_FRAME_CHECK.json'
out.write_bytes((json.dumps(dict(status='PASS',checks=['known orthonormal frame','world/local reconstruction','rotation/translation equivariance','right-handed basis','known degenerate frame']),indent=2)+'\n').encode())
print('FRAME_CHECK_PASS')
