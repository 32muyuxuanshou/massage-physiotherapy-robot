import hashlib, json
from pathlib import Path

REQUIRED_REPORTS = ("final_decision_v2.json", "system_summary_v2.json", "per_frame_results.json", "failure_cases_v2.json", "server_visualization_manifest_v2.json")

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def snapshot(root):
    root=Path(root);report=root/"formal"/"report";items=[]
    for name in REQUIRED_REPORTS:
        path=report/name
        if not path.is_file():raise FileNotFoundError(path)
        items.append({"path":str(path),"bytes":path.stat().st_size,"sha256":sha256(path)})
    return items

def snapshot_tree(root):
    root=Path(root)
    return [{"path":path.relative_to(root).as_posix(),"bytes":path.stat().st_size,"sha256":sha256(path)} for path in sorted(p for p in root.rglob('*') if p.is_file())]

def assert_tree_unchanged(root,before):
    if snapshot_tree(root)!=before:raise RuntimeError("READ_ONLY_V23_TREE_VIOLATION")

def assert_unchanged(before):
    after=[{"path":item["path"],"bytes":Path(item["path"]).stat().st_size,"sha256":sha256(item["path"])} for item in before]
    if after!=before:raise RuntimeError("READ_ONLY_V23_VIOLATION")
