TRACE_FIELDS=('nearest','distances','keep','retained_residual','step')
def signature(run):
 values=[('translation',run['translation']['sha256'])]
 for item in run['trace']:
  for field in TRACE_FIELDS:values.append((f"iteration_{item['iteration']}.{field}",item[field]['sha256']))
 return values
def analyze_runs(runs):
 reference=signature(runs[0]);first=None
 for run_index,run in enumerate(runs[1:],2):
  for (name,a),(_,b) in zip(reference,signature(run)):
   if a!=b:first={'run':run_index,'object':name,'run_a_hash':a,'run_b_hash':b};break
  if first:break
 return {'all_equal':first is None,'first_divergence':first,'runs':len(runs)}
