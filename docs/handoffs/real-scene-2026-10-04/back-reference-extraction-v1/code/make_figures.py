"""All scans, all methods, no post-result example selection."""
import argparse, csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_extraction import PARENT, read, write, sha


def main(root):
    predictions = read(root / 'PREDICTION_MANIFEST.json')
    results = list(csv.DictReader((root / 'PER_SCAN_RESULTS.csv').open()))
    out = root / 'figures'; out.mkdir(exist_ok=True); manifest = []
    colors = dict(BOUNDARY_CENTER='orange', SYMMETRY_DP='limegreen', GROOVE_DP='magenta')
    for packet in read(PARENT / 'REFERENCE_PACKET_MANIFEST.json'):
        reference = np.load(packet['path'])['line_m']
        grid = np.load(root / 'grids' / (packet['candidate_id'] + '.npz'))
        curves = [r for r in predictions if r['candidate_id'] == packet['candidate_id']]
        fig, axes = plt.subplots(1, 3, figsize=(16, 7))
        masked = np.ma.array(grid['depth_m'], mask=~grid['valid'])
        axes[0].imshow(masked, origin='lower', extent=[grid['xs_m'][0]*1000, grid['xs_m'][-1]*1000,grid['ys_m'][0]*1000,grid['ys_m'][-1]*1000],cmap='gray',aspect='equal')
        axes[0].plot(reference[:,0]*1000,reference[:,1]*1000,color='deepskyblue',label='Author drawn line (evaluation only)',lw=2)
        axes[1].plot(reference[:,0]*1000,reference[:,1]*1000,color='deepskyblue',lw=2)
        axes[2].plot(reference[:,2]*1000,reference[:,1]*1000,color='deepskyblue',lw=2)
        for row in curves:
            if row['status'] != 'COMPLETE': continue
            curve=np.load(row['path'])['curve_m']; name=row['method']
            score=next(r for r in results if r['candidate_id']==packet['candidate_id'] and r['method']==name)
            label=f"{name}: {float(score['median_xyz_mm']):.1f} / {float(score['p95_xyz_mm']):.1f} mm"
            axes[0].plot(curve[:,0]*1000,curve[:,1]*1000,color=colors[name],label=label,lw=1.4)
            axes[1].plot(curve[:,0]*1000,curve[:,1]*1000,color=colors[name],lw=1.4)
            axes[2].plot(curve[:,2]*1000,curve[:,1]*1000,color=colors[name],lw=1.4)
        axes[0].set_title('Source XYZ depth display + curves');axes[1].set_title('Lateral correspondence');axes[2].set_title('Native depth profile')
        for ax in axes:
            ax.invert_yaxis(); ax.set_ylabel('Native longitudinal Y (mm)');ax.grid(alpha=.2)
        axes[0].set_xlabel('Native lateral X (mm)');axes[1].set_xlabel('Native lateral X (mm)');axes[2].set_xlabel('Native depth Z (mm)')
        axes[0].legend(fontsize=7,loc='upper left')
        fig.suptitle(f"{packet['scan_id']} / XYZ-only extraction / median-P95 on identical common points\nOrthographic native geometry, NOT RGB camera image; author line is not clinical acupoint GT")
        fig.tight_layout();path=out/(packet['candidate_id']+'.png');fig.savefig(path,dpi=120);plt.close(fig)
        manifest.append(dict(candidate_id=packet['candidate_id'],path=str(path),sha256=sha(path),methods=3))
        print('FIGURE',packet['scan_id'],flush=True)
    write(root/'VISUALIZATION_MANIFEST.json',manifest)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
