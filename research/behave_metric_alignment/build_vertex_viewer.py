"""Private all-frame 3D corresponding-vertex review, from exact cached residuals."""
import argparse
import base64
import json
from pathlib import Path
import numpy as np


def encoded(x):
    return base64.b64encode(np.ascontiguousarray(x,dtype='<f4').tobytes()).decode()


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
    rows=json.loads((root/'inputs/INPUT_MANIFEST.json').read_text())['records']
    lookup={}
    for file in (root/'evaluation').glob('*/RESULTS.json'):
        for r in json.loads(file.read_text())['records']:lookup[r['cell'],r['sequence'],r['frame']]=r
    directory=root/'visualizations/vertex_clouds';directory.mkdir(parents=True,exist_ok=True);index=[]
    for row in rows:
        ref=np.load(row['reference_file'])['vertices_camera_m'][::3]
        for seed in [11,23,37]:
            for ck in ['best','last']:
                cells=[f'official_s{seed}',f'official_s{seed}_txyz']+[f'{m}_s{seed}_{ck}' for m in ['rgb_only','g1','coarse','full']]
                methods={}
                for cell in cells:
                    report=lookup[cell,row['sequence'],row['frame']]
                    z=np.load(report['distances_file'])
                    methods[cell]=dict(vertices=encoded(z['mapped_smpl_vertices_camera_m'][::3]),
                        errors=encoded(z['corresponding_vertex_error_mm'][::3]),pve=report['pve'],
                        surface=report['frame_surface_camera_equal_mean'])
                key=f"{row['sequence']}_{row['frame']}_s{seed}_{ck}"
                data=dict(reference=encoded(ref),count=len(ref),methods=methods,coordinate='K0 camera meters; no per-method alignment',
                          sampling='SMPL vertex ids 0,3,6,... for display only; evaluation uses every vertex')
                (directory/(key+'.json')).write_text(json.dumps(data,separators=(',',':')))
                index.append(dict(key=key,subject=row['subject'],seed=seed,checkpoint=ck))
        print('VERTEX_VIEWER_FRAME',row['sequence'],row['frame'],flush=True)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>三维对应顶点 · BEHAVE</title>
<style>body{font:16px/1.6 system-ui;background:#edf2f7;color:#15304d;margin:0;padding:24px}select,button{padding:8px;font:inherit;max-width:95%}.grid{display:grid;grid-template-columns:repeat(2,minmax(360px,1fr));gap:12px}.box{background:white;border-radius:12px;padding:14px}canvas{width:100%;height:430px;background:#f9fbfd}.note{padding:14px;background:white;border-left:5px solid #c47d20;margin:15px 0}@media(max-width:850px){.grid{grid-template-columns:1fr}}h3{margin:0}</style>
<h1>从侧面、俯视看：身体对了，还是只有位置变了？</h1>
<p>选择帧 <select id="frame"></select>　模型 <select id="model"></select>　<label><input id="error" type="checkbox" checked>顶点误差着色</label></p>
<div class="note">橙色：BEHAVE 拟合参考；蓝色或热色：固定映射后的预测顶点。这里显示对应顶点云，不冒充原生 MHR 三角面。所有方法共同使用参考质心作显示原点，共同缩放；不单独对齐预测。全量评价用 6,890 顶点，显示固定抽取每三个顶点中的一个。</div>
<p id="metrics"></p><div class="grid">''' + ''.join(f'<div class="box"><h3>{title}</h3><canvas id="c{i}" width="760" height="460"></canvas></div>' for i,title in enumerate(['相机平面正交图 X/Y（不是 RGB 透视叠图）','侧面正交图 Z/Y','俯视正交图 X/Z','可旋转三维图：拖动'])) + '''</div>
<p><a id="image" href="#">打开同一帧的透视 Mesh 叠图与 K1–K3 残差</a>　<a href="../reports/BEHAVE_R5_最终对照.html">返回数字对照</a></p>
<script>const INDEX=__INDEX__;let data,center,scale,verts,err,ref,yaw=.6,pitch=.25;
const f=document.getElementById('frame'),m=document.getElementById('model');INDEX.forEach((r,i)=>f.add(new Option(r.key,i)));
const decode=s=>{let b=atob(s),a=new Uint8Array(b.length);for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return new Float32Array(a.buffer)};
const triples=a=>Array.from({length:a.length/3},(_,i)=>[a[3*i],a[3*i+1],a[3*i+2]]);
async function load(){let r=INDEX[Number(f.value)];data=await(await fetch('vertex_clouds/'+r.key+'.json')).json();ref=triples(decode(data.reference));m.innerHTML='';Object.keys(data.methods).forEach(k=>m.add(new Option(k,k)));center=[0,1,2].map(j=>ref.reduce((a,v)=>a+v[j],0)/ref.length);let all=[ref,...Object.values(data.methods).map(v=>triples(decode(v.vertices)))].flat();let radius=Math.max(...all.map(v=>Math.hypot(...v.map((x,j)=>x-center[j]))));scale=180/Math.max(radius,.1);document.getElementById('image').href=r.key+'.jpg';select();}
function select(){let v=data.methods[m.value];verts=triples(decode(v.vertices));err=decode(v.errors);document.getElementById('metrics').textContent=`PVE ${v.pve.pve_absolute_mm.toFixed(2)} mm；去质心 ${v.pve.pve_centroid_centered_mm.toFixed(2)} mm；该帧三相机平均表面 median ${v.surface.median_mm.toFixed(2)} mm，P95 ${v.surface.p95_mm.toFixed(2)} mm。热色从低误差蓝色到高误差红色，显示上限 150 mm；数值未截断。`;draw();}
function project(v,i){let p=v.map((x,j)=>x-center[j]);if(i===0)return[p[0],p[1]];if(i===1)return[p[2],p[1]];if(i===2)return[p[0],-p[2]];let x=Math.cos(yaw)*p[0]+Math.sin(yaw)*p[2],z=-Math.sin(yaw)*p[0]+Math.cos(yaw)*p[2];return[x,Math.cos(pitch)*p[1]-Math.sin(pitch)*z];}
function draw(){for(let i=0;i<4;i++){let c=document.getElementById('c'+i),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);ctx.strokeStyle='#d9e2ec';ctx.beginPath();ctx.moveTo(380,0);ctx.lineTo(380,460);ctx.moveTo(0,230);ctx.lineTo(760,230);ctx.stroke();for(const [points,isref] of [[ref,true],[verts,false]])for(let j=0;j<points.length;j++){let [x,y]=project(points[j],i);ctx.fillStyle=isref?'#e98d2277':document.getElementById('error').checked?`hsl(${220*(1-Math.min(err[j]/150,1))},85%,45%)`:'#2678c9';ctx.fillRect(380+x*scale,230+y*scale,isref?2:2.5,isref?2:2.5);}ctx.fillStyle='#536579';ctx.fillText('共同显示尺度；橙色为拟合参考',10,20);}}
f.onchange=load;m.onchange=select;document.getElementById('error').onchange=draw;let c=document.getElementById('c3'),last;c.onpointerdown=e=>{last=[e.clientX,e.clientY];c.setPointerCapture(e.pointerId)};c.onpointermove=e=>{if(!last)return;yaw+=(e.clientX-last[0])*.01;pitch+=(e.clientY-last[1])*.01;last=[e.clientX,e.clientY];draw()};c.onpointerup=()=>last=null;load();</script></html>'''
    (root/'visualizations/vertex_viewer.html').write_text(page.replace('__INDEX__',json.dumps(index)),encoding='utf-8')
    (root/'reports/VERTEX_VIEWER_MANIFEST.json').write_text(json.dumps(dict(status='COMPLETE',records=index,
        expected=len(rows)*6,source='Cached mapped vertices and cached true full-vertex errors; fixed vertex stride3 for display only'),indent=2))


if __name__=='__main__':main()
