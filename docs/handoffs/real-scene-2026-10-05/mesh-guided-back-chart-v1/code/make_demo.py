"""Visualize the preselected cached S104 engineering interface, with coverage flags."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(root):
    target=json.loads((root/'targets/S104.json').read_text())
    with np.load(target['mesh_path']) as z:v=z['vertices_m'];f=z['faces']
    np.savez_compressed(root/'DEMO_MESH_S104.npz',vertices_m=v,faces=f)
    p=np.asarray([r['xyz_m'] for r in target['points']]);bad=np.asarray([r['clamped'] for r in target['points']])
    colors=np.where(bad,'red','limegreen')
    data=json.dumps(dict(v=v.tolist(),f=f.tolist(),p=p.tolist(),bad=bad.tolist()))
    html='''<!doctype html><meta charset="utf-8"><title>Cached engineering interface</title>
<h2>S104：缓存 Mesh 与 27 个工程探针</h2><p>红点：超过参考线范围，已钳制到端点。绿点：范围内。不是穴位，不允许治疗执行。</p>
<label>旋转 <input id="a" type="range" min="-180" max="180" value="0"></label>
<label>俯仰 <input id="b" type="range" min="-90" max="90" value="0"></label>
<canvas id="c" width="900" height="850"></canvas><script>
const d=DATA, c=document.getElementById('c'),ctx=c.getContext('2d'),a=document.getElementById('a'),b=document.getElementById('b');
const origin=d.v.reduce((s,p)=>s.map((x,j)=>x+p[j]/d.v.length),[0,0,0]);
function draw(){let t=a.value*Math.PI/180,h=b.value*Math.PI/180;let all=d.v.concat(d.p).map(p=>{
let x=p[0]-origin[0],y=p[1]-origin[1],z=p[2]-origin[2],xx=x*Math.cos(t)+z*Math.sin(t),zz=-x*Math.sin(t)+z*Math.cos(t);
return [450+400*xx,425+400*(y*Math.cos(h)-zz*Math.sin(h)),y*Math.sin(h)+zz*Math.cos(h)];});
ctx.clearRect(0,0,c.width,c.height);let faces=d.f.map(f=>({f,z:f.reduce((s,i)=>s+all[i][2]/3,0)})).sort((x,y)=>y.z-x.z);
ctx.fillStyle='#b5b8c1';ctx.strokeStyle='#9296a0';ctx.lineWidth=.15;
faces.forEach(({f})=>{ctx.beginPath();f.forEach((i,j)=>j?ctx.lineTo(all[i][0],all[i][1]):ctx.moveTo(all[i][0],all[i][1]));ctx.closePath();ctx.fill();ctx.stroke();});
d.p.forEach((p,j)=>{let q=all[d.v.length+j];ctx.fillStyle=d.bad[j]?'#e22':'#0a4';ctx.beginPath();ctx.arc(q[0],q[1],4,0,2*Math.PI);ctx.fill();});}
a.oninput=b.oninput=draw;draw();</script>'''
    (root/'DEMO_S104.html').write_text(html.replace('DATA',data),encoding='utf-8')
    fig,ax=plt.subplots(1,3,figsize=(15,6))
    for a,(x,y,name) in zip(ax,[(0,1,'XY / camera-plane orthographic'),(0,2,'XZ / depth'),(1,2,'YZ / depth')]):
        a.scatter(v[::4,x]*1000,v[::4,y]*1000,s=.3,color='lightgray');a.scatter(p[:,x]*1000,p[:,y]*1000,c=colors,s=22)
        a.set_aspect('equal');a.set_title(name);a.set_xlabel('mm');a.set_ylabel('mm')
        if y==1:a.invert_yaxis()
    fig.suptitle('S104 / cached RigidD + 27 engineering probes\nRed: target outside predicted curve range, endpoint clamped; NOT medical locations')
    fig.tight_layout();fig.savefig(root/'DEMO_S104.png',dpi=110);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
