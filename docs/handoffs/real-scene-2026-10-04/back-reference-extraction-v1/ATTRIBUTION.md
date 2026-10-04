# Source attribution and scope

Real XYZ scans and manually drawn reference curves originate from Mirko Kaiser / [PCdareSoftware](https://github.com/mkaisereth/PCdareSoftware), fixed commit `35f7a1d9c1b24264708111a986ba89bdf17f1df1`. Original software/data license: **CC BY-NC-SA 4.0**. Anonymous derived curves and geometry figures here retain that noncommercial share-alike attribution. They are not new clinical annotations.

The original hNet map preparation (`Asymmetry/hNet/A_GenerateDepthAsymmMaps.m`) explicitly reads XYZ pointcloud in metres and the source drawn ESL in millimetres separately. This task implements three new simple deterministic geometry baselines in Python; it does not claim to reproduce/train the authors' hNet.

[PCdare original publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC12728027/) distinguishes registration markers and external surface/spinous-process line. Neither is a verified acupoint label in this task. Original points/identity mapping and annotations stay on the authorized server. No raw photographs, X-rays, names, or model weights are included.
