"""Recompute bindings/statistics and draw cached fields; no model inference."""
import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from run_observed import ROOT, WORKBENCH, PREVIOUS_EXECUTION, load_json, sha, save_json, verify
from patient_interface import decode_field, frame_and_references
from reference_frame import to_local
from rule_pipeline import generate


def project(points, K):
    return points[:,:2]/points[:,2,None]*[K[0,0],K[1,1]]+[K[0,2],K[1,2]]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--private-output', type=Path)
    parser.add_argument('--subject', default='S107')
    args=parser.parse_args()
    subject=args.subject
    report=load_json(ROOT/'results'/subject/'EXECUTION_RESULT.json')
    mesh=load_json(WORKBENCH/'site/cases'/(subject+'.json'))
    vertices=np.asarray(mesh['vertices_m']);directory=ROOT/'results'/subject
    names=['MESH_SAMPLED_FIXTURE','AUTHOR_FILTERED_OBSERVED_PC']; data=[]; documents=[]
    for name in names:
        cache=directory/(name+'.npz');document=load_json(directory/(name+'.json'))
        assert sha(cache)==document['cache_sha256']
        with np.load(cache) as z: data.append({key:z[key] for key in z.files})
        z=data[-1]
        assert np.array_equal(z['vertices_m'],vertices)
        assert np.array_equal(z['faces'],mesh['faces'])
        frame,_=frame_and_references(mesh,document['supplied_references'],[0.,0.,0.])
        assert np.allclose(to_local(vertices,frame),z['local_query'],rtol=0,atol=1e-12)
        decoded=decode_field(mesh,z['learned_field'],frame)
        for key in decoded:
            assert decoded[key]['face_id']==document['suggestions'][key]['face_id']
            assert np.allclose(decoded[key]['barycentric'],document['suggestions'][key]['barycentric'],rtol=0,atol=1e-12)
            assert np.allclose(decoded[key]['xyz_m'],document['suggestions'][key]['xyz_m'],rtol=0,atol=1e-12)
        rules=generate(mesh,{**document['supplied_references'],**decoded},25.,'FIXTURE_25_MM_NOT_MEDICAL')
        verify(mesh,rules)
        for new,old in zip(rules['rules'],document['rules']['rules']):
            assert np.allclose(new['xyz_m'],old['xyz_m'],rtol=0,atol=1e-12)
        documents.append(document)
    moved={k:float(np.linalg.norm(np.asarray(documents[1]['suggestions'][k]['xyz_m'])-
        documents[0]['suggestions'][k]['xyz_m'])*1000) for k in documents[0]['suggestions']}
    assert moved==report['suggestion_input_change_mm']
    assert float(np.percentile(abs(data[1]['ray_delta_mm']),95))==report['raw_ray_delta_abs_p95_mm']
    with np.load(PREVIOUS_EXECUTION/'results/inputs'/subject/'split_0.npz') as z:
        assert np.intersect1d(data[1]['observed_indices'],z['heldout_idx']).size==0
        assert np.isin(data[1]['observed_indices'],z['train_idx']).all()
    figures=ROOT/'figures';figures.mkdir(exist_ok=True)
    fig,axes=plt.subplots(2,3,figsize=(12,8),sharex=True,sharey=True)
    local=data[0]['local_query']*500.
    delta_limit=max(float(np.max(abs(d['ray_delta_mm']))) for d in data)
    for row,(name,z,doc) in enumerate(zip(names,data,documents)):
        s=axes[row,0].scatter(local[:,0],local[:,2],c=z['learned_field'][:,0],s=5,cmap='viridis',vmin=-.4,vmax=1.4)
        fig.colorbar(s,ax=axes[row,0],label='longitudinal coordinate')
        for key,value in doc['suggestions'].items():
            xy=to_local(np.asarray(value['xyz_m'])[None],frame)[0]*500.
            axes[row,0].scatter(xy[0],xy[2],marker='x',c='red',s=25)
            axes[row,0].annotate(key,xy[[0,2]]+np.array([5.,0.]),fontsize=8)
        s=axes[row,1].scatter(local[:,0],local[:,2],c=z['learned_field'][:,1]*500.,s=5,cmap='coolwarm',vmin=-150,vmax=150)
        fig.colorbar(s,ax=axes[row,1],label='lateral coordinate (mm)')
        s=axes[row,2].scatter(local[:,0],local[:,2],c=z['ray_delta_mm'],s=5,cmap='coolwarm',vmin=-delta_limit,vmax=delta_limit)
        fig.colorbar(s,ax=axes[row,2],label='raw ray correction (mm)')
        for col,title in enumerate(['suggestion coordinates','lateral field','raw correction: NOT APPLIED']):
            axes[row,col].set_title(('Mesh-sampled fixture' if row==0 else 'Actual observed author PC')+'\n'+title,fontsize=9)
            axes[row,col].set_aspect('equal');axes[row,col].set_xlabel('local right (mm)')
            axes[row,col].set_ylabel('local inferior (mm)')
    axes[0,0].invert_yaxis()
    fig.suptitle(subject+' | same fixed mesh / model / four reference fixtures | no medical accuracy claim',fontsize=10)
    figure_path=figures/(subject+'_INPUT_SOURCE_COMPARISON.png')
    fig.tight_layout();fig.savefig(figure_path,dpi=150);plt.close(fig)
    result=dict(status='PASS_CACHE_REPLAY_NO_MODEL_INFERENCE',caches=2,suggestions_redecoded=6,
        rules_reconstructed=16,frozen_mesh_unchanged=True,train_heldout_intersection=0,
        public_figure_sha256=sha(figure_path),
        scope='Numerical/cache binding and input identity only, not anatomical correctness')
    if args.private_output:
        draw_private_overlay(args.private_output,subject,data,documents,mesh,frame)
        result['private_overlay_sha256']=sha(args.private_output/(subject+'_ACTUAL_INPUT_OVERLAY.png'))
    save_json(directory/'CACHE_REPLAY.json',result);print(result)


def draw_private_overlay(private_output,subject,data,documents,mesh,frame):
    with np.load(private_output/'inputs'/subject/'input.npz') as z:
        observed=z['points_m'][data[1]['observed_indices']];rgb=z['rgb'];K=z['K']
    vertices=np.asarray(mesh['vertices_m'])
    # Original image is private. These are observed projections/mesh edges and
    # unverified engineering candidates, not true anatomical annotations.
    fig,axes=plt.subplots(1,3,figsize=(12,8),sharex=True,sharey=True)
    mesh_uv=project(vertices,K);point_uv=project(observed,K)
    faces=np.asarray(mesh['faces'])
    for i,ax in enumerate(axes):
        ax.imshow(rgb);ax.set_xlim(0,rgb.shape[1]);ax.set_ylim(rgb.shape[0],0);ax.axis('off')
        ax.set_title(['Original RGB','Actual train observations + fixed mesh','Unverified proxy/rule candidates'][i],fontsize=9)
    axes[1].triplot(mesh_uv[:,0],mesh_uv[:,1],faces,color='white',alpha=.12,lw=.3)
    sc=axes[1].scatter(point_uv[:,0],point_uv[:,1],c=observed[:,2],s=4,cmap='viridis')
    color_axis=axes[1].inset_axes([1.02,.35,.035,.3])
    fig.colorbar(sc,cax=color_axis,label='observed camera Z (m)')
    axes[2].triplot(mesh_uv[:,0],mesh_uv[:,1],faces,color='lime',alpha=.25,lw=.4)
    for key,slot in documents[1]['suggestions'].items():
        xy=project(np.asarray(slot['xyz_m'])[None],K)[0]
        axes[2].scatter(*xy,c='orange',marker='x',s=35);axes[2].annotate(key,xy+[8.,0.],color='orange',fontsize=8)
    for rule in documents[1]['rules']['rules']:
        xy=project(np.asarray(rule['xyz_m'])[None],K)[0]
        axes[2].scatter(*xy,c='cyan',s=13)
    fig.suptitle(subject+' | approximate camera; 4 fixture references; 25 mm fixture scale; NOT clinical',fontsize=10)
    fig.tight_layout();private_output.mkdir(exist_ok=True,parents=True)
    fig.savefig(private_output/(subject+'_ACTUAL_INPUT_OVERLAY.png'),dpi=150);plt.close(fig)


if __name__=='__main__':main()
