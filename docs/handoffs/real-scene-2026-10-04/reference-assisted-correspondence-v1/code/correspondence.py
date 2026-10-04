"""Reference-assisted point correspondence on a fixed surface, no Mesh fitting."""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra
from trimesh.triangles import closest_point

def binding(V,F,records):
    triangles=V[F[[r['face_id'] for r in records]]];b=np.asarray([r['barycentric'] for r in records])
    return np.sum(triangles*b[:,:,None],axis=1)

def graph_distances(V,F,records,input_indices):
    P=binding(V,F,records);n=len(V)
    E=np.unique(np.sort(np.vstack([F[:,[0,1]],F[:,[1,2]],F[:,[2,0]]]),axis=1),axis=0)
    i=E[:,0];j=E[:,1];length=np.linalg.norm(V[i]-V[j],axis=1)
    vertices=F[[r['face_id'] for r in records]]
    ii=np.repeat(n+np.arange(len(P)),3);jj=vertices.ravel()
    d=np.linalg.norm(P[:,None,:]-V[vertices],axis=2).ravel()
    i=np.r_[i,ii];j=np.r_[j,jj];length=np.r_[length,d]
    graph=sp.coo_matrix((np.r_[length,length],(np.r_[i,j],np.r_[j,i])),shape=(n+len(P),n+len(P))).tocsr()
    distances=dijkstra(graph,directed=False,indices=n+np.asarray(input_indices))[:,n:]
    assert np.isfinite(distances).all()
    return P,distances

def rbf_offsets(distances,input_indices,offsets,ridge=1e-6):
    pair=distances[:,input_indices]
    width=float(np.median(pair[np.triu_indices(len(input_indices),1)]));assert width>0
    G=np.exp(-.5*(pair/width)**2);A=np.block([[G+ridge*np.eye(len(G)),np.ones((len(G),1))],[np.ones((1,len(G))),np.zeros((1,1))]])
    rhs=np.vstack([offsets,np.zeros((1,3))]);coefficient=np.linalg.solve(A,rhs)
    prediction=np.exp(-.5*(distances.T/width)**2)@coefficient[:-1]+coefficient[-1]
    return prediction,dict(width_m=width,ridge=ridge,system_condition_number=float(np.linalg.cond(A)),coefficient=coefficient.tolist())

def surface_project(points,V,F,face_ids):
    ids=np.asarray(face_ids,int);tri=V[F[ids]];xyz=[];faces=[];bary=[];normals=[]
    for p in points:
        projected=closest_point(tri,np.repeat(p[None],len(tri),axis=0))
        assert np.isfinite(projected).all()
        k=int(np.argmin(np.sum((projected-p)**2,axis=1)));t=tri[k]
        uv=np.linalg.lstsq(np.column_stack([t[1]-t[0],t[2]-t[0]]),projected[k]-t[0],rcond=None)[0]
        b=np.clip([1-uv.sum(),uv[0],uv[1]],0,1);b/=b.sum();q=np.sum(t*b[:,None],axis=0)
        assert np.linalg.norm(q-projected[k])<1e-9
        normal=np.cross(t[1]-t[0],t[2]-t[0]);normal/=np.linalg.norm(normal)
        xyz.append(q);faces.append(ids[k]);bary.append(b);normals.append(normal)
    return dict(xyz_m=np.asarray(xyz),face_id=np.asarray(faces),barycentric=np.asarray(bary),normals=np.asarray(normals),
        projection_distance_m=np.linalg.norm(np.asarray(xyz)-points,axis=1))

def estimate(V,F,records,input_indices,input_xyz,face_ids):
    P,distances=graph_distances(V,F,records,input_indices)
    offsets,info=rbf_offsets(distances,input_indices,input_xyz-P[input_indices])
    result=surface_project(P+offsets,V,F,face_ids)
    result.update(preprojection_xyz_m=P+offsets,interpolated_offset_m=offsets,graph_distance_m=distances)
    return result,info
