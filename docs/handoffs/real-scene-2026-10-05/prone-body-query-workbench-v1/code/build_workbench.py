"""Self-contained patient surface review; manual image rays bind actual MHR triangles."""
import base64,io,json
from pathlib import Path
import numpy as np
from PIL import Image
from run_workbench import OUT,OLD,DATA,ASSETS,read,write,sha

HTML=r'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>俯卧背部点位工作台</title>
<style>body{margin:0;background:#f5f7fa;color:#233043;font:16px system-ui}header{padding:20px 28px;background:#fff;border-bottom:1px solid #ddd}h1{font-size:24px;margin:0 0 9px}p{margin:7px 0;color:#546171}main{padding:20px;display:grid;grid-template-columns:minmax(320px,1fr) minmax(440px,1.6fr);gap:20px}.card{background:white;padding:18px;border-radius:12px}canvas{max-width:100%;border:1px solid #d9e0e8;background:#eef2f6}#rgb{max-height:760px;width:auto;display:block;margin:auto}#surface{width:100%}button,select,input{font:inherit;padding:7px;margin:4px;border:1px solid #c6cfdb;border-radius:5px}button{cursor:pointer;background:#e8f2ff}label{margin-right:9px}#message{min-height:28px;color:#14643d}table{font-size:13px;border-collapse:collapse;width:100%;margin-top:12px}td,th{padding:7px;border-bottom:1px solid #eee;text-align:left}.tag{font-size:13px;padding:5px 9px;background:#fff0cf;border-radius:5px}.hint{font-size:13px;line-height:1.6}@media(max-width:850px){main{display:block}.card{margin-bottom:15px}}</style>
<header><h1>俯卧背部 Mesh 与点位复核</h1><span class="tag">研究工程演示 · 默认拓扑传播 · 未放行治疗</span><p>固定样本 S104 / input 0 / RigidD。原图点击可记录参考点；右侧查看真实缓存后背面与目标。</p><p class="hint">当前相机使用历史重建合同。ENG点与人工点击不是已验证穴位；右侧是可旋转的正交3D视图，不是透视照片。</p></header>
<main><section class="card"><h3>原图与透视叠加</h3><label><input id="meshToggle" type="checkbox" checked>显示预测后背面</label><canvas id="rgb"></canvas><p class="hint">点击后背表面增加参考点。未命中时不补点、不拟合。</p></section>
<section class="card"><h3>缓存 Mesh 与目标</h3><label>方法<select id="method"></select></label><canvas id="surface" width="800" height="600"></canvas>
<div><label>水平旋转<input id="ry" type="range" min="-180" max="180" value="-15"></label><label>俯仰<input id="rx" type="range" min="-90" max="90" value="10"></label></div>
<div><label>参考名称<input id="refName" value="REF_01"></label><button id="undo">撤销最后标记</button><button id="export">保存复核 JSON</button></div><p id="message"></p><table><thead><tr><th>点名</th><th>来源</th><th>XYZ / mm</th><th>Face ID</th></tr></thead><tbody id="rows"></tbody></table><p class="hint">橙色：当前方法8个ENG点。青色：人工图像射线与预测后背面的交点。保存包含Mesh hash、face、bary、normal与原像素；没有虚构confidence。</p></section></main>
<script>const D=__PAYLOAD__;const marks=[];const rgb=document.getElementById('rgb'),rc=rgb.getContext('2d');const surface=document.getElementById('surface'),sc=surface.getContext('2d');const methods=document.getElementById('method');let image=null;
for(const [key,label] of Object.entries(D.method_labels)){let o=document.createElement('option');o.value=key;o.textContent=label;methods.append(o)}
const add=(a,b)=>a.map((x,i)=>x+b[i]),sub=(a,b)=>a.map((x,i)=>x-b[i]),mul=(a,s)=>a.map(x=>x*s),dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function project(v){const t=D.K.map(row=>dot(row,v));return [t[0]/t[2],t[1]/t[2]]}
function rayHit(u,v){const fx=D.K[0][0],fy=D.K[1][1],cx=D.K[0][2],cy=D.K[1][2];const dir=[(u-cx)/fx,(v-cy)/fy,1];let best=null;
 for(let i=0;i<D.faces.length;i++){let tri=D.faces[i].map(j=>D.vertices_m[j]),[a,b,c]=tri,e1=sub(b,a),e2=sub(c,a),h=cross(dir,e2),det=dot(e1,h);if(Math.abs(det)<1e-12)continue;let inv=1/det,s=mul(a,-1),beta=inv*dot(s,h);if(beta<0||beta>1)continue;let q=cross(s,e1),gamma=inv*dot(dir,q);if(gamma<0||beta+gamma>1)continue;let t=inv*dot(e2,q);if(t<=0||best&&t>=best.t)continue;let n=cross(e1,e2);n=mul(n,1/Math.sqrt(dot(n,n)));best={t,xyz_m:mul(dir,t),face_id:D.global_face_ids[i],barycentric:[1-beta-gamma,beta,gamma],normal:n}}
 return best}
function allPoints(){return [...D.methods[methods.value].map(p=>({...p,source:methods.value})),...marks.map(p=>({...p,source:'manual_image_ray'}))]}
function drawRGB(){rgb.width=D.image_width;rgb.height=D.image_height;rc.fillStyle='#e8edf2';rc.fillRect(0,0,rgb.width,rgb.height);if(image)rc.drawImage(image,0,0,rgb.width,rgb.height);else{rc.fillStyle='#536274';rc.font='16px sans-serif';rc.fillText('公共版本不含原患者RGB',20,40)}
 if(document.getElementById('meshToggle').checked){rc.fillStyle='rgba(20,170,190,.13)';for(let f of D.faces){let p=f.map(j=>project(D.vertices_m[j]));rc.beginPath();p.forEach((v,i)=>i?rc.lineTo(...v):rc.moveTo(...v));rc.closePath();rc.fill()}}
 for(let p of allPoints()){let uv=project(p.xyz_m);rc.beginPath();rc.arc(...uv,4,0,2*Math.PI);rc.fillStyle=p.source==='manual_image_ray'?'#00c7d0':'#ff9300';rc.fill();rc.strokeStyle='#172b4d';rc.stroke()}}
function draw3D(){const ay=Number(document.getElementById('ry').value)*Math.PI/180,ax=Number(document.getElementById('rx').value)*Math.PI/180;let center=D.vertices_m.reduce((s,v)=>add(s,v),[0,0,0]).map(x=>x/D.vertices_m.length);
 const rotate=v=>{v=sub(v,center);let a=[v[0]*Math.cos(ay)+v[2]*Math.sin(ay),v[1],-v[0]*Math.sin(ay)+v[2]*Math.cos(ay)];return [a[0],a[1]*Math.cos(ax)-a[2]*Math.sin(ax),a[1]*Math.sin(ax)+a[2]*Math.cos(ax)]};let verts=D.vertices_m.map(rotate),bound=Math.max(...verts.map(v=>Math.max(Math.abs(v[0]),Math.abs(v[1])))),scale=240/bound;const xy=v=>[400+v[0]*scale,300+v[1]*scale];sc.clearRect(0,0,800,600);sc.fillStyle='#f5f8fb';sc.fillRect(0,0,800,600);
 let faces=D.faces.map(f=>({f,z:f.reduce((s,j)=>s+verts[j][2],0)/3})).sort((a,b)=>b.z-a.z);for(let {f} of faces){let p=f.map(j=>xy(verts[j]));sc.beginPath();p.forEach((v,i)=>i?sc.lineTo(...v):sc.moveTo(...v));sc.closePath();sc.fillStyle='#b9cbd4';sc.fill();sc.strokeStyle='rgba(65,88,100,.15)';sc.lineWidth=.4;sc.stroke()}
 for(let p of allPoints()){let uv=xy(rotate(p.xyz_m));sc.beginPath();sc.arc(...uv,5,0,2*Math.PI);sc.fillStyle=p.source==='manual_image_ray'?'#00a3b0':'#e88400';sc.fill();sc.fillStyle='#182a3a';sc.font='11px sans-serif';sc.fillText(p.id,uv[0]+7,uv[1]-4)}sc.fillStyle='#465768';sc.font='13px sans-serif';sc.fillText('当前缓存后背 / camera_m / 正交3D',15,22)}
function table(){let tbody=document.getElementById('rows');tbody.replaceChildren();for(let p of allPoints()){let tr=document.createElement('tr');for(let text of [p.id,p.source,p.xyz_m.map(x=>(x*1000).toFixed(1)).join(', '),p.face_id]){let td=document.createElement('td');td.textContent=text;tr.append(td)}tbody.append(tr)}}
function draw(){drawRGB();draw3D();table()}
rgb.addEventListener('click',e=>{if(!image){document.getElementById('message').textContent='请使用本地含原图版本标记。';return}let r=rgb.getBoundingClientRect(),u=(e.clientX-r.left)*rgb.width/r.width,v=(e.clientY-r.top)*rgb.height/r.height,hit=rayHit(u,v);if(!hit){document.getElementById('message').textContent='此像素没有命中当前后背Mesh。';return}const id=document.getElementById('refName').value.trim()||'REF_'+(marks.length+1);marks.push({id,xyz_m:hit.xyz_m,face_id:hit.face_id,barycentric:hit.barycentric,normal:hit.normal,image_uv:[u,v],origin:'manual_image_ray_on_predicted_surface'});document.getElementById('refName').value='REF_'+String(marks.length+1).padStart(2,'0');document.getElementById('message').textContent='已记录 '+id+'；这是预测面上的人工参考。';draw()});
document.getElementById('undo').onclick=()=>{marks.pop();draw()};document.getElementById('export').onclick=async()=>{let obj={schema:'PREDICTED_BACK_MANUAL_REVIEW_V1',subject:D.subject,input_seed:0,mesh_method:'RigidD',mesh_sha256:D.mesh_sha256,coordinate_frame:'historical reconstructed camera_m',selected_method:methods.value,engineering_points:D.methods[methods.value],manual_references:marks,created_at:new Date().toISOString(),medical_validated:false,robot_release:false,calibration_validated:false};
 if(location.protocol==='http:'&&location.hostname==='127.0.0.1'){let response=await fetch('/api/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});if(!response.ok){document.getElementById('message').textContent='保存失败：本地服务未写入文件。';return}let saved=await response.json();document.getElementById('message').textContent='已写入本地复核文件：'+saved.saved_file;return}
 let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(obj,null,2)],{type:'application/json'}));a.download=D.subject+'_reference_review.json';a.click();URL.revokeObjectURL(a.href);document.getElementById('message').textContent='下载请求已发起，请在浏览器下载列表确认文件。'};
for(let id of ['method','meshToggle','ry','rx'])document.getElementById(id).addEventListener('input',draw);window.workbench={rayHit,marks,payload:D};if(D.rgb_data_url){image=new Image();image.onload=draw;image.src=D.rgb_data_url}else draw();
</script></html>'''


def main():
    subject='S104';rows=[r for r in read(OUT/'TARGET_MANIFEST.json') if (r['subject'],r['split_seed'],r['mesh_method'])==(subject,0,'RigidD')]
    mesh=rows[0];full=dict(np.load(mesh['mesh_path']));mask=np.asarray(read(ASSETS/'candidate_posterior_mask.json')['face_ids']);f=full['faces'][mask];ids=np.unique(f);local=np.full(len(full['vertices_m']),-1,int);local[ids]=np.arange(len(ids))
    with np.load(DATA/'inputs'/subject/'input.npz') as data:
        image=Image.fromarray(data['rgb']);K=data['K'];buf=io.BytesIO();image.save(buf,format='JPEG',quality=90)
    labels=read(OUT/'CONFIG.json')['source_query_ids'];methods={};names={}
    for r in rows:
        key=r['method'] if r['model_seed']<0 else r['method']+'_'+str(r['model_seed']);z=dict(np.load(r['path']))
        methods[key]=[dict(id=labels[j],xyz_m=z['xyz_m'][j].tolist(),face_id=int(z['face_id'][j]),barycentric=z['barycentric'][j].tolist(),normal=z['normals'][j].tolist()) for j in range(len(labels))]
        names[key]={'TOPOLOGY':'拓扑传播（默认）','BODY_CHART_NN':'分位坐标近邻（实验）'}.get(key,'身体查询 seed'+str(r['model_seed'])+'（实验）')
    payload=dict(subject=subject,vertices_m=full['vertices_m'][ids].tolist(),faces=local[f].tolist(),global_face_ids=mask.tolist(),K=K.tolist(),image_width=image.width,image_height=image.height,mesh_sha256=mesh['mesh_sha256'],methods=methods,method_labels=names,rgb_data_url=None)
    (OUT/'site').mkdir(exist_ok=True);public=OUT/'site/public_workbench.html';public.write_text(HTML.replace('__PAYLOAD__',json.dumps(payload,separators=(',',':'))),encoding='utf-8')
    payload['rgb_data_url']='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode();private=OUT/'site/workbench.html';private.write_text(HTML.replace('__PAYLOAD__',json.dumps(payload,separators=(',',':'))),encoding='utf-8')
    write(OUT/'WORKBENCH_MANIFEST.json',dict(subject=subject,selection='fixed development source S104 / input0 / RigidD; not selected by score',mesh_path=mesh['mesh_path'],mesh_sha256=mesh['mesh_sha256'],public_path=str(public),public_sha256=sha(public),private_path=str(private),private_sha256=sha(private),faces=len(mask),vertices=len(ids),medical_validated=False,robot_release=False))
    print('WORKBENCH_HTML_COMPLETE',len(ids),len(mask),flush=True)


if __name__=='__main__':main()
