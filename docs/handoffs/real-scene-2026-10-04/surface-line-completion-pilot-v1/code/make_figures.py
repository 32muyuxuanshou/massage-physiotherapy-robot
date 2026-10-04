"""All six evaluation scans; visualizations read frozen predictions, never refit."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data_line import read,sha,write

def main(root):
    rows=read(root/'PREDICTION_MANIFEST.json');cases={r['candidate_id']:r for r in read(root/'DATA_MANIFEST.json')}
    freeze=read(root/'PREDICTION_FREEZE.json');assert sha(root/'PREDICTION_MANIFEST.json')==freeze['manifest_sha256']
    output=root/'figures';output.mkdir(exist_ok=True);manifest=[]
    colors={'BOUNDARY_CENTER':'cyan','SYMMETRY_DP':'magenta','GROOVE_DP':'yellow','NO_BLOCK_AUG':'red','BLOCK_AUG':'lime'}
    for candidate in sorted({r['candidate_id'] for r in rows}):
        with np.load(cases[candidate]['path']) as z:ys=z['ys_m'];target=z['target_x_m'];valid=z['target_row_valid']
        figure,axes=plt.subplots(1,4,figsize=(17,7),sharey=True)
        for ax,condition in zip(axes,['FULL','MISSING_0','MISSING_1','MISSING_2']):
            group=[r for r in rows if r['candidate_id']==candidate and r['condition']==condition]
            with np.load(group[0]['input_path']) as z:features=z['features'];xs=z['xs_m'];grid_y=z['ys_m'];mask=z['valid']
            ax.imshow(np.where(mask,features[0],np.nan),origin='lower',extent=[xs[0]*1000,xs[-1]*1000,grid_y[0]*1000,grid_y[-1]*1000],cmap='gray',aspect='equal')
            ax.plot(target[valid]*1000,ys[valid]*1000,'--',color='white',linewidth=2,label='Author line reference')
            failed=[]
            for row in group:
                if row['status']!='COMPLETE':failed.append(row['method']);continue
                assert sha(row['path'])==row['sha256']
                with np.load(row['path']) as z:xy=z['query_xy_m']
                label=row['method']+(f" seed{row['seed']}" if row['seed'] is not None else '')
                ax.plot(xy[:,0]*1000,xy[:,1]*1000,color=colors[row['method']],linewidth=1,alpha=.65,label=label)
            ax.set_title(condition+('\nFailed: '+', '.join(failed) if failed else ''));ax.set_xlabel('Native X / mm')
        axes[0].set_ylabel('Native Y / mm');axes[-1].legend(fontsize=6,loc='lower left')
        figure.suptitle(candidate+' / same six frozen source roles / author surface line, NOT acupoint GT')
        figure.tight_layout();path=output/(candidate+'.png');figure.savefig(path,dpi=120);plt.close(figure)
        manifest.append(dict(candidate_id=candidate,path=str(path),sha256=sha(path),conditions=4,predictions_recomputed=False))
    assert len(manifest)==6;write(root/'VISUALIZATION_MANIFEST.json',manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();main(args.root)
