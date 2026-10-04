"""Post-only diagnostic: selected registration markers are not the drawn line."""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audit_references import ROOT,read,write,sha

def nearest_polyline(points,line):
    a=line[:-1];d=np.diff(line,axis=0);den=np.einsum('ij,ij->i',d,d)
    valid=den>0;a=a[valid];d=d[valid];den=den[valid];assert len(a)>0
    closest=[];distances=[]
    for p in points:
        t=np.clip(np.einsum('ij,ij->i',p-a,d)/den,0,1)
        q=a+t[:,None]*d;ds=np.linalg.norm(q-p,axis=1);k=ds.argmin()
        closest.append(q[k]);distances.append(ds[k])
    return np.asarray(distances),np.asarray(closest)

def main():
    rows=[];before=[]
    for r in read(ROOT/'REFERENCE_PACKET_MANIFEST.json'):
        p=ROOT/'reference_packets'/(r['candidate_id']+'.npz');before.append((p,sha(p)));z=np.load(p)
        distance,nearest=nearest_polyline(z['markers_m'],z['line_m']);local=z['line_local_m']
        rows.append(dict(candidate_id=r['candidate_id'],scan_id=r['scan_id'],marker_to_continuous_drawn_line_mm=(distance*1000).tolist(),
            marker_axis_to_drawn_line_lateral_median_mm=float(np.median(np.abs(local[:,0]))*1000),
            marker_axis_to_drawn_line_signed_lateral_median_mm=float(np.median(local[:,0])*1000),
            first_two_marker_to_drawn_line_median_mm=float(np.median(distance[:2])*1000),
            line_endpoint_to_marker1_mm=float(np.linalg.norm(z['line_m'][0]-z['markers_m'][0])*1000),
            line_endpoint_to_marker2_mm=float(np.linalg.norm(z['line_m'][-1]-z['markers_m'][1])*1000),
            interpretation='Geometric discrepancy between registration markers and source drawn line, not clinical localization error',
            clinical_error=False,selection_changed=False))
    values=np.asarray([r['first_two_marker_to_drawn_line_median_mm'] for r in rows])
    lateral=np.asarray([r['marker_axis_to_drawn_line_lateral_median_mm'] for r in rows])
    summary=dict(marker1_to_line_median_mm=float(np.median([r['marker_to_continuous_drawn_line_mm'][0] for r in rows])),
        marker2_to_line_median_mm=float(np.median([r['marker_to_continuous_drawn_line_mm'][1] for r in rows])),
        marker12_to_line_per_packet_median_min_mm=float(values.min()),marker12_to_line_per_packet_median_mm=float(np.median(values)),
        marker12_to_line_per_packet_median_max_mm=float(values.max()),marker_axis_lateral_deviation_median_mm=float(np.median(lateral)))
    for p,h in before:assert sha(p)==h
    write(ROOT/'MARKER_LINE_CONSISTENCY_AUDIT.json',dict(status='COMPLETE',post_execution_diagnostic=True,packet_count=len(rows),
        rows=rows,summary=summary,all_packets_unchanged=True,no_threshold_selection_or_algorithm_change=True,
        anatomy_adjudication='Hold: named registration marker positions must not be treated as verified posterior midline or spinous processes',
        script_sha256=sha(__file__)))
    fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(rows))
    ax.plot(x,[r['marker_to_continuous_drawn_line_mm'][0] for r in rows],'o-',label='M1 -> source drawn polyline')
    ax.plot(x,[r['marker_to_continuous_drawn_line_mm'][1] for r in rows],'o-',label='M2 -> source drawn polyline')
    ax.plot(x,lateral,'o-',label='Source line lateral displacement from M1-M2 axis')
    ax.set_xticks(x,[r['scan_id'] for r in rows],rotation=90,fontsize=7);ax.set_ylabel('Geometric discrepancy (mm)');ax.legend(fontsize=8)
    ax.set_title('All 30 real reference packets: registration markers and drawn line are different references\nNot acupoint accuracy, not camera calibration error')
    fig.tight_layout();p=ROOT/'figures/MARKER_LINE_ALL_30.png';fig.savefig(p,dpi=140);plt.close(fig)
    print(summary,flush=True)

if __name__=='__main__':main()
