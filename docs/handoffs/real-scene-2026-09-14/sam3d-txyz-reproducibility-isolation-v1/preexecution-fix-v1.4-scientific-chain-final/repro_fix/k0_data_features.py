import cv2,numpy as np
from .hashing import file_sha

def extract(depth_path,mask_path,expected_depth_sha256=None,expected_mask_sha256=None):
 if expected_depth_sha256 and file_sha(depth_path)!=expected_depth_sha256:raise RuntimeError('K0_DEPTH_HASH_MISMATCH')
 if expected_mask_sha256 and file_sha(mask_path)!=expected_mask_sha256:raise RuntimeError('K0_MASK_HASH_MISMATCH')
 depth=cv2.imread(str(depth_path),-1);mask=cv2.imread(str(mask_path),0)
 if depth is None or mask is None or depth.shape!=mask.shape:raise RuntimeError('K0_DEPTH_MASK_DECODE_INVALID')
 person=mask>127;valid=person&(depth>0);person_count=int(person.sum());valid_count=int(valid.sum())
 if person_count==0 or valid_count==0:raise RuntimeError('K0_DEPTH_SUPPORT_EMPTY')
 y,x=np.where(valid);mid_x=depth.shape[1]/2;mid_y=depth.shape[0]/2;support=valid_count/person_count
 return {'valid_depth_pixels':valid_count,'depth_support_fraction':float(support),'depth_hole_ratio':float(1-support),'support_left_right_balance':float((np.sum(x<mid_x)-np.sum(x>=mid_x))/valid_count),'support_top_bottom_balance':float((np.sum(y<mid_y)-np.sum(y>=mid_y))/valid_count)}
