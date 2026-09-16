# FORMAL_RGBD_ORACLE_PARAMETER_SPACE_STUDY_V1

This study tests whether K0-only RGB-D geometry can improve MHR pose and/or shape beyond the frozen Cheap Txyz V2.3 translation baseline, with K1/K2/K3 reserved for held-out evaluation after Stage A is frozen.

Status: formal experiment completed on 45 frames / 5 subjects. Stage A was frozen from K0-only evidence before K1/K2/K3 evaluation.

Decision: **STRONG_GO**. O2 (translation + pose) is the strongest group: held-out subject-aware median improves by 10.62% / 1.98 mm over O1, aligned error improves by 7.84%, and all 5 subjects improve. O4 also passes; O3 shape-only does not.

See [the complete report](results-v1/FINAL_REPORT.md), [formal characterization](results-v1/stage_b/FINAL_CHARACTERIZATION.json), [execution ledger](results-v1/EXECUTION_LEDGER.json), and [visualizations](results-v1/report/visualizations/).
