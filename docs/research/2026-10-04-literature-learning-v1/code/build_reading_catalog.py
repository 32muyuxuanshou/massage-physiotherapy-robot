"""Catalogue retrieved PDFs and explicitly recorded reading scopes; no model execution."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import fitz

delivery = Path(__file__).resolve().parents[1]
repo = delivery.parents[2]

PAPERS = [
    dict(id='3d-coded', title='3D-CODED: 3D Correspondences by Deep Deformation',
         authors=['Thibault Groueix', 'Matthew Fisher', 'Vladimir G. Kim', 'Bryan C. Russell', 'Mathieu Aubry'],
         venue='ECCV 2018', filename='3d_coded_eccv2018.pdf',
         source='https://openaccess.thecvf.com/content_ECCV_2018/papers/Thibault_Groueix_Shape_correspondences_from_ECCV_2018_paper.pdf',
         code='https://github.com/ThibaultGROUEIX/3D-CODED', code_check='official README inspected; not executed',
         scope='method and correspondence ablation', text_pages=[1,5,6,13,14], visual_pages=[14], priority=1),
    dict(id='point2ssm', title='Point2SSM: Learning Morphological Variations of Anatomies from Point Clouds',
         authors=['Jadie Adams', 'Shireen Y. Elhabian'], venue='ICLR 2024 (Spotlight, author arXiv record and official code)',
         filename='2305.14486.pdf', source='https://arxiv.org/pdf/2305.14486',
         code='https://github.com/jadie1/Point2SSM', code_check='official README inspected; not executed',
         scope='method, evaluation definitions, robustness, limitations; arXiv v2; OpenReview PDF returned HTTP403',
         text_pages=[1,4,5,6,8,9], visual_pages=[4,8,9], priority=2),
    dict(id='bodymap-correspondence', title='BodyMap: Learning Full-Body Dense Correspondence Map',
         authors=['Anastasia Ianina', 'Nikolaos Sarafianos', 'Yuanlu Xu', 'Ignacio Rocco', 'Tony Tung'],
         venue='CVPR 2022', filename='2205.09111.pdf', source='https://arxiv.org/pdf/2205.09111',
         project='https://nsarafianos.github.io/bodymap', code_check='project page inspected; code/weights not established',
         scope='architecture, losses, supervision and real-domain adaptation, selected qualitative/ablation',
         text_pages=[3,4,5], visual_pages=[3,7], priority=3),
    dict(id='densematcher', title='DenseMatcher: Learning 3D Semantic Correspondence for Category-Level Manipulation from a Single Demo',
         authors=['Junzhe Zhu', 'Yuanchen Ju', 'Junyi Zhang', 'Muhan Wang', 'Zhecheng Yuan', 'Kaizhe Hu', 'Huazhe Xu'],
         venue='ICLR 2025', filename='densematcher_iclr2025.pdf',
         source='https://proceedings.iclr.cc/paper_files/paper/2025/file/7ba6b5b03ae07151a9a353b51f943290-Paper-Conference.pdf',
         alternate_filename='2412.05268.pdf', alternate_source='https://arxiv.org/pdf/2412.05268',
         code='https://github.com/TEA-Lab/DenseMatcher', code_check='official README inspected; not executed',
         scope='final-version architecture, training, evaluation, robot workflow and partial matching; preprint also consulted',
         text_pages=[1,5,6,7,8,9,21,22], visual_pages=[5,8], priority=4),
    dict(id='disrt-in-bed', title='DiSRT-In-Bed: Diffusion-Based Sim-to-Real Transfer Framework for In-Bed Human Mesh Recovery',
         authors=['Jing Gao', 'Ce Zheng', 'Laszlo A. Jeni', 'Zackory Erickson'], venue='CVPR 2025',
         filename='2504.03006.pdf', source='https://arxiv.org/pdf/2504.03006',
         code='https://github.com/Jing-G2/DiSRT-In-Bed', code_check='official repository entry inspected; not executed',
         scope='SMPL diffusion, architecture, training and dataset protocol; selected main results',
         text_pages=[3,4,5], visual_pages=[3,5,6,7], priority=5),
    dict(id='votehmr', title='VoteHMR: Occlusion-Aware Voting Network for Robust 3D Human Mesh Recovery from Partial Point Clouds',
         authors=['Guanze Liu', 'Yu Rong', 'Lu Sheng'], venue='ACM MM 2021',
         filename='2110.08729.pdf', source='https://arxiv.org/pdf/2110.08729',
         code='https://github.com/hanabi7/VoteHMR', code_check='official README inspected; not executed',
         scope='point voting/completion/regression/losses; synthetic and real evaluation; ablation',
         text_pages=[3,4,5], visual_pages=[3,6,7], priority=6),
    dict(id='bodymap-bed', title='BodyMAP - Jointly Predicting Body Mesh and 3D Applied Pressure Map for People in Bed',
         authors=['Abhishek Tandon', 'Anujraaj Goyal', 'Henry M. Clever', 'Zackory Erickson'], venue='CVPR 2024',
         filename='2404.03183.pdf', source='https://arxiv.org/pdf/2404.03183',
         code_check='paper and source pages inspected; execution readiness not verified',
         scope='FIM/PointNet/pressure weak supervision; modality, label source and main result table',
         text_pages=[3,4,5,8], visual_pages=[4,6,7], priority=7),
    dict(id='markerless-spinal', title='Markerless spinal assessment: a purely geometric framework for automated landmark detection from 3D surface scans',
         authors=['Paolo Di Stefano', 'Emanuele Guardiani', 'Anna Eva Morabito'], venue='IJIDeM 2026',
         filename='markerless_spinal_2026.pdf', source='https://link.springer.com/content/pdf/10.1007/s12008-026-02603-8.pdf',
         doi='10.1007/s12008-026-02603-8', code_check='no public code/data package verified; no author contacted',
         scope='shape-index method, acquisition, marker-reference evaluation and limitations',
         text_pages=[4,5,6,7,8,10,11], visual_pages=[8,12], priority=8),
    dict(id='bodies-at-rest', title='Bodies at Rest: 3D Human Pose and Shape Estimation From a Pressure Image Using Synthetic Data',
         authors=['Henry M. Clever', 'Zackory Erickson', 'Ariel Kapusta', 'Greg Turk', 'C. Karen Liu', 'Charles C. Kemp'],
         venue='CVPR 2020', filename='bodies_at_rest_cvpr2020.pdf',
         source='https://openaccess.thecvf.com/content_CVPR_2020/papers/Clever_Bodies_at_Rest_3D_Human_Pose_and_Shape_Estimation_From_CVPR_2020_paper.pdf',
         code='https://github.com/Healthcare-Robotics/bodies-at-rest', code_check='official README inspected; existing project data not re-downloaded',
         scope='context audit: synthetic labels, real 20-person acquisition and actual evaluation',
         text_pages=[3,6,7], visual_pages=[7], priority=None),
    dict(id='jotr', title='JOTR: 3D Joint Contrastive Learning with Transformers for Occluded Human Mesh Recovery',
         authors=['Jiahao Li', 'Zongxin Yang', 'Xiaohan Wang', 'Jianxin Ma', 'Chang Zhou', 'Yi Yang'],
         venue='ICCV 2023', filename='2307.16377.pdf', source='https://arxiv.org/pdf/2307.16377',
         code_check='not inspected', scope='limited input-modality and feature-lifting audit; not full experiment review',
         text_pages=[3,4], visual_pages=[3], priority=None),
    dict(id='sam3d-body', title='SAM 3D Body: Robust Full-Body Human Mesh Recovery',
         authors_status='see existing paper title page', venue='CVPR 2026',
         filename='C:/Users/Administrator/Downloads/Yang_SAM_3D_Body_Robust_Full-Body_Human_Mesh_Recovery_CVPR_2026_paper.pdf',
         source='user-provided existing PDF',
         public_source='https://openaccess.thecvf.com/content/CVPR2026/papers/Yang_SAM_3D_Body_Robust_Full-Body_Human_Mesh_Recovery_CVPR_2026_paper.pdf',
         public_source_check='web request returned HTTP403; reading used existing local PDF',
         code='https://github.com/facebookresearch/sam-3d-body', code_check='existing project baseline; not re-executed this reading round',
         scope='reread architecture, annotation and mesh fitting', text_pages=[3,4,5], visual_pages=[3,5], priority=None),
]

def describe(path):
    with fitz.open(path) as pdf:
        version = re.search(r'arXiv:\s*\d+\.\d+v\d+', pdf[0].get_text())
        return dict(path=path.as_posix(), bytes=path.stat().st_size, pages=len(pdf),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    arxiv_version=version.group(0) if version else None)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf-root', type=Path, default=repo / 'downloads/literature-learning-20261004')
    args = ap.parse_args()
    entries = []
    for paper in PAPERS:
        row = dict(paper)
        path = Path(row['filename'])
        if not path.is_absolute():
            path = args.pdf_root / path
        row['actual_pdf'] = describe(path)
        if 'alternate_filename' in row:
            row['alternate_pdf'] = describe(args.pdf_root / row['alternate_filename'])
        row['all_pdf_pages_read'] = False
        row['model_executed_this_round'] = False
        entries.append(row)
    catalog = dict(date='2026-10-04', mode='focused literature learning, not systematic review',
                   unique_papers=11, newly_downloaded_unique_papers=10, newly_downloaded_pdf_files=11,
                   reused_existing_pdf_files=1, core_method_papers=8,
                   rendered_page_images=len(list((args.pdf_root / 'page_images').glob('*.png'))),
                   actually_viewed_page_images=sum(len(x['visual_pages']) for x in entries),
                   reading_pages_are_one_based=True, papers=entries)
    (delivery / 'PAPERS.json').write_bytes((json.dumps(catalog, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps({k:v for k,v in catalog.items() if k != 'papers'}))
