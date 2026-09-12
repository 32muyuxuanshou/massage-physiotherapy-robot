import cv2,numpy as np

def extract(depth_path,mask_path):
    depth=cv2.imread(str(depth_path),cv2.IMREAD_UNCHANGED);mask=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
    if depth is None or mask is None:raise RuntimeError('K0_DEPTH_OR_MASK_UNREADABLE')
    person=mask>127;valid=person&(depth>0);y,x=np.where(valid)
    if not person.any() or not valid.any():raise RuntimeError('K0_DEPTH_SUPPORT_EMPTY')
    mid_x=mask.shape[1]/2;mid_y=mask.shape[0]/2;values=depth[valid].astype(float)
    return {'valid_depth_pixels':int(valid.sum()),'depth_support_fraction':float(valid.sum()/person.sum()),'depth_hole_ratio':float(1-valid.sum()/person.sum()),'depth_range_mm':float(np.percentile(values,95)-np.percentile(values,5)),'support_left_right_balance':float((np.sum(x<mid_x)-np.sum(x>=mid_x))/len(x)),'support_top_bottom_balance':float((np.sum(y<mid_y)-np.sum(y>=mid_y))/len(y))}
