"""Decisions from actual inspection of all 15 original K0 contact sheets."""
from common import ROOT,read,write,sha

# B: a central clothed posterior patch is clearly visible. N includes front,
# oblique/ambiguous, carried-object occlusion and blurred views. No model scores.
B={23,24,25,26,29,39,41,42,48,49,53,54,55,56,57,58,59,
   81,83,85,86,89,90,91,92,106,108,109,116,119,
   121,130,133,137,138,140,146,148,149,153,157,158,
   160,161,162,163,164,166,167,168,171,175,177,178,
   181,186,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,
   220,221,222,227,228,237,239,261,276,277,278,279,282,295,298}

def main():
    out=ROOT/'b_qualification';inv=read(out/'CANDIDATE_INVENTORY.json')
    rows=[dict(**f,code='B' if f['candidate_index'] in B else 'N',
        reason='CLEAR_CLOTHED_POSTERIOR_PATCH' if f['candidate_index'] in B else 'NO_CLEAR_CENTRAL_BACK_FRONT_OBLIQUE_OBJECT_OR_BLUR',
        reviewer='Codex original K0 RGB visual inspection; no medical localization') for f in inv['frames']]
    write(out/'K0_VISUAL_REVIEW.json',dict(status='ALL_300_K0_CONTACTS_INSPECTED',rows=rows,
        model_outputs_used=0,clear_posterior_candidates=len(B),
        contact_sources=[dict(path=str(p),sha256=sha(p)) for p in sorted((out/'private_images').glob('*_K0.jpg'))]))
    print('K0_REVIEW',len(rows),len(B),flush=True)

if __name__=='__main__':main()
