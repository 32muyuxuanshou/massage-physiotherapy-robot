from .back_region import require_ready

def compute_placeholder(region):
    require_ready(region)
    raise RuntimeError("REQUIRES_POST_REVIEW_EXECUTION")
