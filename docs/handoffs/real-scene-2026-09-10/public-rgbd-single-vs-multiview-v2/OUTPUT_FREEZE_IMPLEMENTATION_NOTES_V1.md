# Pose/Camera output freeze gate

Gate result: **PASS_EXACT_OUTPUT_FREEZE**.

The live MHR pose head is a joint 519-output FFN. Its runtime-derived ranges are global rotation `[0,6)`, continuous body pose `[6,266)`, shape `[266,311)`, scale `[311,339)`, hands `[339,447)`, and face `[447,519)`. Only the first 266 rows are allowed to change. The entire camera FFN remains trainable.

The implementation freezes all pose-head hidden layers, masks gradients on forbidden final-projection rows, restores those rows from the Official parameters after every AdamW step, and clears matching optimizer-state rows. Restoring rows alone is insufficient: pose feedback changes the decoder token at later iterations, which otherwise changes forbidden outputs even with identical frozen weights. Therefore each of the six iterative pose projection calls also replaces forbidden raw values with the corresponding per-input Official reference values.

The 100-step test used one fixed real HuMMan RGB observation with its dataset ROI and camera intrinsics. At steps 1, 10, and 100, shape, scale, derived MHR scales, hands, and face remained tensor-exact with maximum absolute difference `0.0`; global rotation, body pose, raw camera, and camera translation changed.

This exact contract has a real runtime cost. Training samples may cache their Official six-stage references. An unseen input needs an Official reference pass before the tuned pass unless the architecture is redesigned to carry an independent frozen forbidden-output branch. This is still feed-forward RGB+K inference, but it is a two-pass implementation and must be reported as such.
