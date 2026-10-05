"""Three GPU workers, shared source roles, three preset seeds; no raw data to Git."""
import os
import subprocess
import sys

from acquire_full_v3 import ROOT


def main():
    env=os.environ.copy();env['TMPDIR']=str(ROOT/'tmp');env['MPLCONFIGDIR']=str(ROOT/'mpl_cache')
    env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
    subprocess.run([sys.executable,str(ROOT/'code/fit_field_prior.py')],env=env,check=True)
    methods=['GLOBAL_ANATOMY','LOCAL_ANATOMY','LOCAL_JOINT']
    for seed in [0,1,2]:
        jobs=[]
        for gpu,method in enumerate(methods):
            job_env=env.copy();job_env['CUDA_VISIBLE_DEVICES']=str(gpu)
            log_path=ROOT/('train_'+method+'_seed'+str(seed)+'.log')
            log=log_path.open('w')
            process=subprocess.Popen([sys.executable,str(ROOT/'code/train_field.py'),'--model',method,'--seed',str(seed),'--epochs','60'],
                                     env=job_env,stdout=log,stderr=subprocess.STDOUT)
            jobs.append((process,log,method))
        for process,log,method in jobs:
            code=process.wait();log.close()
            assert code==0, method+'_TRAINING_FAILED'
        for reference_noise in ['0','5']:
            eval_env=env.copy();eval_env['CUDA_VISIBLE_DEVICES']='0'
            subprocess.run([sys.executable,str(ROOT/'code/evaluate_field.py'),'--seed',str(seed),'--reference-noise-mm',reference_noise],
                           env=eval_env,check=True)
        subprocess.run([sys.executable,str(ROOT/'code/evaluate_field.py'),'--seed',str(seed),'--no-references'],
                       env=eval_env,check=True)
    subprocess.run([sys.executable,str(ROOT/'code/aggregate_field.py')],env=env,check=True)


if __name__=='__main__':
    main()
