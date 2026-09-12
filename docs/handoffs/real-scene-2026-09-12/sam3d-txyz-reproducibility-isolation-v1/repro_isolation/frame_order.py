import random
def build(rows,seed=20260912):
 original=list(rows);reversed_rows=list(reversed(rows));random_rows=list(rows);random.Random(seed).shuffle(random_rows);return {'sentinel_frozen_before_execution':True,'orders':{'ORDER_ORIGINAL':original,'ORDER_REVERSED':reversed_rows,'ORDER_RANDOM_FIXED_SEED':random_rows},'seed':seed}
