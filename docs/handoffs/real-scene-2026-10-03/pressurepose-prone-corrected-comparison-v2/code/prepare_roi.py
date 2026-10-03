"""Freeze conservative visible posterior RGB regions without examining fitted meshes."""
import hashlib, json
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[3]
RGB=PROJECT/'output/pressurepose_prone_review/preview/rgb'
POLYGONS={
 'S103':[[185,245],[263,241],[278,266],[269,315],[266,380],[159,386],[163,320],[169,275]],
 'S104':[[205,300],[247,300],[272,320],[274,353],[263,398],[261,413],[186,418],[183,389],[182,345],[185,320]],
 'S107':[[211,207],[239,209],[266,239],[281,286],[279,321],[285,339],[185,356],[168,293],[173,245],[191,222]],
 'S114':[[197,248],[267,249],[285,273],[274,320],[276,381],[191,387],[181,324],[180,276]],
 'S118':[[171,240],[219,241],[244,260],[244,291],[246,356],[159,357],[156,296],[157,261]],
 'S121':[[188,240],[238,242],[276,268],[280,307],[279,398],[165,399],[158,312],[162,266]],
 'S130':[[192,240],[241,240],[267,261],[268,293],[262,375],[178,385],[177,307],[168,265]],
 'S134':[[200,258],[243,255],[273,280],[277,316],[281,382],[190,388],[176,308],[181,282]],
 'S140':[[188,307],[237,304],[267,325],[265,364],[268,431],[174,437],[163,366],[163,332]],
 'S141':[[208,260],[252,260],[269,284],[270,320],[266,389],[183,394],[180,330],[181,284]],
 'S145':[[193,250],[235,244],[270,264],[274,300],[268,381],[175,386],[160,310],[163,279]],
 'S151':[[202,225],[249,224],[274,247],[281,291],[286,385],[177,397],[169,304],[167,264]],
 'S163':[[193,249],[241,258],[268,277],[262,318],[251,381],[167,380],[168,328],[165,275]],
 'S165':[[181,213],[219,214],[258,239],[267,309],[270,366],[254,374],[167,373],[149,307],[155,249]],
 'S170':[[195,217],[240,218],[271,245],[277,291],[280,366],[183,369],[169,302],[164,254]],
 'S179':[[200,246],[244,237],[280,254],[287,291],[302,366],[211,386],[187,320],[174,278]],
 'S184':[[175,226],[221,223],[254,247],[268,292],[270,371],[166,386],[155,315],[148,263]],
 'S187':[[202,273],[250,273],[275,294],[285,337],[282,426],[179,434],[177,349],[173,307]],
 'S188':[[192,215],[241,216],[272,238],[285,278],[281,383],[181,395],[162,306],[155,252]],
 'S196':[[200,246],[244,245],[267,270],[281,309],[271,369],[181,372],[174,308],[177,275]]
}

def main():
    entries=[]; dest=ROOT/'roi_review'; dest.mkdir(exist_ok=True)
    for subject, polygon in POLYGONS.items():
        src=RGB/f'{subject}_p_sel_prn.png'; im=Image.open(src).convert('RGB')
        entries.append(dict(subject=subject,polygon_xy_px=polygon,rgb_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),rgb_size=list(im.size),rgb_array_sha256=hashlib.sha256(np.asarray(im).tobytes()).hexdigest()))
        canvas=Image.new('RGB',(440,920),'white');canvas.paste(im,(0,40));draw=ImageDraw.Draw(canvas)
        draw.text((10,10),subject+' RGB-only posterior ROI (cyan)',fill='black')
        draw.line([(x,y+40) for x,y in polygon]+[(polygon[0][0],polygon[0][1]+40)],fill='#00ffff',width=3)
        canvas.save(dest/f'{subject}_roi.jpg',quality=91)
    pages=[]
    for i in range(0,len(entries),4):
        canvas=Image.new('RGB',(1760,920),'white')
        for j,e in enumerate(entries[i:i+4]): canvas.paste(Image.open(dest/f"{e['subject']}_roi.jpg"),(j*440,0))
        p=dest/f'roi_contact_{i//4+1:02d}.jpg';canvas.save(p,quality=92);pages.append(p.name)
    payload=dict(status='FROZEN_RGB_ONLY_ENGINEERING_ANNOTATION',medical_truth=False,
        source='Agent visual review of original RGB, before new model outputs',
        boundary='Conservative visible clothed posterior torso; excludes hair/head, neck, arms, belt/hips and legs',
        ambiguity='Not anatomical vertebral-level or naked-skin truth; boundary may exclude part of lower back',entries=entries)
    (ROOT/'POSTERIOR_RGB_ROI.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(subjects=len(entries),review_pages=pages)))

if __name__=='__main__': main()
