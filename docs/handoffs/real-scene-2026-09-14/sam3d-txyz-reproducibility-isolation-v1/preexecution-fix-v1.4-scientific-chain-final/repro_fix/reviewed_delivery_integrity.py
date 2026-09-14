import argparse,json,subprocess
from pathlib import Path

REVIEWED_TAG='sam3d-txyz-repro-v1.4.3'

def git(repo,*args,check=True):
 result=subprocess.run(['git',*args],cwd=str(repo),text=True,encoding='utf-8',errors='strict',capture_output=True,check=False)
 if check and result.returncode!=0:raise RuntimeError(f'REVIEWED_DELIVERY_GIT_COMMAND_FAILED:{" ".join(args)}:{result.stderr.strip()}')
 return result

def verify(delivery_root=None,repo_root=None,reviewed_tag=REVIEWED_TAG):
 delivery=Path(delivery_root or Path(__file__).parents[1]).resolve()
 repo=Path(repo_root).resolve() if repo_root else Path(git(delivery,'rev-parse','--show-toplevel').stdout.strip()).resolve()
 try:relative=delivery.relative_to(repo).as_posix()
 except ValueError as error:raise RuntimeError('REVIEWED_DELIVERY_OUTSIDE_GIT_WORKTREE') from error
 head=git(repo,'rev-parse','HEAD').stdout.strip();tag_commit=git(repo,'rev-parse',f'{reviewed_tag}^{{commit}}').stdout.strip()
 if head!=tag_commit:raise RuntimeError(f'REVIEWED_DELIVERY_COMMIT_MISMATCH:HEAD={head}:TAG={tag_commit}')
 tracked_diff=git(repo,'diff','--quiet',tag_commit,'HEAD','--',relative,check=False)
 if tracked_diff.returncode!=0:raise RuntimeError('REVIEWED_DELIVERY_COMMITTED_TREE_MISMATCH')
 status=git(repo,'status','--porcelain','--untracked-files=all','--',relative).stdout.splitlines()
 if status:raise RuntimeError('REVIEWED_DELIVERY_WORKTREE_DIRTY:'+json.dumps(status,separators=(',',':')))
 return {'status':'PASS_REVIEWED_DELIVERY_INTEGRITY','reviewed_tag':reviewed_tag,'reviewed_commit':tag_commit,'head_commit':head,'delivery_relative_path':relative,'working_tree_clean':True,'commit_identity_exact':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--delivery-root',type=Path);p.add_argument('--repo-root',type=Path);p.add_argument('--reviewed-tag',default=REVIEWED_TAG);p.add_argument('--output',type=Path);a=p.parse_args();result=verify(a.delivery_root,a.repo_root,a.reviewed_tag)
 if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
 else:print(json.dumps(result,indent=2))
if __name__=='__main__':main()
