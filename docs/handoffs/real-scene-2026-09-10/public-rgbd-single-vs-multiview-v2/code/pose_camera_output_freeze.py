"""Exact output-row freeze for the SAM 3D Body MHR pose head.

The pose FFN is a joint 519-output head.  To keep non-pose outputs invariant we
freeze every hidden layer, mask gradients on the final Linear's forbidden rows,
then restore those rows and their optimizer state after every AdamW step.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import torch


@dataclass(frozen=True)
class OutputBlock:
    name: str
    start: int
    stop: int
    trainable: bool


def infer_mhr_output_contract(head) -> Tuple[OutputBlock, ...]:
    """Derive ranges from the live MHRHead attributes, not prompt constants."""
    cursor = 0
    specs = (
        ("global_rotation_6d", 6, True),
        ("body_pose_continuous", int(head.body_cont_dim), True),
        ("shape", int(head.num_shape_comps), False),
        ("scale_coefficients", int(head.num_scale_comps), False),
        ("hands", int(head.num_hand_comps) * 2, False),
        ("face_expression", int(head.num_face_comps), False),
    )
    blocks = []
    for name, width, trainable in specs:
        blocks.append(OutputBlock(name, cursor, cursor + width, trainable))
        cursor += width
    if cursor != int(head.npose):
        raise RuntimeError(f"runtime MHR contract covers {cursor}, head.npose={head.npose}")
    return tuple(blocks)


def find_final_linear(proj: torch.nn.Module) -> torch.nn.Linear:
    linears = [module for module in proj.modules() if isinstance(module, torch.nn.Linear)]
    if not linears:
        raise RuntimeError("projection contains no Linear")
    return linears[-1]


class PoseCameraOutputFreeze:
    """Configure and enforce strict pose-row/camera-only optimization."""

    def __init__(self, model):
        self.model = model
        self.blocks = infer_mhr_output_contract(model.head_pose)
        self.pose_final = find_final_linear(model.head_pose.proj)
        self.allowed = torch.zeros(self.pose_final.out_features, dtype=torch.bool,
                                   device=self.pose_final.weight.device)
        for block in self.blocks:
            if block.trainable:
                self.allowed[block.start:block.stop] = True
        self.forbidden = ~self.allowed

        model.requires_grad_(False)
        # Hidden pose layers remain frozen: changing them would change forbidden
        # outputs even if their final projection rows were restored.
        self.pose_final.weight.requires_grad_(True)
        self.pose_final.bias.requires_grad_(True)
        model.head_camera.proj.requires_grad_(True)

        self.reference_weight = self.pose_final.weight.detach().clone()
        self.reference_bias = self.pose_final.bias.detach().clone()
        self._hooks = (
            self.pose_final.weight.register_hook(self._mask_weight_gradient),
            self.pose_final.bias.register_hook(self._mask_bias_gradient),
        )
        self._reference_sequence = None
        self._reference_cursor = 0
        self._capture = None
        self._output_hook = model.head_pose.proj.register_forward_hook(self._replace_forbidden_output)

    def _replace_forbidden_output(self, module, inputs, output):
        if self._capture is not None:
            self._capture.append(output.detach().clone())
        if self._reference_sequence is None:
            return output
        if self._reference_cursor >= len(self._reference_sequence):
            raise RuntimeError("pose projection called more times than frozen reference")
        reference = self._reference_sequence[self._reference_cursor]
        self._reference_cursor += 1
        # torch.where preserves gradients only for allowed rows and clamps every
        # forbidden value to the Official per-input/per-decoder-stage prediction.
        return torch.where(self.allowed[None, :], output, reference.to(output))

    def begin_reference_capture(self):
        self._capture = []

    def end_reference_capture(self):
        captured = self._capture
        self._capture = None
        return captured

    def use_frozen_output_reference(self, sequence):
        self._reference_sequence = sequence
        self._reference_cursor = 0

    def clear_frozen_output_reference(self):
        if self._reference_sequence is not None and self._reference_cursor != len(self._reference_sequence):
            raise RuntimeError("pose projection called fewer times than frozen reference")
        self._reference_sequence = None
        self._reference_cursor = 0

    def _mask_weight_gradient(self, grad):
        return grad * self.allowed[:, None].to(dtype=grad.dtype)

    def _mask_bias_gradient(self, grad):
        return grad * self.allowed.to(dtype=grad.dtype)

    def parameters(self) -> Iterable[torch.nn.Parameter]:
        return (p for p in self.model.parameters() if p.requires_grad)

    @torch.no_grad()
    def restore_after_step(self, optimizer: torch.optim.Optimizer) -> None:
        """Undo AdamW decay/update and erase forbidden-row momentum exactly."""
        self.pose_final.weight[self.forbidden] = self.reference_weight[self.forbidden]
        self.pose_final.bias[self.forbidden] = self.reference_bias[self.forbidden]
        for param in (self.pose_final.weight, self.pose_final.bias):
            state = optimizer.state.get(param, {})
            for value in state.values():
                if torch.is_tensor(value) and value.shape == param.shape:
                    value[self.forbidden].zero_()

    def forbidden_parameter_rows_exact(self) -> Dict[str, bool]:
        return {
            "pose_final.weight": torch.equal(
                self.pose_final.weight[self.forbidden], self.reference_weight[self.forbidden]),
            "pose_final.bias": torch.equal(
                self.pose_final.bias[self.forbidden], self.reference_bias[self.forbidden]),
        }

    def output_contract_json(self):
        return [dict(name=b.name, range=[b.start, b.stop], dimension=b.stop-b.start,
                     trainable=b.trainable) for b in self.blocks]

