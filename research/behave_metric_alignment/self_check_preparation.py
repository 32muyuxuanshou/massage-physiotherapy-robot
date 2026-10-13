"""Three normal-path checks; no model inference or scientific accuracy claims."""
import io,json,zipfile
from pathlib import Path
import numpy as np
from download_subset import unpack_member
from dataset_io import pinhole_input,fixed_indices
from summarize_benchmark import aggregate

payload=b'normal RGBD subset member '*1000
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('frame/depth.bin',payload)
with zipfile.ZipFile(b) as z:
    info=z.infolist()[0]
    recovered=unpack_member(b.getvalue(),0,dict(offset=info.header_offset,compressed=info.compress_size,
        method=info.compress_type,size=info.file_size,crc32=info.CRC,name=info.filename))
assert recovered==payload
rgb=np.full((32,32,3),128,np.uint8);depth=np.full((32,32),2000,np.uint16);depth[0,0]=0
mask=np.full((32,32),255,np.uint8);cam={'K':np.array([[30.,0,16],[0,30.,16],[0,0,1]]),'dist':np.zeros(5)}
image,d,m,bbox=pinhole_input(rgb,depth,mask,cam)
assert np.array_equal(image,rgb) and d[0,0]==0 and np.max(np.abs(d[1:]-2))<1e-6
assert np.array_equal(fixed_indices(10000,'a',2048),fixed_indices(10000,'a',2048))
rows=[]
for subject,seq,values in [('Sub03','Date03_Sub03_a',[10,30]),('Sub03','Date03_Sub03_b',[100]),('Sub04','Date03_Sub04_a',[200])]:
    for i,v in enumerate(values):rows.append({'subject':subject,'sequence':seq,'frame':str(i),
        'pve':{'pve_absolute_mm':v,'pve_centroid_centered_mm':v,'pa_pve_similarity_mm':v},
        'frame_surface_camera_equal_mean':{'median_mm':v,'p95_mm':v,'coverage_50mm':.5}})
result=aggregate(rows)
assert result['frame_equal_mean']['pve_absolute_mm']==85.0
assert result['sequence_then_subject_equal_mean']['pve_absolute_mm']==130.0
report={'status':'PASS_3_NORMAL_PATH_CHECKS','checks':['Coalesced ZIP decompression+CRC','Pinhole RGB/Z and deterministic indices','Frame vs sequence-subject aggregation'],
        'new_model_forward_verified':False,'scientific_benchmark_complete':False}
Path('reports').mkdir(exist_ok=True);Path('reports/SELF_CHECK_PREPARATION.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
