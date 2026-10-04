"""Local pure/mock preflight; explicitly does not validate CUDA execution."""
import argparse,ast,hashlib,importlib.util,io,platform,sys,unittest
from pathlib import Path
from data_v2 import load_json,save_json,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    for path in sorted((root/'code').glob('*.py')):ast.parse(path.read_text(encoding='utf8'),filename=str(path))
    suite=unittest.defaultTestLoader.discover(str(root/'code'),pattern='test_*v2.py')
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    contract=load_json(root/'EXPERIMENT_CONTRACT.json');roi=load_json(root/'POSTERIOR_RGB_ROI.json')
    assert {r['subject'] for r in roi['entries']}==set(contract['subjects'])
    assert len(contract['subjects'])*len(contract['methods'])*len(contract['seeds'])==300
    # Source-snapshot algorithms and registration are checked by tests, not just syntax.
    record=dict(status='LOCAL_CODE_PREFLIGHT_PASS' if result.wasSuccessful() else 'FAILED',
        tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),log=log.getvalue(),
        python=sys.version,platform=platform.platform(),torch_installed=importlib.util.find_spec('torch') is not None,
        posterior_roi_count=len(roi['entries']),formal_expected_rows=300,formal_executed_rows=0,
        limits=['GPU SAM3D inference and O2 not executed by this preflight',
                'mock checks validate data flow, not model numerical accuracy',
                'server runtime assets and nonplanar camera QA on all dev subjects pending'])
    save_json(a.report,record);print(record['status'],record['tests_run'],'tests')
    if not result.wasSuccessful():print(log.getvalue());raise SystemExit(1)


if __name__=='__main__':main()
