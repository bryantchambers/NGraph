# NGraph ML Workflow Learning Notes

## Purpose

This note captures the ML side of the conversation around the current NGraph pipeline:
- what the graph learning steps are doing
- how the learned outputs are used downstream
- what the main artifacts mean
- how the permissive `prev_10` exploratory branch behaved
- what to watch for when thinking about saturation, module stability, and downstream retrieval

This is not a generic ML overview. It is specific to the current pipeline as implemented in `/src`.

## The Pipeline in Plain Language

The current workflow takes ancient DNA OTU/taxon tables and turns them into:
- thresholded sample-centered CLR matrices
- site-specific taxon graphs
- graph-of-graphs comparisons
- heterograph exports
- learned node embeddings and modules
- predicted links
- evidence cards
- retrieval indexes
- query outputs and a local browser

The ML steps are not independent experiments. They are a chain:
1. build a graph representation from the abundance data
2. learn latent structure from that graph
3. use the learned structure to generate hypotheses
4. package those hypotheses into evidence cards
5. search and query the cards

## Two Branches We Now Care About

There are now two important operating modes:

### Strict branch

`abundance_thresholding`

Key properties:
- uses `tax_abund_tad`-only prevalence logic
- keeps a smaller feature space
- is the conservative baseline
- still uses sample-centered CLR

### Exploratory branch

`permissive_hybrid_prev10`

Key properties:
- keeps `is_dmg == "Damaged"`
- requires `n_reads >= 100`
- uses `tax_abund_tad` when available
- falls back to `tax_abund_read` when `tax_abund_tad` is zero
- retains taxa present in at least 10 samples
- still uses sample-centered CLR

This branch is intentionally permissive. The goal was to see whether the graph saturates when the feature space expands.

## What We Learned From the Permissive Run

The permissive run completed successfully end to end.

Important counts:
- stage-1 aggregate: `4621` taxa x `214` samples
- permissive `prev_10` matrix: `1797` taxa x `214` samples

The main takeaway is that the permissive hybrid fallback greatly expands the retained feature space, but the rest of the pipeline still runs without collapsing.

Observed behavior:
- site graphs became dense, especially for `bicor` and `spearman`
- `mi_aracne` remained much sparser
- graph-of-graphs similarity stayed informative
- VGAE and DiffPool both trained successfully
- link prediction completed with reasonable holdout AUC values
- the retrieval and query layers completed

So the permissive branch is dense, but not catastrophically saturated.

## What the ML Models Learn

### VGAE

VGAE stands for variational graph autoencoder.

It learns:
- a latent vector for each node
- a hidden geometry where related nodes are close together
- a representation that can reconstruct observed edges
- a generalizable structure rather than a memorized adjacency list

In this pipeline, VGAE is used to:
- learn taxon and site embeddings
- support link prediction
- support downstream module discovery
- provide a latent substrate for retrieval and evidence packaging

The objective has two main parts:
- edge reconstruction
- KL regularization

KL regularization keeps the latent space from becoming chaotic. It encourages the latent distribution to stay close to a simple prior, so the model learns a smoother and more stable hidden map.

### DiffPool

DiffPool learns hierarchical soft clustering.

It does not primarily learn a coordinate space. It learns:
- how to assign nodes to clusters
- how to pool clusters into higher-level clusters
- how to represent module structure at multiple levels

In this pipeline, DiffPool is used to:
- produce site-wise soft assignments
- derive consensus modules
- estimate assignment entropy
- evaluate whether module calls are stable across sites

So VGAE is more about hidden geometry, while DiffPool is more about grouping and hierarchy.

## Latent Graph Geometry

The phrase “latent graph geometry” means the hidden coordinate space learned by the model.

You can think of it like this:
- the real graph is the visible network of edges
- the latent space is an invisible map
- points in the map represent taxa or sites
- proximity in the map means the model thinks the nodes behave similarly or connect similarly

This is not the graph itself. It is the model’s explanation of the graph.

## KL Regularization

KL means Kullback-Leibler divergence.

In this context it is a penalty that keeps the learned latent distribution from drifting too far away from a simple prior distribution.

Practical interpretation:
- without KL, the model can memorize too closely
- with KL, the model is forced to keep the hidden space smooth and regular
- that usually improves generalization and makes embeddings more usable

So KL regularization is not the graph space. It is a constraint on the graph space.

## What the Learned Outputs Are Used For

### Embeddings

The latent vectors from VGAE are saved and then used for:
- clustering taxa into modules
- nearest-neighbor lookup
- link prediction
- retrieval support

### Module calls

The pipeline writes:
- `vgae_taxon_modules.tsv`
- `diffpool_consensus_modules.tsv`

These are not direct biological truths. They are learned partitions or soft partitions of the taxa under the current graph and threshold settings.

### Link prediction

The link predictor uses the learned embeddings to score plausible:
- taxon-taxon links
- taxon-site links

These are hypotheses, not observations.

### Evidence cards

The evidence cards package:
- sample context
- site graph context
- taxon context
- module summaries
- predicted links

They are the interface between the learned graph and the query system.

## What the Evidence Cards Are

They are not just module membership statements.

They are compact grounded records that can represent:
- observed sample facts
- site-level graph summaries
- taxon annotations
- learned module membership
- predicted links

So they combine observed and learned evidence in one place.

Important distinction:
- module cards summarize learned clusters
- taxon cards include learned memberships and linked evidence
- predicted-link cards are hypotheses about connectedness

## Retrieval and Query Logic

The search layer is not transformer-based NLP.

It uses:
- TF-IDF over card text
- n-grams
- cosine similarity
- simple intent routing
- graph-based and abundance-based postprocessing

This is lexical retrieval plus rule-based query routing.

There is also a separate nearest-neighbor search over VGAE embeddings, but that is graph similarity search, not text NLP.

## What the Permissive Run Tells Us About Saturation

The permissive run is the right test for saturation because it deliberately expanded the feature set.

What we saw:
- graph edge counts increased a lot
- the graph remained tractable
- link prediction still produced usable AUC values
- the downstream system did not collapse

That suggests the pipeline can tolerate a more permissive matrix, at least at `prev_10`.

This does not prove the permissive setting is biologically preferable. It only shows that it is computationally and structurally usable for exploration.

## Practical Interpretation of the ML Stack

Use this mental model:

- **VGAE** learns a hidden map of the graph
- **DiffPool** learns how to group nodes into modules
- **Link prediction** turns hidden similarity into hypotheses
- **Evidence cards** turn those hypotheses into readable grounded records
- **TF-IDF retrieval** finds relevant cards from a query
- **The query engine** turns retrieved evidence into a structured answer

## Important Caveats

- These are learned representations, not direct biological truth.
- Module membership is model-dependent.
- Predicted links are hypotheses, not validated interactions.
- High density does not automatically mean better biology.
- A more permissive prevalence rule may increase sensitivity while also increasing artifact risk.
- The local browser and query layer are only as good as the underlying evidence cards and learned summaries.

## Where to Look in the Repo

Key files:
- `scripts/07_ngraph_train_vgae.py`
- `scripts/08_ngraph_train_diffpool.py`
- `scripts/09_ngraph_deep_module_summary.R`
- `scripts/10_ngraph_link_prediction.py`
- `scripts/11_ngraph_build_evidence_cards.R`
- `scripts/12_ngraph_build_retrieval_index.py`
- `scripts/13_ngraph_query_engine.py`
- `scripts/14_ngraph_local_browser.py`

Key outputs for the permissive branch:
- `results/ngraph/permissive_hybrid_prev10/deep_modules/`
- `results/ngraph/permissive_hybrid_prev10/deep_knowledge_discovery/`
- `NGRAPH_SUMMARY_permissive_hybrid_prev10.md`

## Bottom Line

The ML stack is not one model. It is a layered pipeline:
- graph construction
- latent geometry learning
- hierarchical clustering
- hypothesis generation
- evidence packaging
- retrieval and query

The permissive branch showed that the system can handle a much larger feature set without breaking, which makes it a valid exploration setting for future saturation and KG work.

