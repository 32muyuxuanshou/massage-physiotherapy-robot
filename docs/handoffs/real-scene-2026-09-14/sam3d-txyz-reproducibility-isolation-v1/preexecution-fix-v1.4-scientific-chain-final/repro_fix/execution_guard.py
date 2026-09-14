import hashlib,os
GO_TOKEN='GO_SAM3D_TXYZ_REPRODUCIBILITY_ISOLATION_V1'
GO_SHA256=hashlib.sha256(GO_TOKEN.encode()).hexdigest()
def require_master_authorization():
 if os.environ.get('REPRO_ISOLATION_MASTER_ACTIVE')!='1' or os.environ.get('REPRO_ISOLATION_GO_TOKEN_SHA256')!=GO_SHA256:raise RuntimeError('FORMAL_CHILD_MUST_RUN_THROUGH_MASTER_ORCHESTRATOR')
 return True
