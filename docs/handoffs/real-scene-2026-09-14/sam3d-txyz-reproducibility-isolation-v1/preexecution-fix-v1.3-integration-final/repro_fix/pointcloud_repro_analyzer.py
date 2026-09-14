FIELDS=('raw_depth_sha256','decoded_depth.sha256','decoded_depth.dtype','decoded_depth.shape','raw_mask_sha256','decoded_mask.sha256','decoded_mask.dtype','decoded_mask.shape','pointcloud_table_file_sha256','pointcloud_table.sha256','pointcloud_table.dtype','pointcloud_table.shape','points.sha256','points.dtype','points.shape','points.order')
def get(row,path):
 value=row
 for key in path.split('.'):value=value[key]
 return value
def analyze(runs):
 reference=runs[0]['rows'];by_ref={x['frame_id']:x for x in reference};first=None
 for run_index,run in enumerate(runs[1:],2):
  for row in run['rows']:
   base=by_ref[row['frame_id']]
   for field in FIELDS:
    if get(base,field)!=get(row,field):first={'run':run_index,'frame_id':row['frame_id'],'field':field,'reference':get(base,field),'observed':get(row,field)};break
   if first:break
  if first:break
 return {'status':'POINTCLOUD_REPRODUCIBILITY_PASS' if first is None else 'POINTCLOUD_RECONSTRUCTION_NONDETERMINISTIC','first_mismatch':first,'fresh_processes':len(runs),'checked_fields':list(FIELDS)}
