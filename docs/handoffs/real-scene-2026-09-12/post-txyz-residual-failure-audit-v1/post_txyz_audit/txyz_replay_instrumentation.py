"""Instrumentation for the frozen all-points V2.3 algorithm; never changes its update."""
import numpy as np
from scipy.spatial import cKDTree

ITERATIONS=6;TRIM_UPPER_FRACTION=.20;STEP_COMPONENT_BOUND_M=.05;TOTAL_BOUND_M=.17788820176363325
def replay(points,anchors):
    points=np.asarray(points,float);anchors=np.asarray(anchors,float);translation=np.zeros(3);trace=[]
    for iteration in range(ITERATIONS):
        distances,nearest=cKDTree(anchors+translation).query(points,workers=-1);keep=distances<=np.quantile(distances,1-TRIM_UPPER_FRACTION);residuals=points[keep]-(anchors+translation)[nearest[keep]];step=np.clip(np.median(residuals,axis=0),-STEP_COMPONENT_BOUND_M,STEP_COMPONENT_BOUND_M);translation+=step;norms=np.linalg.norm(residuals,axis=1);median=float(np.median(norms));mad=float(np.median(np.abs(norms-median)));trace.append({'iteration':iteration+1,'step_m':step.tolist(),'step_norm_m':float(np.linalg.norm(step)),'correspondence_count':int(len(distances)),'inlier_count':int(keep.sum()),'inlier_ratio':float(keep.mean()),'trimmed_residual_median_m':median,'residual_mad_m':mad,'residual_p90_m':float(np.percentile(norms,90)),'residual_p95_m':float(np.percentile(norms,95))})
    steps=np.asarray([item['step_m'] for item in trace]);step_norms=np.linalg.norm(steps,axis=1);dots=np.sum(steps[1:]*steps[:-1],axis=1);den=np.maximum(step_norms[1:]*step_norms[:-1],1e-12);raw_initial=cKDTree(anchors).query(points,workers=-1)[0]
    return {'translation_m':translation.tolist(),'fallback':bool(np.linalg.norm(translation)>TOTAL_BOUND_M),'trace':trace,'features':{'iteration_step_norms_mm':(step_norms*1000).tolist(),'iteration_convergence_ratio':float(step_norms[-1]/max(step_norms[0],1e-12)),'last_step_norm_mm':float(step_norms[-1]*1000),'step_direction_consistency':float(np.mean(dots/den)),'oscillation_indicator':bool(np.any(dots<0)),'raw_residual_median_mm':float(np.median(raw_initial)*1000),'trimmed_residual_median_mm':trace[-1]['trimmed_residual_median_m']*1000,'residual_mad_mm':trace[-1]['residual_mad_m']*1000,'residual_p90_mm':trace[-1]['residual_p90_m']*1000,'residual_p95_mm':trace[-1]['residual_p95_m']*1000,'inlier_ratio':trace[-1]['inlier_ratio']}}
