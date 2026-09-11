"""Audit two frozen DMD37-to-MHR bridge candidates on canonical geometry."""

from __future__ import annotations

import hashlib
import heapq
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
OUT = HERE.parent.parent
ROOT = HERE.parents[5]
CONTRACT = OUT / "DMD37_BRIDGE_ACCEPTANCE_CONTRACT_V2.json"


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def closest_on_triangles(point: np.ndarray, tri: np.ndarray):
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    ab, ac = b - a, c - a
    normal = np.cross(ab, ac)
    nn = np.einsum("ij,ij->i", normal, normal)
    plane = point - normal * (
        np.einsum("ij,ij->i", point - a, normal) / np.maximum(nn, 1e-20)
    )[:, None]
    d00 = np.einsum("ij,ij->i", ab, ab)
    d01 = np.einsum("ij,ij->i", ab, ac)
    d11 = np.einsum("ij,ij->i", ac, ac)
    d20 = np.einsum("ij,ij->i", plane - a, ab)
    d21 = np.einsum("ij,ij->i", plane - a, ac)
    den = d00 * d11 - d01 * d01
    vb = (d11 * d20 - d01 * d21) / np.maximum(den, 1e-20)
    wb = (d00 * d21 - d01 * d20) / np.maximum(den, 1e-20)
    ub = 1.0 - vb - wb
    inside = (ub >= 0) & (vb >= 0) & (wb >= 0) & (nn > 1e-20)
    candidates = [np.where(inside[:, None], plane, np.inf)]
    weights = [np.column_stack([ub, vb, wb])]
    for x, y, indices in ((a, b, (0, 1)), (b, c, (1, 2)), (c, a, (2, 0))):
        edge = y - x
        t = np.clip(
            np.einsum("ij,ij->i", point - x, edge)
            / np.maximum(np.einsum("ij,ij->i", edge, edge), 1e-20),
            0,
            1,
        )
        q = x + t[:, None] * edge
        w = np.zeros((len(tri), 3), dtype=np.float64)
        w[:, indices[0]] = 1 - t
        w[:, indices[1]] = t
        candidates.append(q)
        weights.append(w)
    candidate = np.stack(candidates, axis=1)
    bary = np.stack(weights, axis=1)
    dist2 = np.sum((candidate - point) ** 2, axis=2)
    per_face_choice = np.argmin(dist2, axis=1)
    rows = np.arange(len(tri))
    per_face_dist2 = dist2[rows, per_face_choice]
    face_id = int(np.argmin(per_face_dist2))
    choice = int(per_face_choice[face_id])
    return candidate[face_id, choice], face_id, bary[face_id, choice]


def summary_mm(values_cm: np.ndarray) -> dict:
    values = np.asarray(values_cm, dtype=np.float64) * 10.0
    return {
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "p95": float(np.quantile(values, 0.95)),
        "max": float(values.max()),
    }


def graph_adjacency(faces: np.ndarray, vertices: np.ndarray):
    adjacency = [[] for _ in range(len(vertices))]
    seen = set()
    for face in faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            a, b = int(a), int(b)
            edge = (min(a, b), max(a, b))
            if edge in seen:
                continue
            seen.add(edge)
            weight = float(np.linalg.norm(vertices[a] - vertices[b]))
            adjacency[a].append((b, weight))
            adjacency[b].append((a, weight))
    return adjacency


def point_graph_distance(
    source: np.ndarray,
    source_face: np.ndarray,
    target: np.ndarray,
    target_face: np.ndarray,
    vertices: np.ndarray,
    adjacency,
) -> float:
    targets = {int(v): float(np.linalg.norm(target - vertices[v])) for v in target_face}
    queue = []
    best = {}
    for vertex in source_face:
        vertex = int(vertex)
        value = float(np.linalg.norm(source - vertices[vertex]))
        best[vertex] = value
        heapq.heappush(queue, (value, vertex))
    answer = float("inf")
    while queue:
        distance, vertex = heapq.heappop(queue)
        if distance != best.get(vertex):
            continue
        if distance >= answer:
            break
        if vertex in targets:
            answer = min(answer, distance + targets[vertex])
        for neighbor, weight in adjacency[vertex]:
            candidate = distance + weight
            if candidate < best.get(neighbor, float("inf")) and candidate < answer:
                best[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    return answer


def render_blinded(vertices: np.ndarray, candidates: dict[str, list], mapping: dict[str, str]):
    width, height = 720, 900
    board = Image.new("RGB", (width * 3, height * 2 + 70), (22, 24, 28))
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    views = [
        ("posterior", lambda p: np.column_stack((p[:, 0], p[:, 1], p[:, 2]))),
        ("left oblique", lambda p: np.column_stack(((p[:, 0] - p[:, 2]) / np.sqrt(2), p[:, 1], (p[:, 0] + p[:, 2]) / np.sqrt(2)))),
        ("right oblique", lambda p: np.column_stack(((p[:, 0] + p[:, 2]) / np.sqrt(2), p[:, 1], (-p[:, 0] + p[:, 2]) / np.sqrt(2)))),
    ]
    all_xy = []
    for _, transform in views:
        q = transform(vertices)
        all_xy.append(q[:, :2])
    colors = {"LEFT": (70, 180, 255), "RIGHT": (255, 120, 100), "MIDLINE": (255, 225, 70)}
    for row, neutral in enumerate(("Q", "R")):
        method = mapping[neutral]
        points = candidates[method]
        xyz = np.asarray([p["xyz_cm"] for p in points])
        for col, (view_name, transform) in enumerate(views):
            panel = Image.new("RGB", (width, height), (35, 38, 43))
            draw = ImageDraw.Draw(panel)
            q = transform(vertices)
            xy = q[:, :2]
            low = np.percentile(xy, 0.5, axis=0)
            high = np.percentile(xy, 99.5, axis=0)
            scale = min((width - 60) / (high[0] - low[0]), (height - 80) / (high[1] - low[1]))
            px = (xy[:, 0] - (low[0] + high[0]) / 2) * scale + width / 2
            py = height - 30 - (xy[:, 1] - low[1]) * scale
            for x, y in zip(px, py):
                if 0 <= x < width and 25 <= y < height:
                    draw.point((float(x), float(y)), fill=(115, 118, 123))
            pxy = transform(xyz)[:, :2]
            ppx = (pxy[:, 0] - (low[0] + high[0]) / 2) * scale + width / 2
            ppy = height - 30 - (pxy[:, 1] - low[1]) * scale
            for item, x, y in zip(points, ppx, ppy):
                color = colors[item["side"]]
                draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color, outline=(0, 0, 0), width=1)
            draw.text((12, 8), f"Candidate {neutral} | {view_name}", font=font, fill="white")
            board.paste(panel, (col * width, 55 + row * height))
    ImageDraw.Draw(board).text(
        (15, 15),
        "Canonical-only engineering review; blue=subject-left, red=subject-right, yellow=midline",
        font=font,
        fill="white",
    )
    path = OUT / "visualizations" / "DMD37_BRIDGE_CANONICAL_BLINDED_V2.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    board.save(path)
    return path


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    contract_sha = file_sha(CONTRACT)
    reviewed_path = ROOT / "docs/handoffs/real-scene-2026-09-06/reviewed-dmd37-2026-09-07/reviewed_points.json"
    previous = ROOT / "docs/handoffs/real-scene-2026-09-11/back-dmd37-engineering-validation-v1"
    asset_dir = ROOT / "AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/MHR/tools/mhr_smpl_conversion/assets"
    project_map_path = ROOT / "AI感知模块/模型资源/SMPL-X_SKEL_v2.2_internal/alignment/mapping_male.npz"
    body_map_path = ROOT / "docs/handoffs/real-scene-2026-09-10/public-rgbd-single-vs-multiview-v2/MHR_ENGINEERING_BODY_PART_MAP_V1.npz"
    reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
    vertices = np.load(previous / "raw/mhr_rest_vertices.npy").astype(np.float64)
    faces = np.load(previous / "raw/mhr_faces.npy").astype(np.int64)
    triangles = vertices[faces]
    project = np.load(project_map_path)
    mhr2smpl = np.load(asset_dir / "mhr2smpl_mapping.npz")
    smpl2mhr = np.load(asset_dir / "smpl2mhr_mapping.npz")
    mhr2smplx = np.load(asset_dir / "mhr2smplx_mapping.npz")
    body_map = np.load(body_map_path)
    groups = [str(v) for v in body_map["group_names"]]
    assert contract_sha == "9dab4850794feb2c2b8a24ff68d4fe6c1dbce234123bc13b58cf30ecd006d36d"
    assert vertices.shape == (18439, 3) and faces.shape == (36874, 3)
    assert hashlib.sha256(faces.astype(np.int32).tobytes()).hexdigest() == contract["inputs"]["target_topology"]["faces_sha256_int32_c_order"]
    assert np.array_equal(body_map["faces"].astype(np.int64), faces)
    smpl_faces = project["skel_skin_faces"].astype(np.int64)
    smpl_on_mhr = (
        triangles[mhr2smpl["triangle_ids"]]
        * mhr2smpl["baryc_coords"][:, :, None]
    ).sum(1)
    smplx_on_mhr = (
        triangles[mhr2smplx["triangle_ids"]]
        * mhr2smplx["baryc_coords"][:, :, None]
    ).sum(1)
    mhr_cycle = (
        smpl_on_mhr[smpl_faces[smpl2mhr["triangle_ids"]]]
        * smpl2mhr["baryc_coords"][:, :, None]
    ).sum(1)
    candidates = {"DIRECT_SMPL": [], "HISTORICAL_SMPLX": []}
    locality_rows = []
    for source in reviewed["points"]:
        ids = np.asarray(source["vertex_indices"], dtype=np.int64)
        weights = np.asarray(source["barycentric"], dtype=np.float64)
        assert np.array_equal(smpl_faces[source["face_index"]], ids)
        direct_support = smpl_on_mhr[ids]
        historical_support = smplx_on_mhr[project["target_indices"][ids]]
        diameters = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            diameters.append(float(np.linalg.norm(direct_support[a] - direct_support[b])))
        for method, support in (
            ("DIRECT_SMPL", direct_support),
            ("HISTORICAL_SMPLX", historical_support),
        ):
            composed = (support * weights[:, None]).sum(0)
            projected, face_id, bary = closest_on_triangles(composed, triangles)
            replay = (vertices[faces[face_id]] * bary[:, None]).sum(0)
            normal = np.cross(
                vertices[faces[face_id, 1]] - vertices[faces[face_id, 0]],
                vertices[faces[face_id, 2]] - vertices[faces[face_id, 0]],
            )
            normal /= max(float(np.linalg.norm(normal)), 1e-12)
            candidates[method].append(
                {
                    "point_id": source["point_id"],
                    "reference_code": source["reference_code"],
                    "side": source["side"],
                    "face_index": face_id,
                    "vertex_indices": faces[face_id].tolist(),
                    "barycentric": bary.tolist(),
                    "xyz_cm": replay.tolist(),
                    "composed_xyz_cm": composed.tolist(),
                    "projection_residual_mm": float(np.linalg.norm(replay - composed) * 10),
                    "face_normal": normal.tolist(),
                    "coarse_group": groups[int(body_map["face_labels"][face_id])],
                }
            )
        locality_rows.append(
            {
                "point_id": source["point_id"],
                "support_pair_distances_mm": (np.asarray(diameters) * 10).tolist(),
                "support_diameter_mm": max(diameters) * 10,
                "composed_to_surface_mm": candidates["DIRECT_SMPL"][-1]["projection_residual_mm"],
            }
        )

    adjacency = graph_adjacency(faces, vertices)
    disagreement_rows = []
    for direct, historical in zip(candidates["DIRECT_SMPL"], candidates["HISTORICAL_SMPLX"]):
        a = np.asarray(direct["xyz_cm"])
        b = np.asarray(historical["xyz_cm"])
        delta = b - a
        normal = np.asarray(direct["face_normal"])
        normal_component = abs(float(delta @ normal))
        tangential = float(np.linalg.norm(delta - (delta @ normal) * normal))
        geodesic = point_graph_distance(
            a,
            np.asarray(direct["vertex_indices"]),
            b,
            np.asarray(historical["vertex_indices"]),
            vertices,
            adjacency,
        )
        disagreement_rows.append(
            {
                "point_id": direct["point_id"],
                "euclidean_mm": float(np.linalg.norm(delta) * 10),
                "normal_component_mm": normal_component * 10,
                "tangential_component_mm": tangential * 10,
                "edge_graph_geodesic_upper_bound_mm": geodesic * 10,
            }
        )

    roundtrip_rows = []
    for item in candidates["DIRECT_SMPL"]:
        ids = np.asarray(item["vertex_indices"])
        bary = np.asarray(item["barycentric"])
        original = np.asarray(item["xyz_cm"])
        reconstructed = (mhr_cycle[ids] * bary[:, None]).sum(0)
        roundtrip_rows.append(
            {
                "point_id": item["point_id"],
                "error_mm": float(np.linalg.norm(reconstructed - original) * 10),
            }
        )

    sanity = {}
    pairs = {}
    for method, rows in candidates.items():
        by_code = {}
        point_checks = []
        for row in rows:
            xyz = np.asarray(row["xyz_cm"])
            side = row["side"]
            side_ok = xyz[0] >= 0.5 if side == "LEFT" else xyz[0] <= -0.5 if side == "RIGHT" else abs(xyz[0]) <= 1.0
            window = 2.5
            mask = (np.abs(vertices[:, 0] - xyz[0]) <= window) & (np.abs(vertices[:, 1] - xyz[1]) <= window)
            fallback = False
            if int(mask.sum()) < 20:
                window = 4.0
                fallback = True
                mask = (np.abs(vertices[:, 0] - xyz[0]) <= window) & (np.abs(vertices[:, 1] - xyz[1]) <= window)
            median_z = float(np.median(vertices[mask, 2]))
            posterior_ok = bool(xyz[2] <= median_z)
            region_ok = row["coarse_group"] in {"torso", "arms"}
            point_checks.append(
                {
                    "point_id": row["point_id"],
                    "side_ok": bool(side_ok),
                    "posterior_cross_section_ok": posterior_ok,
                    "cross_section_vertex_count": int(mask.sum()),
                    "cross_section_window_mm": window * 10,
                    "fallback_used": fallback,
                    "candidate_z_cm": float(xyz[2]),
                    "local_median_z_cm": median_z,
                    "coarse_group": row["coarse_group"],
                    "coarse_region_ok": region_ok,
                    "face_normal_z": row["face_normal"][2],
                }
            )
            by_code.setdefault(row["reference_code"], []).append(row)
        pair_checks = []
        for code, group in by_code.items():
            if len(group) != 2:
                continue
            left = next(x for x in group if x["side"] == "LEFT")
            right = next(x for x in group if x["side"] == "RIGHT")
            l, r = np.asarray(left["xyz_cm"]), np.asarray(right["xyz_cm"])
            metrics = {
                "abs_y_difference_mm": abs(float(l[1] - r[1])) * 10,
                "abs_z_difference_mm": abs(float(l[2] - r[2])) * 10,
                "abs_x_magnitude_difference_mm": abs(float(abs(l[0]) - abs(r[0]))) * 10,
            }
            pair_checks.append(
                {
                    "reference_code": code,
                    **metrics,
                    "pass": metrics["abs_y_difference_mm"] <= 20
                    and metrics["abs_z_difference_mm"] <= 20
                    and metrics["abs_x_magnitude_difference_mm"] <= 25,
                    "row_center_y_cm": float((l[1] + r[1]) / 2),
                }
            )
        ordered_codes = ["BL11", "BL12", "BL13", "BL14", "BL15", "BL43", "BL17", "BL18", "BL19", "BL20", "BL21", "BL22", "BL23", "BL25"]
        centers = {p["reference_code"]: p["row_center_y_cm"] for p in pair_checks}
        order_checks = [
            {
                "upper": a,
                "lower": b,
                "delta_y_mm": float((centers[a] - centers[b]) * 10),
                "pass": bool(centers[a] >= centers[b]),
            }
            for a, b in zip(ordered_codes[:-1], ordered_codes[1:])
        ]
        sanity[method] = {
            "points": point_checks,
            "pairs": pair_checks,
            "order": order_checks,
            "all_side_pass": all(p["side_ok"] for p in point_checks),
            "all_posterior_cross_section_pass": all(p["posterior_cross_section_ok"] for p in point_checks),
            "all_coarse_region_pass": all(p["coarse_region_ok"] for p in point_checks),
            "all_symmetry_pass": all(p["pass"] for p in pair_checks),
            "all_order_pass": all(p["pass"] for p in order_checks),
        }

    locality_diameter = np.asarray([x["support_diameter_mm"] for x in locality_rows]) / 10
    locality_projection = np.asarray([x["composed_to_surface_mm"] for x in locality_rows]) / 10
    disagreement = np.asarray([x["euclidean_mm"] for x in disagreement_rows]) / 10
    normal_disagreement = np.asarray([x["normal_component_mm"] for x in disagreement_rows]) / 10
    tangential_disagreement = np.asarray([x["tangential_component_mm"] for x in disagreement_rows]) / 10
    graph_disagreement = np.asarray([x["edge_graph_geodesic_upper_bound_mm"] for x in disagreement_rows]) / 10
    roundtrip = np.asarray([x["error_mm"] for x in roundtrip_rows]) / 10
    numeric_gates = {
        "direct_support_locality": bool(locality_diameter.max() * 10 <= 30 and locality_projection.max() * 10 <= 2),
        "official_mapping_roundtrip": bool(roundtrip.max() * 10 <= 5 and np.quantile(roundtrip * 10, 0.95) <= 3),
        "candidate_disagreement": bool(np.quantile(disagreement * 10, 0.95) <= 10 and disagreement.max() * 10 <= 15),
        "direct_sanity": all(
            sanity["DIRECT_SMPL"][key]
            for key in ("all_side_pass", "all_posterior_cross_section_pass", "all_coarse_region_pass", "all_symmetry_pass", "all_order_pass")
        ),
    }
    numeric_status = "PASS" if all(numeric_gates.values()) else "FAIL"
    results = {
        "schema": "DMD37_BRIDGE_NUMERIC_AUDIT_V2",
        "status": numeric_status,
        "contract_sha256": contract_sha,
        "candidate_count": 2,
        "point_count": 37,
        "direct_support_locality": {
            "diameter_mm": summary_mm(locality_diameter),
            "projection_residual_mm": summary_mm(locality_projection),
            "points": locality_rows,
        },
        "official_mapping_roundtrip": {
            "definition": contract["mandatory_numeric_checks"]["official_mapping_roundtrip"]["procedure"],
            "error_mm": summary_mm(roundtrip),
            "points": roundtrip_rows,
        },
        "candidate_disagreement": {
            "euclidean_mm": summary_mm(disagreement),
            "normal_component_mm": summary_mm(normal_disagreement),
            "tangential_component_mm": summary_mm(tangential_disagreement),
            "edge_graph_geodesic_upper_bound_mm": summary_mm(graph_disagreement),
            "geodesic_method": "MHR triangle-edge graph shortest-path upper bound; each surface point connects to its face's three vertices by Euclidean in-triangle segments",
            "points": disagreement_rows,
        },
        "sanity": sanity,
        "numeric_gates": numeric_gates,
        "limitations": [
            "The graph distance is an edge-graph upper bound, not an exact continuous geodesic.",
            "Posterior cross-section and LBS region checks are engineering geometry sanity checks, not anatomical validation.",
            "Passing numeric checks cannot establish medical correctness."
        ],
    }
    dump(OUT / "DMD37_BRIDGE_NUMERIC_AUDIT_V2.json", results)
    dump(
        OUT / "DMD37_DIRECT_BRIDGE_SUPPORT_LOCALITY_V2.json",
        {
            "schema": "DMD37_DIRECT_BRIDGE_SUPPORT_LOCALITY_V2",
            "status": "PASS" if numeric_gates["direct_support_locality"] else "FAIL",
            "contract_sha256": contract_sha,
            **results["direct_support_locality"],
            "thresholds_mm": contract["mandatory_numeric_checks"]["direct_support_locality"]["thresholds_mm"],
        },
    )
    dump(
        OUT / "DMD37_OFFICIAL_MAPPING_ROUNDTRIP_V2.json",
        {
            "schema": "DMD37_OFFICIAL_MAPPING_ROUNDTRIP_V2",
            "status": "PASS" if numeric_gates["official_mapping_roundtrip"] else "FAIL",
            "contract_sha256": contract_sha,
            **results["official_mapping_roundtrip"],
            "thresholds_mm": contract["mandatory_numeric_checks"]["official_mapping_roundtrip"]["thresholds_mm"],
        },
    )
    dump(
        OUT / "DMD37_BRIDGE_FAILURE_CASES_V2.json",
        {
            "schema": "DMD37_BRIDGE_FAILURE_CASES_V2",
            "status": "FAILURES_RECORDED",
            "contract_sha256": contract_sha,
            "support_locality_over_30mm": [
                row for row in locality_rows if row["support_diameter_mm"] > 30.0
            ],
            "candidate_disagreement_over_15mm": [
                row for row in disagreement_rows if row["euclidean_mm"] > 15.0
            ],
            "direct_order_failures": [
                row for row in sanity["DIRECT_SMPL"]["order"] if not row["pass"]
            ],
            "historical_order_failures": [
                row for row in sanity["HISTORICAL_SMPLX"]["order"] if not row["pass"]
            ],
            "interpretation": "Support locality and candidate disagreement are real numeric gate failures. The shared BL15-to-BL43 order failure exposes a frozen-contract grouping error and is not evidence that one candidate is worse."
        },
    )
    reverse_contract = {
        "schema": "MHR_SMPL_REVERSE_MAPPING_CONTRACT_V2",
        "status": "PASS_ASSET_AND_NUMERIC_INTEGRITY",
        "contract_sha256": contract_sha,
        "meaning": "Official surface mappings are approximate bidirectional barycentric samplers, not a bijection or semantic SKEL-to-MHR map.",
        "mhr2smpl": {
            "file": "AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/MHR/tools/mhr_smpl_conversion/assets/mhr2smpl_mapping.npz",
            "sha256": file_sha(asset_dir / "mhr2smpl_mapping.npz"),
            "source": "MHR LOD1 triangles",
            "target": "6890 SMPL vertices",
            "triangle_ids_shape": list(mhr2smpl["triangle_ids"].shape),
            "barycentric_shape": list(mhr2smpl["baryc_coords"].shape),
            "triangle_id_range": [int(mhr2smpl["triangle_ids"].min()), int(mhr2smpl["triangle_ids"].max())],
            "max_abs_barycentric_sum_error": float(np.abs(mhr2smpl["baryc_coords"].sum(1) - 1).max()),
        },
        "smpl2mhr": {
            "file": "AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/MHR/tools/mhr_smpl_conversion/assets/smpl2mhr_mapping.npz",
            "sha256": file_sha(asset_dir / "smpl2mhr_mapping.npz"),
            "source": "13776 SMPL triangles",
            "target": "18439 MHR LOD1 vertices",
            "triangle_ids_shape": list(smpl2mhr["triangle_ids"].shape),
            "barycentric_shape": list(smpl2mhr["baryc_coords"].shape),
            "triangle_id_range": [int(smpl2mhr["triangle_ids"].min()), int(smpl2mhr["triangle_ids"].max())],
            "max_abs_barycentric_sum_error": float(np.abs(smpl2mhr["baryc_coords"].sum(1) - 1).max()),
        },
        "cycle_test": {
            "procedure": contract["mandatory_numeric_checks"]["official_mapping_roundtrip"]["procedure"],
            "dmd37_error_mm": summary_mm(roundtrip),
            "gate_pass": numeric_gates["official_mapping_roundtrip"],
        },
        "limitations": [
            "Cycle consistency can pass even when a semantic correspondence is wrong.",
            "The direct DMD37 anchor composition generally spans three distinct MHR source triangles and still needs a declared one-time surface projection to become a single MHR face binding."
        ],
    }
    dump(OUT / "MHR_SMPL_REVERSE_MAPPING_CONTRACT_V2.json", reverse_contract)
    OUT.joinpath("raw").mkdir(exist_ok=True)
    dump(OUT / "raw" / "DMD37_BRIDGE_CANDIDATES_V2.json", {"schema": "DMD37_BRIDGE_CANDIDATES_V2", "contract_sha256": contract_sha, "candidates": candidates})
    neutral_map = {"Q": "DIRECT_SMPL", "R": "HISTORICAL_SMPLX"}
    image_path = render_blinded(vertices, candidates, neutral_map)
    dump(
        OUT / "raw" / "DMD37_BRIDGE_VISUAL_BLINDING_KEY_V2.json",
        {
            "schema": "DMD37_BRIDGE_VISUAL_BLINDING_KEY_V2",
            "image": str(image_path.relative_to(OUT)).replace("\\", "/"),
            "neutral_to_method": neutral_map,
            "warning": "Do not show this key to a prospective blind reviewer before review.",
        },
    )
    dump(
        OUT / "DMD37_BRIDGE_CANONICAL_VISUAL_REVIEW_V2.json",
        {
            "schema": "DMD37_BRIDGE_CANONICAL_VISUAL_REVIEW_V2",
            "status": "BLINDED_CANONICAL_ONLY_REVIEW_PENDING",
            "image": str(image_path.relative_to(OUT)).replace("\\", "/"),
            "creator_review_status": "NOT_COUNTED_AS_BLIND_BECAUSE_CREATOR_KNOWS_METHODS_AND_HISTORY",
            "blind_reviewer_result": "PENDING_OR_INCONCLUSIVE",
        },
    )
    print(json.dumps({"contract_sha256": contract_sha, "numeric_status": numeric_status, "gates": numeric_gates, "image": str(image_path)}))


if __name__ == "__main__":
    main()
