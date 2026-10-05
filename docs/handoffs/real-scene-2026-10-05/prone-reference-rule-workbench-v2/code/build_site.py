"""Reuse existing workbench geometry, add explicit proposal/acceptance controls."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent/'prone-reference-rule-workbench-v1'
PRIOR = ROOT.parent/'tum-synchronized-anatomy-validation-v1/REFERENCE_PRIOR_FIT.json'

for name in ['rule_pipeline.py', 'frozen_rule_engine.py', 'check_pipeline.py']:
    (ROOT/'code'/name).write_bytes((OLD/'code'/name).read_bytes())
(ROOT/'code/frozen_reference_prior.json').write_bytes(PRIOR.read_bytes())
html = (OLD/'site/index.html').read_text(encoding='utf8')
html = html.replace('俯卧背部参考与规则工作台', '俯卧背部两参考与规则工作台')
html = html.replace('参考 → 规则候选 → Mesh绑定', '两参考 → 待复核建议 → 规则候选 → Mesh绑定')
html = html.replace('先记录5个椎体水平候选与左右方向参考，再填写比例。', '先输入T3、L2与左右方向参考；可生成其余待复核建议，也可逐点手工录入。')
html = html.replace('青色是输入参考，紫色是规则候选，橙色是原ENG拓扑点。', '青色是图像输入，黄色是未采纳建议，蓝色是工程采纳建议，紫色是规则候选。')
html = html.replace('<div><button id="generate">', '<div><button id="propose">两参考生成待复核建议</button><button id="accept">采纳建议为工程候选（未医学确认）</button></div>\n<div><button id="generate">')
html = html.replace('let refs={},history=[],rules=[],ruleOutput=null;', 'let refs={},history=[],rules=[],ruleOutput=null,proposals={},proposalOutput=null;')
html = html.replace("...Object.entries(refs).map(([id,p])=>({...p,id,type:'输入参考',color:'#00aaba'})),", "...Object.entries(refs).map(([id,p])=>({...p,id,type:p.origin==='ENGINEERING_ACCEPTED_CT_PROXY_SUGGESTION'?'工程采纳建议':'图像输入参考',color:p.origin==='ENGINEERING_ACCEPTED_CT_PROXY_SUGGESTION'?'#245fdd':'#00aaba'})),...Object.entries(proposals).map(([id,p])=>({...p,id,type:'未采纳CT代理建议',color:'#e6b900'})),")
html = html.replace('rules=[];ruleOutput=null;image=null;', 'rules=[];ruleOutput=null;proposals={};proposalOutput=null;image=null;')
html = html.replace("$('reference').value=required[0]", "$('reference').value='T3'")
html = html.replace("history.push({name,previous:refs[name]});", "clearDerived();history.push({name,previous:refs[name]});")
html = html.replace('const next=required.find(n=>!refs[n]);', "const next=['T3','L2','LEFT_REF','RIGHT_REF',...required].find(n=>!refs[n]);")
html = html.replace("$('undo').onclick=()=>{", "$('undo').onclick=()=>{clearDerived();")
html = html.replace("$('generate').onclick", """function clearDerived(){proposals={};proposalOutput=null;for(const name of required){if(refs[name]?.origin==='ENGINEERING_ACCEPTED_CT_PROXY_SUGGESTION')delete refs[name]}rules=[];ruleOutput=null;}
$('propose').onclick=async()=>{const need=['T3','L2','LEFT_REF','RIGHT_REF'].filter(n=>!refs[n]);if(need.length){$('status').textContent='先录入 '+need.join(', ');return}const r=await fetch('/api/propose',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({subject:D.subject,mesh_sha256:D.mesh_sha256,references:Object.fromEntries(['T3','L2','LEFT_REF','RIGHT_REF'].map(n=>[n,refs[n]]))})});proposalOutput=await r.json();proposals=proposalOutput.suggestions;rules=[];ruleOutput=null;$('status').textContent='已生成3个未采纳建议。C7骨代理不等于C7下方凹陷；请复核/重点击，或仅采纳为工程候选。';draw()};
$('accept').onclick=()=>{for(const[name,p]of Object.entries(proposals)){history.push({name,previous:refs[name]});refs[name]={...p,origin:'ENGINEERING_ACCEPTED_CT_PROXY_SUGGESTION',accepted_as_engineering_candidate:true}}proposals={};rules=[];ruleOutput=null;$('status').textContent='建议仅作为工程候选采纳，医学身份仍未确认。填比例后可生成规则候选。';draw()};
$('generate').onclick""")
html = html.replace('references:refs,b_cun_mm:', 'references:refs,proposal_output:proposalOutput,b_cun_mm:')
html = html.replace("schema:'PATIENT_REFERENCE_RULE_REVIEW_V1'", "schema:'PATIENT_REFERENCE_RULE_REVIEW_V2'")
html = html.replace('CT骨标签代理不会自动替换这里的棘突凹陷参考。', 'CT代理建议不等于棘突凹陷；工程采纳也不是医学确认。更改输入会清除依赖它的建议。')
html = html.replace('<th>Face</th>', '<th>Face</th><th>投影距离/mm</th>')
html = html.replace("p.face_id??'—']", "p.face_id??'—',p.projection_distance_mm==null?'—':p.projection_distance_mm.toFixed(1)]")
(ROOT/'site').mkdir(exist_ok=True); (ROOT/'site/index.html').write_text(html, encoding='utf8')
print('site built; original rule engine unchanged')
