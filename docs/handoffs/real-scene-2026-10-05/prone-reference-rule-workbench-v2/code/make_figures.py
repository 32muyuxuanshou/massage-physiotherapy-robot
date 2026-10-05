"""All-patient cached geometry display; no anatomical accuracy comparison."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT.parent/'prone-reference-rule-workbench-v1/site'
data = json.loads((ROOT/'ENGINEERING_COMPLETION_RESULTS.json').read_text())
(ROOT/'figures').mkdir(exist_ok=True)
for row in data['records']:
    mesh = json.loads((ASSETS/'cases'/(row['subject']+'.json')).read_text())
    V = np.array(mesh['vertices_m'])*1000; F = np.array(mesh['faces']); ids = {g:i for i,g in enumerate(mesh['global_face_ids'])}
    fig, ax = plt.subplots(figsize=(6, 8)); ax.add_collection(PolyCollection(V[F, :2], facecolors='#dce4ea', edgecolors='#a2b2c0', linewidths=.1))
    for name, ref in row['proposals']['input_references'].items():
        xyz = np.array(ref['barycentric']) @ V[F[ids[ref['face_id']]]]; ax.scatter(*xyz[:2], c='#00aaba');ax.text(*xyz[:2], name, fontsize=8)
    for name, ref in row['proposals']['suggestions'].items():
        xyz=np.array(ref['xyz_m'])*1000; ax.scatter(*xyz[:2], c='#e6b900');ax.text(*xyz[:2], name+' proposal', fontsize=8)
    for ref in row['rule_output']['rules']:
        xyz=np.array(ref['xyz_m'])*1000;ax.scatter(*xyz[:2],c='#a73ce0',s=10)
    ax.autoscale();ax.set_aspect('equal');ax.invert_yaxis();ax.set_xlabel('camera X / mm');ax.set_ylabel('camera Y / mm')
    ax.set_title(row['subject']+' / 4 geometry input fixtures\n3 CT-prior suggestions + 8 rule candidates\nNOT ANATOMICAL GROUND TRUTH');fig.tight_layout()
    fig.savefig(ROOT/'figures'/(row['subject']+'.png'),dpi=110);plt.close(fig)
files=sorted((ROOT/'figures').glob('*.png'));pages=[];(ROOT/'montages').mkdir(exist_ok=True)
for start in range(0,len(files),6):
    canvas=Image.new('RGB',(1500,1500),'white')
    for i,path in enumerate(files[start:start+6]):
        im=Image.open(path).convert('RGB');im.thumbnail((470,700));x=(i%3)*500;y=(i//3)*750;canvas.paste(im,(x+(500-im.width)//2,y+25));ImageDraw.Draw(canvas).text((x+15,y+8),path.stem,fill='black')
    path=ROOT/'montages'/('all_'+str(start//6+1)+'.jpg');canvas.save(path,quality=88);pages.append(path.name)
print('cached figures',len(files),'pages',pages)
