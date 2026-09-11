"""Frozen V2 subject-equal aggregation and decision gate."""
import argparse, collections, csv, json
from pathlib import Path
import numpy as np

CAMS = ("K1", "K2", "K3")
METRICS = ("median_mm", "p90_mm", "p95_mm", "coverage_50mm")

def med(values): return float(np.median(values))
def frame(row, kind, key): return med([row["cameras"][cam][kind][key] for cam in CAMS])
def equal(rows, kind, key):
    grouped = collections.defaultdict(list)
    for row in rows: grouped[row["spec"]["subject"]].append(frame(row, kind, key))
    per_subject = {subject: med(values) for subject, values in grouped.items()}
    return {"per_subject": per_subject, "overall_equal_weight_mean": float(np.mean(list(per_subject.values())))}
def write_csv(path, rows):
    if rows:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--results", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); rows = json.loads(args.results.read_text(encoding="utf-8")); args.out.mkdir(parents=True, exist_ok=True)
    aggregate = {kind: {key: equal(rows, kind, key) for key in METRICS} for kind in ("official", "txyz")}
    subjects = {subject: aggregate["txyz"]["median_mm"]["per_subject"][subject] < value for subject, value in aggregate["official"]["median_mm"]["per_subject"].items()}
    cameras = {}
    for cam in CAMS:
        cameras[cam] = {}
        for kind in ("official", "txyz"):
            grouped = collections.defaultdict(list)
            for row in rows: grouped[row["spec"]["subject"]].append(row["cameras"][cam][kind]["median_mm"])
            cameras[cam][kind] = float(np.mean([med(values) for values in grouped.values()]))
    flat = []
    for row in rows:
        for cam in CAMS:
            item = {"subject": row["spec"]["subject"], "sequence": row["spec"]["sequence"], "frame": row["spec"]["frame"], "camera": cam, "outcome": row["multicamera_outcome"]}
            for kind in ("official", "txyz"):
                for key in METRICS: item[f"{kind}_{key}"] = row["cameras"][cam][kind][key]
            item["delta_median_mm"] = item["txyz_median_mm"] - item["official_median_mm"]; flat.append(item)
    write_csv(args.out / "per_frame_per_camera_metrics.csv", flat)
    per_subject = []
    for subject in sorted(subjects):
        item = {"subject": subject, "median_improved": subjects[subject]}
        for kind in ("official", "txyz"):
            for key in METRICS: item[f"{kind}_{key}"] = aggregate[kind][key]["per_subject"][subject]
        per_subject.append(item)
    write_csv(args.out / "per_subject_metrics.csv", per_subject)
    write_csv(args.out / "per_camera_metrics.csv", [{"camera": cam, "official_median_mm": cameras[cam]["official"], "txyz_median_mm": cameras[cam]["txyz"], "improved": cameras[cam]["txyz"] < cameras[cam]["official"]} for cam in CAMS])
    outcomes = collections.Counter(row["multicamera_outcome"] for row in rows); low, high, failures, translations, rendered = [], [], [], [], []
    for row in rows:
        official, txyz = frame(row, "official", "median_mm"), frame(row, "txyz", "median_mm")
        item = {"subject": row["spec"]["subject"], "sequence": row["spec"]["sequence"], "frame": row["spec"]["frame"], "official_mm": official, "txyz_mm": txyz, "delta_mm": txyz-official, "outcome": row["multicamera_outcome"]}
        if official < 30: low.append(item)
        if official >= 60: high.append(item)
        if txyz >= official: failures.append(item)
        translations.append({"spec": row["spec"], **row.get("translation_only_qa", {})})
        for cam in CAMS:
            camera = row["cameras"][cam]
            rendered.append({"spec": row["spec"], "camera": cam,
                             **camera["rendered_depth_pinhole_undistorted_sensor"]})
    degraded = sum(item["delta_mm"] > 5 for item in low); degradation_rate = None if len(low) < 10 else degraded / len(low)
    official, txyz = aggregate["official"]["median_mm"]["overall_equal_weight_mean"], aggregate["txyz"]["median_mm"]["overall_equal_weight_mean"]
    official_p95, txyz_p95 = aggregate["official"]["p95_mm"]["overall_equal_weight_mean"], aggregate["txyz"]["p95_mm"]["overall_equal_weight_mean"]
    checks = {"median_improvement": (official-txyz)>=3 or (official-txyz)/official>=.10, "subjects_improved": sum(subjects.values())/len(subjects)>=.80, "cameras_improved": sum(cameras[cam]["txyz"]<cameras[cam]["official"] for cam in CAMS)>=2, "p95_not_worse_over_relative_5_percent": txyz_p95<=1.05*official_p95, "low_error_protection": len(low)<10 or degradation_rate<=.20}
    gate = "PASS_BEHAVE_CHEAP_TXYZ_GENERALIZATION_V2" if all(checks.values()) else ("PASS_POSITIVE_SIGNAL_BUT_INCONSISTENT" if checks["median_improvement"] else "FAIL_TXYZ_GENERALIZATION")
    contract = {"frame": "median across K1/K2/K3", "subject": "median across frozen frames", "subject_equal_overall": "arithmetic mean of five subject values", "p95_gate": "Txyz <= 1.05 * Official (relative 5%)", "low_high": "frame median across K1/K2/K3"}
    outliers=[]
    for row in rows:
        for cam in CAMS:
            for kind in ("official","txyz"):
                metric=row["cameras"][cam][kind]
                outliers.append({"spec":row["spec"],"camera":cam,"method":kind,
                                 "p99_mm":metric["p99_mm"],"max_mm":metric["max_mm"],
                                 "above_500mm_count":metric["above_500mm_count"],
                                 "above_500mm_ratio":metric["above_500mm_ratio"]})
    outputs = {"system_summary_v2.json": {"contract": contract, "aggregates": aggregate, "camera": cameras, "subjects_improved": subjects, "outcomes": outcomes}, "LOW_ERROR_PROTECTION_V2.json": {"official_threshold_mm":30,"meaningful_degradation_mm":5,"descriptive_only":len(low)<10,"count":len(low),"meaningfully_degraded":degraded,"rate":degradation_rate,"rows":low}, "HIGH_ERROR_RESCUE_V2.json":{"official_threshold_mm":60,"count":len(high),"improved":sum(item["delta_mm"]<0 for item in high),"rows":high}, "MULTICAMERA_FRAME_OUTCOME_V2.json":{"counts":outcomes,"rows":[{"spec":row["spec"],"outcome":row["multicamera_outcome"]} for row in rows]}, "TXYZ_TRANSLATION_ONLY_QA_V2.json":{"policy":"report all raw/applied corrections; no result filtering","rows":translations}, "BEHAVE_RENDERED_DEPTH_EVAL_V2.json":{"domain":"undistorted pinhole sensor depth/mask","rows":rendered}, "BEHAVE_DEPTH_OUTLIER_AUDIT_V2.json":{"metric":"point-to-triangle observed-point distance","threshold_mm":500,"policy":"report only; never filter or modify Txyz","rows":outliers}, "failure_cases_v2.json":{"selection":"all txyz >= official frame aggregates","rows":failures}, "final_decision_v2.json":{"gate":gate,"conditions":checks,"contract":contract}}
    for name, payload in outputs.items(): (args.out/name).write_text(json.dumps(payload, indent=2)+"\n", encoding="utf-8")

if __name__ == "__main__": main()
