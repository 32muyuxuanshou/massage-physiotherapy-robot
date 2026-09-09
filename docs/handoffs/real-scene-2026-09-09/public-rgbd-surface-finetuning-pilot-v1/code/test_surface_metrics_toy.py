"""Synthetic unit tests. No HuMMan DEV or sealed-test observation is read."""
import argparse
import json
import numpy as np

from surface_metrics import (camera_to_world, legacy_point_to_vertex,
                             _point_triangle_distance_squared, point_to_triangle,
                             point_to_triangle_distances,
                             render_depth, world_to_camera)


def test_world_camera_roundtrip_contract():
    theta = 0.37
    R = np.array([[np.cos(theta), 0., np.sin(theta)], [0., 1., 0.],
                  [-np.sin(theta), 0., np.cos(theta)]])
    T = np.array([0.3, -0.2, 1.7])
    world = np.array([[0.1, 0.2, 0.3], [-1.0, 2.0, 4.0]])
    assert np.allclose(camera_to_world(world_to_camera(world, R, T), R, T), world,
                       atol=1e-12)


def test_triangle_interior_distinguishes_legacy_vertex_metric():
    vertices = np.array([[-1., -1., 2.], [1., -1., 2.], [0., 1., 2.]])
    faces = np.array([[0, 1, 2]])
    point = np.array([[0., 0., 2.]])
    assert point_to_triangle(point, vertices, faces)["max_mm"] < 1e-8
    assert legacy_point_to_vertex(point, vertices)["median_mm"] > 900


def test_triangle_distance_and_millimetre_contract():
    vertices = np.array([[-1., -1., 2.], [1., -1., 2.], [0., 1., 2.]])
    d = point_to_triangle(np.array([[0., 0., 2.010]]), vertices, np.array([[0, 1, 2]]))
    assert abs(d["median_mm"] - 10.0) < 1e-8


def test_degenerate_triangle_falls_back_to_segment():
    vertices = np.array([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]])
    d = point_to_triangle_distances(np.array([[0.5, 0.2, 0.]]), vertices, np.array([[0, 1, 2]]))
    assert np.allclose(d, 0.2)


def test_triangle_bvh_matches_exhaustive_small_case():
    rng = np.random.default_rng(42)
    vertices = rng.normal(size=(30, 3))
    faces = np.arange(30).reshape(10, 3)
    points = rng.normal(size=(7, 3))
    bvh = point_to_triangle_distances(points, vertices, faces)
    exhaustive = []
    triangles = vertices[faces]
    for point in points:
        paired = np.broadcast_to(point, (len(triangles), 3))
        exhaustive.append(np.sqrt(_point_triangle_distance_squared(paired, triangles).min()))
    assert np.allclose(bvh, exhaustive, atol=1e-12)


def test_rendered_depth_opencv_coordinate_contract():
    vertices = np.array([[-.2, -.2, 2.], [.2, -.2, 2.], [.2, .2, 2.], [-.2, .2, 2.]])
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    K = np.array([[100., 0., 32.], [0., 100., 32.], [0., 0., 1.]])
    depth = render_depth(vertices, faces, K, 64, 64)
    assert abs(float(depth[32, 32]) - 2.0) < 1e-3
    assert depth[0, 0] == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = []
    for test in tests:
        test()
        passed.append(test.__name__)
        print("PASS", test.__name__)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            json.dump({"status": "ALL_SYNTHETIC_TESTS_PASSED", "test_count": len(passed),
                       "tests": passed, "real_observations_accessed": False,
                       "sealed_test_accessed": False}, stream, indent=2)
