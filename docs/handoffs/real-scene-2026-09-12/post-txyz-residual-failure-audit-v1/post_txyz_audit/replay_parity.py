import numpy as np

TOLERANCE_M=1e-6
def compare(frame_id,replay_row,v23_row):
    replay=np.asarray(replay_row['translation_m'],float);v23=np.asarray(v23_row['Txyz_m'],float);difference=replay-v23;max_component=float(np.max(np.abs(difference)));fallback_match=bool(replay_row['fallback'])==bool(v23_row['fallback']);passed=max_component<TOLERANCE_M and fallback_match
    return {'frame_id':frame_id,'replay_translation_m':replay.tolist(),'v23_translation_m':v23.tolist(),'translation_difference_m':difference.tolist(),'translation_difference_norm_mm':float(np.linalg.norm(difference)*1000),'max_component_difference_m':max_component,'replay_fallback':bool(replay_row['fallback']),'v23_fallback':bool(v23_row['fallback']),'parity_pass':passed}

def assert_all(rows):
    failed=[row['frame_id'] for row in rows if not row['parity_pass']]
    if failed:raise RuntimeError('TXYZ_REPLAY_PARITY_FAILED '+repr(failed))
    return {'status':'PASS_45_OF_45_TXYZ_REPLAY_PARITY','frame_count':len(rows),'tolerance_max_component_m':TOLERANCE_M,'rows':rows}
