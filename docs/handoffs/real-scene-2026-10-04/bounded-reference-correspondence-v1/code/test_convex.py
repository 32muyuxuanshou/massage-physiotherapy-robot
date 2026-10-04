import numpy as np
from convex_correspondence import convex_weights


def main():
    inputs=np.array([0.,1.,2.,3.]);query=np.linspace(0,3,8)
    distance=np.abs(inputs[:,None]-query[None,:]);w=convex_weights(distance)
    assert (w>=0).all();np.testing.assert_allclose(w.sum(axis=1),1)
    np.testing.assert_array_equal(w[0],[1,0,0,0]);np.testing.assert_array_equal(w[-1],[0,0,0,1])
    translation=np.tile([.02,-.01,.03],(4,1));np.testing.assert_allclose(w@translation,np.tile(translation[0],(8,1)),atol=1e-12)
    noise=np.array([[1,2,3],[-2,3,1],[2,1,-3],[-1,-3,2]],float);noise*=.005/np.linalg.norm(noise,axis=1)[:,None]
    assert np.linalg.norm(w@noise,axis=1).max()<=.005+1e-12
    print('PASS: positive weights, unit sums, endpoint identity, translation, noise bound')


if __name__=='__main__':main()
