from .sam_repro_analyzer import compare_arrays
def compare_order_runs(runs):
 names=list(runs);pairs=[]
 for i,a in enumerate(names):
  for b in names[i+1:]:
   for fid in sorted(set(runs[a])&set(runs[b])):
    left,right=runs[a][fid],runs[b][fid];same_input=left['prepared_tensor_hash']==right['prepared_tensor_hash'] and left['cam_int_hash']==right['cam_int_hash'];same_model=left['model_state_hash']==right['model_state_hash'];drift=compare_arrays(left['arrays'],right['arrays']);different=drift['vertices']['max_mm']>0 or drift['anchors']['max_mm']>0 or drift['cam_t']['norm_mm']>0
    status='MODEL_STATE_MUTATION' if not same_model else 'FRAME_ORDER_DEPENDENCE' if same_input and different else 'NO_ORDER_DEPENDENCE';pairs.append({'frame_id':fid,'pair':[a,b],'status':status,'drift':drift})
 return {'comparisons':pairs,'status':'FRAME_ORDER_DEPENDENCE' if any(x['status']=='FRAME_ORDER_DEPENDENCE' for x in pairs) else 'MODEL_STATE_MUTATION' if any(x['status']=='MODEL_STATE_MUTATION' for x in pairs) else 'PASS_NO_FRAME_ORDER_DEPENDENCE'}
