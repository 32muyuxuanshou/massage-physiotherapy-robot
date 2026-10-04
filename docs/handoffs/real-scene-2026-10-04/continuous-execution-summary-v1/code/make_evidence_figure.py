"""Three separate measurement contracts; all bars read original result JSON."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent

def main():
    inputs={name:BASE/name/'RESULTS.json' for name in ['back-reference-extraction-v1','prone-reference-mesh-interface-v1','bounded-reference-correspondence-v1']}
    data={name:json.loads(path.read_text(encoding='utf-8-sig')) for name,path in inputs.items()}
    extraction=data['back-reference-extraction-v1']['methods']
    interface=data['prone-reference-mesh-interface-v1']['stability']['consumed_test_role']['GROOVE_DP']
    correspondence=data['bounded-reference-correspondence-v1']['consumed_validation']['TANGENTIAL_SHIFT']
    panels=[
        dict(title='1. Complete real XYZ scans\n30 scans / author surface line',labels=['Boundary','Symmetry','Groove'],
             first=[extraction[k]['median_of_scan_median_xyz_mm'] for k in ['BOUNDARY_CENTER','SYMMETRY_DP','GROOVE_DP']],
             second=[extraction[k]['median_of_scan_p95_xyz_mm'] for k in ['BOUNDARY_CENTER','SYMMETRY_DP','GROOVE_DP']],
             legends=['Scan median, then median','Scan P95, then median'],ylabel='Same-Y reference difference / mm'),
        dict(title='2. Clothed prone interface\n12/16 complete consumed test roles',labels=['Rigid','Rigid+D'],
             first=[interface[k]['projection_median_mm'] for k in ['Rigid','RigidD']],
             second=[interface[k]['bound_span_median_mm'] for k in ['Rigid','RigidD']],
             legends=['Query-to-mesh distance','Bound-point cross-split span'],ylabel='Two distinct measurements / mm'),
        dict(title='3. Controlled tangent mismatch\n16 consumed sources / fixed 5mm noise',labels=['Fixed topology','RBF + noise','Convex4 + noise'],
             first=[correspondence[k]['median_mm'] for k in ['FIXED','RBF_NOISY5','CONVEX4_NOISY5']],
             second=[correspondence[k]['p95_mm'] for k in ['FIXED','RBF_NOISY5','CONVEX4_NOISY5']],
             legends=['Source median, then median','Source P95, then median'],ylabel='Unprovided ENG probe difference / mm')]
    fig,axes=plt.subplots(1,3,figsize=(16,5.6))
    for ax,panel in zip(axes,panels):
        x=np.arange(len(panel['labels']));a=ax.bar(x-.18,panel['first'],.36,color='#3274A1',label=panel['legends'][0])
        b=ax.bar(x+.18,panel['second'],.36,color='#E1812C',label=panel['legends'][1])
        ax.bar_label(a,fmt='%.2f',padding=3,fontsize=9);ax.bar_label(b,fmt='%.2f',padding=3,fontsize=9)
        ax.set_xticks(x,panel['labels']);ax.set_title(panel['title'],fontsize=11);ax.set_ylabel(panel['ylabel'])
        ax.set_ylim(0,max(panel['first']+panel['second'])*1.35);ax.legend(fontsize=8,loc='upper right');ax.grid(axis='y',alpha=.2)
    fig.suptitle('Back-reference engineering evidence: improved fit does not establish anatomical accuracy',fontsize=13)
    fig.text(.5,.015,'Separate contracts: non-prone XYZ / approximate-camera clothed prone / program-generated truth. Do not combine as acupoint accuracy.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.95));fig.savefig(ROOT/'EVIDENCE_OVERVIEW.png',dpi=140);plt.close(fig)
    record=dict(source_files=[dict(package=name,path=str(p.relative_to(BASE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in inputs.items()],
        panels=panels,recomputed_scientific_predictions=False,clinical_accuracy=False)
    (ROOT/'EVIDENCE_FIGURE_DATA.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
    print('EVIDENCE_FIGURE_SAVED_FROM_THREE_RESULT_JSONS')

if __name__=='__main__':main()
