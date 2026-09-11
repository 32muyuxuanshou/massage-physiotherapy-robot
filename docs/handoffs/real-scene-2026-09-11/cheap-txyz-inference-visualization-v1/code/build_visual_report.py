import json,html
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parents[1];rows=json.loads((p/'raw_results.json').read_text());T=np.array([r['Txyz_m'] for r in rows])*1000
fig,axs=plt.subplots(2,2,figsize=(10,7));
for ax,v,title in zip(axs.ravel(),[T[:,0],T[:,1],T[:,2],np.linalg.norm(T,axis=1)],['Tx (mm)','Ty (mm)','Tz (mm)','|T| (mm)']):ax.hist(v,bins=12,color='#2878b5');ax.set_title(title);ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(p/'TXYZ_DISTRIBUTION.png',dpi=160);plt.close(fig)
cards=[]
for r in rows:
 case='case_'+r['id'];t=np.array(r['Txyz_m'])*1000
 cards.append(f'''<article data-subject="{html.escape(r['subject_id'])}" data-pose="{html.escape(str(r['sequence']))}"><h2>{r['id']} · {r['outcome_class']}</h2><p>T=({t[0]:+.1f},{t[1]:+.1f},{t[2]:+.1f}) mm, |T|={np.linalg.norm(t):.1f} mm · B median {r['official_B']['median_mm']:.1f}→{r['corrected_B']['median_mm']:.1f} mm</p><img src="visualizations/{case}/rgb_overlay_comparison.png"><img src="visualizations/{case}/depth_residual_comparison.png"><img src="visualizations/{case}/b_heldout_comparison.png"><p><a href="visualizations/{case}/3d_viewer.html">interactive 3D viewer</a> · <a href="visualizations/{case}/metrics.json">metrics</a></p></article>''')
doc='''<!doctype html><meta charset="utf-8"><title>Cheap Txyz Visual Report</title><style>body{font:15px system-ui;margin:2rem;background:#f5f6f8;color:#18212b}header,article{background:white;padding:1rem;margin:1rem auto;max-width:1100px;border-radius:10px}img{width:100%;margin:.4rem 0}code{background:#eef;padding:.2rem}</style><header><h1>Official SAM3D → frozen Cheap Txyz</h1><p>Red=Official, blue=Corrected. Camera B is held out. Residual maps share 0–100 mm scale. Use each 3D link to rotate, zoom and toggle traces.</p><img src="TXYZ_DISTRIBUTION.png"></header>'''+''.join(cards)
(p/'CHEAP_TXYZ_VISUAL_REPORT_V1.html').write_text(doc,encoding='utf-8')
