"""Prespecified translation-only LS/Huber operators, no heldout inputs."""
import numpy as np
from common import CFG


def update(residual,normals,kind='plane',trim=True,gate=False):
    if len(residual)==0:return np.zeros(3),dict(observed=0,retained=0,rank=0)
    distance=np.linalg.norm(residual,axis=1)
    keep=distance<=np.quantile(distance,.8) if trim else np.ones(len(distance),bool)
    r=residual[keep].astype(np.float64);n=normals[keep].astype(np.float64)
    b=np.einsum('ij,ij->i',n,r);weights=np.ones(len(r))
    if kind=='median':step=np.median(r,axis=0)
    else:
        step=np.linalg.lstsq(n,b,rcond=1e-6)[0]
        if kind=='huber':
            for _ in range(CFG['irls_reweightings']):
                error=np.abs(b-n@step)
                weights=np.minimum(1,CFG['huber_delta_m']/np.maximum(error,1e-12))
                w=np.sqrt(weights);step=np.linalg.lstsq(n*w[:,None],b*w,rcond=1e-6)[0]
    matrix=n.T@(weights[:,None]*n)/weights.sum();ev,axes=np.linalg.eigh(matrix)
    if gate:step=axes@((ev.clip(0)/(ev.clip(0)+.01))*(axes.T@step))
    raw_step=step.copy();step=np.clip(step,-.05,.05)
    return step,dict(observed=len(residual),retained=len(r),normal_eigenvalues=ev.tolist(),
        rank=int(np.sum(ev>ev.max()*1e-12)),euclidean_median_m=float(np.median(distance)),
        plane_abs_median_m=float(np.median(abs(b))),weight_mean=float(weights.mean()),
        unclipped_step_m=raw_step.tolist(),step_clipped=bool(np.any(raw_step!=step)))


def finish(raw):
    fallback=bool(np.linalg.norm(raw)>.17788820176363325)
    return np.zeros(3) if fallback else raw.copy(),fallback


def analytic_qa():
    rng=np.random.default_rng(52);n=rng.normal(size=(200,3));n/=np.linalg.norm(n,axis=1)[:,None]
    delta=np.array([.009,-.006,.011]);r=np.tile(delta,(200,1))
    for kind in ['median','plane','huber']:
        for trim in [False,True]:np.testing.assert_allclose(update(r,n,kind,trim)[0],delta,atol=1e-12)
    flat=np.tile([0.,0.,1.],(200,1))
    np.testing.assert_allclose(update(r,flat)[0],[0,0,.011],atol=1e-12)
    return dict(known_translation_exact=True,flat_surface_minimum_norm=True)
