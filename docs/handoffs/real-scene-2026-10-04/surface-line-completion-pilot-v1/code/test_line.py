"""One real training batch and the actual horizontal probability contract."""
import torch
from line_net import LineNet
from train_line import objective

def main():
    torch.set_num_threads(2);model=LineNet();x=torch.zeros(2,4,128,128)
    logits=model(x);assert logits.shape==(2,128,128)
    assert torch.allclose(logits.softmax(-1).sum(-1),torch.ones(2,128),atol=1e-6)
    xs=torch.linspace(-.15,.15,128).repeat(2,1);target=torch.zeros(2,128);valid=torch.ones(2,128,dtype=torch.bool)
    loss,expected=objective(logits,xs,target,valid);loss.backward()
    assert torch.isfinite(loss) and all(p.grad is not None for p in model.parameters())
    print('FORWARD_LOSS_BACKWARD_PASS',float(loss.detach()),sum(p.numel() for p in model.parameters()))

if __name__=='__main__':main()
