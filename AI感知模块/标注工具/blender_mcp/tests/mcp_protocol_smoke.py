"""Exercise Codex STDIO MCP -> local bridge -> real Blender end to end."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


ROOT = Path(__file__).resolve().parents[1]


def _structured(result):
    data = result.structured_content
    if not isinstance(data, dict):
        raise AssertionError(f"tool returned no structured object: {result}")
    return data


async def main() -> None:
    atlas = os.environ["ACUPOINT_MCP_TEST_ATLAS"]
    parameters = StdioServerParameters(
        command=str(ROOT / ".venv" / "Scripts" / "python.exe"),
        args=[str(ROOT / "server.py")],
        cwd=str(ROOT),
        env={
            "ACUPOINT_MCP_PROJECT_ROOT": os.environ["ACUPOINT_MCP_PROJECT_ROOT"],
            "ACUPOINT_MCP_HOST": "127.0.0.1",
            "ACUPOINT_MCP_PORT": "9877",
        },
    )
    async with Client(parameters, raise_exceptions=True, read_timeout_seconds=320.0) as client:
        listed = await client.list_tools()
        names = [tool.name for tool in listed.tools]
        expected = {
            "blender_status",
            "start_skel_session",
            "inspect_scene",
            "validate_atlas",
            "get_acupoint_3d",
            "list_cameras",
            "set_camera_view",
            "export_training_sample",
        }
        assert set(names) == expected, names
        status = _structured(await client.call_tool("blender_status", {}))
        assert status["connected"] is True, status
        validation = _structured(await client.call_tool("validate_atlas", {"atlas_path": atlas}))
        assert validation["valid"] is True, validation
        point = _structured(
            await client.call_tool(
                "get_acupoint_3d",
                {"atlas_path": atlas, "point_id": "11_MIDLINE"},
            )
        )
        assert point["face_index"] == 13745, point
        camera = _structured(
            await client.call_tool(
                "set_camera_view",
                {"preset": "front", "distance_scale": 1.0, "focal_length_mm": 50.0},
            )
        )
        sample = _structured(
            await client.call_tool(
                "export_training_sample",
                {
                    "atlas_path": atlas,
                    "point_ids": ["11_MIDLINE", "2_MIDLINE", "3_MIDLINE"],
                    "camera_name": camera["camera"],
                    "width": 512,
                    "height": 512,
                },
                read_timeout_seconds=300.0,
            )
        )
        for key in ("rgb_path", "labels_path", "overlay_path", "manifest_path"):
            assert Path(sample[key]).is_file(), (key, sample)
        print(
            "ACUPOINT_MCP_PROTOCOL_SMOKE="
            + json.dumps(
                {
                    "tools": names,
                    "status": status,
                    "validation": validation,
                    "point": point,
                    "camera": camera,
                    "sample": sample,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

