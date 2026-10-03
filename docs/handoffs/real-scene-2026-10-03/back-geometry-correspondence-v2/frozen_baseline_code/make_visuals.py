"""Render cached meshes with the same pinhole K; never refit a mesh."""
import argparse
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data_v2 import load_json,save_json,sha,project,point_pixels
from cache_v2 import mesh_path,verify_cache
from evaluate_cache import silhouette_metrics,projected_support


def render_depth_cpu(vertices,faces,K,height,width):
    """Conservative triangle bounds, inverse-Z interpolation, first intersection.

    Pixel samples are at integer OpenCV coordinates. Primary ray evaluation is
    continuous and independent of this image rasterizer.
    """
    tri=np.asarray(vertices,float)[faces]
    if np.any(tri[:,:,2]<=0):raise ValueError('Positive-Z triangles required')
    uv=project(vertices,K)[faces];depth=np.full((height,width),np.inf)
    for t,z in zip(uv,tri[:,:,2]):
        x0=max(0,int(np.ceil(t[:,0].min())));x1=min(width-1,int(np.floor(t[:,0].max())))
        y0=max(0,int(np.ceil(t[:,1].min())));y1=min(height-1,int(np.floor(t[:,1].max())))
        if x1<x0 or y1<y0:continue
        a,b,c=t;e1=b-a;e2=c-a;den=e1[0]*e2[1]-e1[1]*e2[0]
        if abs(den)<1e-12:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1),np.arange(y0,y1+1));dx=xx-a[0];dy=yy-a[1]
        w1=(dx*e2[1]-e2[0]*dy)/den;w2=(e1[0]*dy-dx*e1[1])/den
        inside=(w1>=-1e-9)&(w2>=-1e-9)&(w1+w2<=1+1e-9)
        inv=(1-w1-w2)/z[0]+w1/z[1]+w2/z[2]
        candidate=np.full_like(inv,np.inf);candidate[inside]=1/inv[inside]
        view=depth[y0:y1+1,x0:x1+1];np.minimum(view,candidate,out=view)
    depth[~np.isfinite(depth)]=0
    return depth


def slice_segments(vertices,faces,x_plane):
    tri=vertices[faces];s=tri[:,:,0]-x_plane
    tri=tri[(s.min(1)<=0)&(s.max(1)>=0)];segments=[]
    for t in tri:
        pts=[]
        for a,b in [(0,1),(1,2),(2,0)]:
            da=t[a,0]-x_plane;db=t[b,0]-x_plane
            if da*db<0:pts.append(t[a]+da/(da-db)*(t[b]-t[a]))
        if len(pts)==2:segments.append(np.asarray(pts)[:,1:3])
    return segments


def visualize_subject(subject,delivery,out,methods=None,seeds=None):
    contract=load_json(delivery/'EXPERIMENT_CONTRACT.json');names=methods or contract['methods']
    seeds=contract['seeds'] if seeds is None else seeds
    inp=np.load(out/'inputs'/subject/'input.npz',allow_pickle=False)
    rgb=inp['rgb'];K=inp['K'];points=inp['points_m'];roi=inp['posterior_rgb_mask']
    h,w=rgb.shape[:2];support=projected_support(points,K,(h,w))
    polygon=next(x['polygon_xy_px'] for x in load_json(delivery/'POSTERIOR_RGB_ROI.json')['entries'] if x['subject']==subject)
    manifest=[]
    for seed in seeds:
        dest=out/'visualizations'/subject/f'seed_{seed}';dest.mkdir(parents=True,exist_ok=True)
        panel=Image.new('RGB',((len(names)+1)*w,h+100),'white');draw=ImageDraw.Draw(panel)
        panel.paste(Image.fromarray(rgb),(0,100));draw.text((8,8),subject+f' seed {seed}: original RGB',fill='black')
        draw.text((8,29),'Purple/green: predicted mesh',fill='black')
        draw.text((8,47),'Cyan: cloud projection; yellow: ROI',fill='black')
        draw.text((8,65),'Approximate camera; not GT alignment',fill='black')
        fig,axes=plt.subplots(1,2,figsize=(13,5))
        xplane=float(np.median(points[inp['posterior_point_mask'],0]))
        slice_cloud=points[np.abs(points[:,0]-xplane)<.008]
        axes[0].scatter(slice_cloud[:,1],slice_cloud[:,2],s=1,c='black',alpha=.15,label='observed cloud |X-X0|<8mm')
        quality=[];translations=[]
        for i,name in enumerate(names):
            path=mesh_path(out,subject,seed,name);meta=verify_cache(path,out,subject,seed)
            z=np.load(path,allow_pickle=False);V=z['vertices_m'];F=z['faces']
            dep=render_depth_cpu(V,F,K,h,w);mask=dep>0
            np.savez_compressed(dest/(name.replace('+','_')+'_render.npz'),depth_m=dep)
            img=rgb.copy();img[mask]=np.clip(.58*img[mask]+.42*np.array([255,70,160]),0,255).astype(np.uint8)
            contour,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(img,contour,-1,(30,255,80),1)
            cloud=points[::80];uv,good=point_pixels(cloud,K,(h,w))
            img[uv[good,1],uv[good,0]]=(0,255,255)
            cv2.polylines(img,[np.asarray(polygon,np.int32)],True,(255,230,0),1)
            file=dest/(name.replace('+','_')+'_overlay.png');Image.fromarray(img).save(file)
            meta['silhouette']=silhouette_metrics(mask,support)
            meta['visualization']=dict(renderer='CPU inverse-Z pinhole at integer pixel coordinates',input_npz_sha256=sha(out/'inputs'/subject/'input.npz'),overlay=str(file.relative_to(out)))
            save_json(path.with_suffix('.json'),meta)
            panel.paste(Image.fromarray(img),((i+1)*w,100));draw.text(((i+1)*w+8,8),name,fill='black')
            met=out/'evaluation'/subject/f'seed_{seed}'/(name.replace('+','_')+'_metrics.npz')
            if met.exists():
                ev=np.load(met,allow_pickle=False);d=ev['posterior_d3d_m']*1000
                draw.text(((i+1)*w+8,29),f'Back d3d med {np.median(d):.2f} / P95 {np.percentile(d,95):.2f} mm',fill='black')
                draw.text(((i+1)*w+8,47),f'Ray hit {ev["posterior_hit"].mean():.1%}; common {ev["posterior_common_hit"].mean():.1%}',fill='black')
                uv,good=point_pixels(points[ev['posterior_point_idx']],K,(h,w))
                heat=rgb.copy();level=(np.minimum(d/50,1)*255).astype(np.uint8).reshape(-1,1)
                colors=cv2.applyColorMap(level,cv2.COLORMAP_TURBO).reshape(-1,3)[:,::-1]
                for pt,color in zip(uv[good],colors[good]):cv2.circle(heat,tuple(pt),2,tuple(int(v) for v in color),-1)
                Image.fromarray(heat).save(dest/(name.replace('+','_')+'_posterior_residual.png'))
            segments=slice_segments(V,F,xplane)
            color=f'C{i}'
            for j,seg in enumerate(segments):axes[0].plot(seg[:,0],seg[:,1],color=color,lw=.6,label=name if j==0 else None)
            quality.append(meta['mesh_quality']['edge_strain_p99'])
            if 'effective_cam_t_m' in z:translations.append(z['effective_cam_t_m'])
            manifest.append(dict(subject=subject,seed=seed,method=name,mesh_sha256=sha(path),overlay=str(file.relative_to(out)),rendered_pixel_count=int(mask.sum())))
        panel.save(dest/'comparison.jpg',quality=93)
        axes[0].invert_yaxis();axes[0].set_xlabel('camera Y (m)');axes[0].set_ylabel('camera Z (m), deeper down')
        axes[0].set_title(f'Camera-X plane X0={xplane:.3f} m; not anatomical midline');axes[0].legend(fontsize=6)
        axes[1].bar(np.arange(len(names)),quality);axes[1].set_xticks(np.arange(len(names)),names,rotation=35,ha='right',fontsize=7)
        axes[1].set_ylabel('P99 relative edge-length change');axes[1].set_title('Against method input, global rotation removed')
        fig.tight_layout();fig.savefig(dest/'camera_x_slice_and_quality.png',dpi=130);plt.close(fig)
        if len(translations)==len(names):
            delta=(np.asarray(translations)-translations[0])*1000;fig,ax=plt.subplots(figsize=(9,4))
            for j,label in enumerate(['Tx','Ty','Tz']):ax.bar(np.arange(len(names))+.23*(j-1),delta[:,j],width=.23,label=label)
            ax.set_xticks(np.arange(len(names)),names,rotation=25,ha='right');ax.set_ylabel('effective camera translation delta vs Official (mm)')
            ax.legend();fig.tight_layout();fig.savefig(dest/'translation_xyz.png',dpi=130);plt.close(fig)
    save_json(out/'visualizations'/subject/'manifest.json',manifest)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--subjects',nargs='+',required=True)
    p.add_argument('--methods',nargs='+');p.add_argument('--seeds',nargs='+',type=int);a=p.parse_args()
    for s in a.subjects:visualize_subject(s,Path(__file__).resolve().parents[1],a.out,a.methods,a.seeds)
