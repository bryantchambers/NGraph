# GPU Scaling Notes for NGraph

## Current State

The existing NGraph pipeline is still mostly CPU-bound.

- R steps such as CLR matrix construction, site-graph building, and graph-of-graphs remain on CPU.
- The PyTorch training steps in `07_ngraph_train_vgae.py` and `08_ngraph_train_diffpool.py` use `torch`, but they do not yet move tensors or models to CUDA.
- Link prediction in `10_ngraph_link_prediction.py` uses scikit-learn `LogisticRegression`, so it is also CPU-bound today.

## Practical Result

Because of that, a 96 GB VRAM GPU would not materially speed up the current pipeline unless the code is changed to use it.

As-is:

- expected end-to-end speedup from hardware alone: near zero
- the GPU would mainly add memory capacity, not throughput

## If the Pipeline Is Properly GPU-Enabled

The GPU return becomes meaningful once the learned-model stages are rewritten for CUDA and batched graph processing.

Likely gains:

- current scale: about `2x` to `5x` faster on the modeling stages
- future large scale: `10x+` effective throughput on graph learning and inference
- million-taxon / thousand-site scale: the GPU is less a convenience and more a feasibility requirement

## Where the Return Is Strongest

- VGAE training
- DiffPool training
- large-scale embedding generation
- batched link scoring

## Where the Return Is Weakest

- R preprocessing
- I/O-heavy steps
- static report generation
- small CPU-only calibration tasks

## Architectural Implication

To get the real return, the pipeline should eventually move toward:

- explicit CUDA device placement
- sparse graph minibatching
- site-wise batching
- reduced host-to-device copying
- a clean split between CPU preprocessing and GPU learning

## Bottom Line

A GPU will not automatically accelerate this pipeline.
The payoff comes only after the modeling stack is rewritten to actually exploit it.
At the scale this project is heading toward, that rewrite becomes necessary rather than optional.
