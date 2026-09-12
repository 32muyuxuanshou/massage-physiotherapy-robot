# Deployment input realism audit specification V1

V2.3 is a dataset-provided human-mask-assisted RGB-D evaluation. `k0.person_mask.jpg` filters human depth and generates the SAM bbox; it is not a raw deployment-ready input pipeline.

A future fresh evaluation must freeze and compare: dataset mask/bbox baseline; detector bbox plus predicted human segmentation; and fixed mask perturbations covering erosion, dilation, boundary noise, object bleed and missing regions. It must report mesh and Txyz sensitivity without tuning on the evaluation outcomes. This experiment is not run here.
