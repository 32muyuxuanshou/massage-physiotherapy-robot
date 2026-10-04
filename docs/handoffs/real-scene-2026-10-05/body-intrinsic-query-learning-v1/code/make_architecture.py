"""Static diagram of the implemented branches, not a claim of clinical validation."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def main():
    fig,ax=plt.subplots(figsize=(14,7));ax.set_xlim(0,14);ax.set_ylim(0,7);ax.axis('off')
    def box(x,y,w,h,label,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.08',facecolor=color,edgecolor='#263238',linewidth=1.2))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=10)
    def arrow(a,b):ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#37474f',lw=1.4))
    box(.25,4.8,2.3,1.1,'Source template\nlocal XYZ + normals\ngiven engineering queries','#e3f2fd')
    box(.25,2.5,2.3,1.1,'Target observed patch\nlocal XYZ + normals\nall candidates','#e3f2fd')
    box(3.1,5.6,3,0.75,'Body coordinates + PointNet\nobserved quantiles / context','#fff3e0')
    box(3.1,4.4,3,0.75,'Local HKS + DiffusionNet\npoint-cloud spectral operators','#e8f5e9')
    box(3.1,3.1,3,0.75,'Body coordinates + PointNet\nshared source / target weights','#fff3e0')
    box(3.1,1.9,3,0.75,'Local HKS + DiffusionNet\nlocal training, author initialization','#e8f5e9')
    for a,b in [((2.55,5.4),(3.1,5.95)),((2.55,5.1),(3.1,4.8)),((2.55,3.15),(3.1,3.5)),((2.55,2.8),(3.1,2.3))]:arrow(a,b)
    box(6.6,4.8,2.4,.95,'Source descriptors\nquery selection','#ede7f6');box(6.6,2.5,2.4,.95,'Target descriptors\nall candidates','#ede7f6')
    for a,b in [((6.1,6),(6.6,5.45)),((6.1,4.8),(6.6,5.1)),((6.1,3.5),(6.6,3.15)),((6.1,2.3),(6.6,2.8))]:arrow(a,b)
    box(9.7,3.3,3.5,1.45,'Query-to-candidate matching\ncosine + paired MLP\nBODY / INTRINSIC / DUAL\n9 fixed training runs','#fce4ec')
    arrow((9,5.2),(9.7,4.35));arrow((9,3),(9.7,3.7))
    box(9.7,1.15,3.5,.85,'Retrieved observed indices\nindependent identity scoring\nMHR projection is a separate interface','#eceff1');arrow((11.45,3.3),(11.45,2.0))
    ax.text(7,6.75,'Implemented local body / intrinsic template-query learning',ha='center',fontsize=16,weight='bold')
    ax.text(7,.35,'Registered identity labels: training loss / evaluation only. No RGB fusion or medical ground truth in this stage.',ha='center',fontsize=10)
    fig.tight_layout();fig.savefig(Path(__file__).resolve().parents[1]/'MODEL_ARCHITECTURE.png',dpi=140);plt.close(fig)


if __name__=='__main__':main()
