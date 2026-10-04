"""All qualified marker/line packets on their original scans, never fitted."""
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audit_references import ROOT,SOURCE,PREVIOUS,read,write,sha,load_reader

def main():
    scans={r['scan_id']:r for r in csv.DictReader((PREVIOUS/'SCAN_REFERENCE_BINDING.csv').open())}
    reader=load_reader();out=ROOT/'figures';out.mkdir(exist_ok=True);visuals=[]
    for packet in read(ROOT/'REFERENCE_PACKET_MANIFEST.json'):
        z=np.load(packet['path']);source=SOURCE/scans[packet['scan_id']]['path'];points,_=reader.read_ply(source)
        body=(points-z['origin_m'])@z['basis'];line=z['line_local_m'];markers=(z['markers_m']-z['origin_m'])@z['basis']
        sample=body[::max(1,int(np.ceil(len(body)/12000)))]*1000;line=line*1000;markers=markers*1000
        fig,axes=plt.subplots(1,3,figsize=(14,7))
        for ax,(x,y),title in zip(axes,[(0,1),(2,1),(0,2)],['Reference lateral / longitudinal','Reference normal / longitudinal','Reference lateral / normal']):
            ax.scatter(sample[:,x],sample[:,y],s=.4,color='gray',alpha=.3,rasterized=True)
            ax.plot(line[:,x],line[:,y],color='deepskyblue',lw=2,label='Source drawn surface line')
            ax.scatter(markers[:,x],markers[:,y],color='crimson',s=32,label='Provided selected markers')
            for i,m in enumerate(markers):ax.annotate('M'+str(i+1),(m[x],m[y]),fontsize=9)
            ax.set_title(title);ax.set_xlabel('mm');ax.set_ylabel('mm');ax.set_aspect('equal',adjustable='datalim')
            if y==1:ax.invert_yaxis()
        axes[0].legend(loc='best',fontsize=7)
        fig.suptitle(f"{packet['scan_id']} / {packet['candidate_id']} / original real scan\nSource order candidate only; NOT prone RGB-D, acupoint GT, or Mesh improvement")
        fig.tight_layout();path=out/(packet['candidate_id']+'.png');fig.savefig(path,dpi=130);plt.close(fig)
        visuals.append(dict(candidate_id=packet['candidate_id'],scan_id=packet['scan_id'],path=str(path),sha256=sha(path),
            point_packet_sha256=sha(packet['path']),scan_sha256=sha(source),visualization='point cloud in provided reference frame; orthographic geometric plots, not original camera/RGB overlays'))
    write(ROOT/'VISUALIZATION_MANIFEST.json',visuals)
    print('VISUALS_COMPLETE',len(visuals),flush=True)

if __name__=='__main__':main()
