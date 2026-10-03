"""Small checks for the real data flow, fixed algorithm snapshots, and rendering."""
import ast,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from data_v2 import block_split,array_sha,save_json,load_json
from cache_v2 import historical_sample_indices,save_mesh,verify_cache,mesh_path
from make_visuals import render_depth_cpu
from metrics_v2 import ray_depth_residual

ROOT=Path(__file__).resolve().parents[1]


def function_ast(path,name):
    tree=ast.parse(path.read_text(encoding='utf8'))
    return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)


class PipelineTests(unittest.TestCase):
    def test_perspective_raster_matches_continuous_ray(self):
        v=np.array([[0,0,1],[2,0,2],[0,2,2]],float);F=np.array([[0,1,2]])
        K=np.array([[3,0,0],[0,3,0],[0,0,1]],float)
        depth=render_depth_cpu(v,F,K,4,4)
        # Pixel (1,1) = normalized ray (1/3,1/3), intersection Z=1.5.
        self.assertAlmostEqual(depth[1,1],1.5,places=12)
        d,h=ray_depth_residual(np.array([[.5,.5,1.5]]),v,F,K)
        self.assertTrue(h[0]);self.assertAlmostEqual(depth[1,1]-1.5,d[0],places=12)

    def test_algorithm_snapshot_functions_preserved(self):
        records=load_json(ROOT/'ALGORITHM_SNAPSHOT.json')
        # The original paths are local provenance only; use the committed AST
        # digests on another machine (no dependence on the old output directory).
        expected=load_json(ROOT/'ALGORITHM_FUNCTION_AST.json')
        for filename,names in expected.items():
            for name,digest in names.items():
                actual=hashlib.sha256(function_ast(ROOT/'code'/filename,name).encode()).hexdigest()
                self.assertEqual(actual,digest,(filename,name))

    def test_historical_spatial_split_and_sampling(self):
        points=np.c_[np.arange(100)/200,np.arange(100)%4/40,np.ones(100)]
        for seed in [0,1,2]:
            key=np.floor(points[:,:2]/.06).astype(int);key=key[:,0]*1000+key[:,1]
            u=np.unique(key);chosen=np.random.default_rng(seed).choice(u,int(round(.2*len(u))),replace=False)
            ho=block_split(points,seed);np.testing.assert_array_equal(ho,np.isin(key,chosen))
            idx=np.flatnonzero(~ho);chosen=historical_sample_indices(idx,10,'mock-o2-observed')
            self.assertTrue(np.isin(chosen,idx).all());self.assertFalse(np.intersect1d(chosen,np.flatnonzero(ho)).size)

    def test_five_branch_cache_main_path(self):
        # Mock only SAM and optimization mathematics. Execute the actual
        # branching, caching, train-point audit, evaluation and figures.
        import run_comparison as runner
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out';delivery=Path(temp)/'delivery';delivery.mkdir()
            contract=load_json(ROOT/'EXPERIMENT_CONTRACT.json');contract['seeds']=[0]
            contract['dev']=['S107']
            save_json(delivery/'EXPERIMENT_CONTRACT.json',contract)
            save_json(delivery/'POSTERIOR_FACE_MASK.json',dict(face_ids=[0,1]))
            save_json(delivery/'POSTERIOR_RGB_ROI.json',dict(entries=[dict(subject='S107',polygon_xy_px=[[1,1],[18,1],[18,18],[1,18]])]))
            inp=out/'inputs/S107';inp.mkdir(parents=True)
            V=np.array([[-.2,-.2,1],[.2,-.2,1],[.2,.2,1],[-.2,.2,1]],float);F=np.array([[0,1,2],[0,2,3]])
            points=np.array([[x,y,1] for x in [-.15,-.05,.05,.15] for y in [-.15,-.05,.05,.15]])
            K=np.array([[30,0,10],[0,30,10],[0,0,1]],np.float32)
            np.savez_compressed(inp/'input.npz',points_m=points,K=K,rgb=np.zeros((20,20,3),np.uint8),
                bbox_xyxy=np.array([2,2,18,18]),posterior_point_mask=np.ones(16,bool),posterior_rgb_mask=np.ones((20,20),bool))
            train=np.arange(12);held=np.arange(12,16)
            np.savez_compressed(inp/'split_0.npz',train_idx=train,heldout_idx=held,posterior_eval_idx=held,torso_eval_idx=held)
            pred={s:np.zeros(3) for s in runner.STATE_KEYS.values()};pred['pred_vertices']=V
            class Estimator:
                calls=0
                def process_one_image(self,*args,**kwargs):self.calls+=1;return [pred]
            class Baseline:
                @staticmethod
                def fit_txyz(p,a):np.testing.assert_array_equal(p,points[train]);return np.zeros(3),[]
                @staticmethod
                def optimize_pose(model,pr,ap,p,*args):
                    np.testing.assert_array_equal(p,points[train]);return V,{k:pr[s] for k,s in runner.STATE_KEYS.items()},[0.],p
            torch=SimpleNamespace(manual_seed=lambda s:None,as_tensor=lambda *args,**kwargs:None,float32=None)
            estimator=Estimator();args=SimpleNamespace(out=out)
            fi=np.array([0,1]);bary=np.ones((2,3))/3
            with patch.object(runner,'DELIVERY',delivery),patch.object(runner,'parameter_vertices',return_value=V),\
                 patch.object(runner,'fit_rigid',return_value=(np.eye(3),np.zeros(3))),\
                 patch.object(runner,'fit_displacement',return_value=(V,np.zeros_like(V),{})):
                rows=runner.run_subject(args,'S107',None,estimator,F,fi,bary,torch,Baseline,contract)
                # Resumption reuses exactly one Official cache, without inference.
                runner.run_subject(args,'S107',None,estimator,F,fi,bary,torch,Baseline,contract)
            self.assertEqual(estimator.calls,1);self.assertEqual(len(rows),5)
            for name in contract['methods']:
                meta=verify_cache(mesh_path(out,'S107',0,name),out,'S107',0)
                self.assertEqual(meta['optimization_heldout_intersection'],0)
                with np.load(mesh_path(out,'S107',0,name)) as z:
                    self.assertTrue(all('mhr_'+k in z for k in runner.STATE_KEYS))
            self.assertEqual(len(load_json(out/'visualizations/S107/manifest.json')),5)


if __name__=='__main__':unittest.main()
