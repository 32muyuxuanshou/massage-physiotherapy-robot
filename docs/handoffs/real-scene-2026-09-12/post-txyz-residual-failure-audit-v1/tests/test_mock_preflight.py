import json,tempfile,unittest
from pathlib import Path
from post_txyz_audit.preflight import run
class TestMockPreflight(unittest.TestCase):
    def test_complete_mock_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report=root/'v/formal/report';report.mkdir(parents=True)
            for name in ('system_summary_v2.json','per_frame_results.json','failure_cases_v2.json','server_visualization_manifest_v2.json'):(report/name).write_text('{}')
            (report/'final_decision_v2.json').write_text(json.dumps({'gate':'PASS_BEHAVE_CHEAP_TXYZ_GENERALIZATION_V2'}))
            rows=[]
            for subject in ('Sub03','Sub04','Sub05','Sub06','Sub07'):
                for sequence in range(3):
                    for frame in range(3):rows.append({'subject':subject,'sequence':('Date06_Sub07_stool_sit' if subject=='Sub07' and sequence==0 else f'{subject}_s{sequence}'),'frame':('t0038.000' if subject=='Sub07' and sequence==0 and frame==0 else f't{frame:04d}.000'),'cameras':['K0','K1','K2','K3']})
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'rows':rows}));schema=root/'schema.json';schema.write_text(json.dumps({'features':[{'name':'x','description':'x','unit':'mm','source_camera':'K0','source_file':'x','deployment_available':True,'uses_heldout_information':False,'requires_replay':False,'availability_status':'AVAILABLE_NOW'}]}))
            self.assertEqual(run(root/'v',schema,manifest)['status'],'PURE_CODE_POST_TXYZ_AUDIT_PREFLIGHT_PASS')
