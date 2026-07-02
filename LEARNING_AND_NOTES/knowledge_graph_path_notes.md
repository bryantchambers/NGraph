# Path From Heterograph to Learnable Knowledge Graph

## Purpose

This note captures the discussion about how the current heterograph can evolve into a more explicit knowledge graph.

The current graph is already useful, but it is still mainly a statistical graph:
- `Site` nodes
- `Taxon` nodes
- learned similarity and association edges
- learned modules and predicted links

To become a real knowledge graph, it needs semantic typing, ontology grounding, provenance, and explicit statement structure.

## Short Answer

Yes, the current heterograph can hold:
- site metadata
- isotope fractions
- biosynthetic gene clusters
- metabolic information
- functional annotations
- ontology-backed entities and relations

So the heterograph is a good substrate for a KG.

But a heterograph alone is not yet a full knowledge graph.

## Heterograph vs Knowledge Graph

### Heterograph

A heterograph is a graph with multiple node and edge types.

It answers questions like:
- which taxa co-vary?
- which sites are similar?
- which taxa belong to a learned module?
- which links are likely missing?

This is relational structure, but it is not yet fully semantic.

### Knowledge Graph

A knowledge graph is a graph where:
- nodes have explicit meaning
- edges have typed semantics
- facts carry provenance
- entities map to ontologies or canonical identifiers
- observed facts and inferred facts are distinguishable

That extra semantic layer is what makes it a KG.

## What Is Missing Right Now

The current graph mainly captures:
- taxa
- sites
- samples indirectly
- association structure
- learned embeddings
- learned modules
- predicted links

What is still missing for full KG behavior:

### 1. Explicit semantic types

You want node types such as:
- `Taxon`
- `Site`
- `Sample`
- `DepthInterval`
- `TimeInterval`
- `Gene`
- `Pathway`
- `Reaction`
- `Compound`
- `BiosyntheticGeneCluster`
- `IsotopeMeasurement`
- `EnvironmentalMeasurement`

And edge types such as:
- `observed_in`
- `measured_in`
- `derived_from`
- `annotated_as`
- `has_function`
- `encodes`
- `part_of`
- `produces`
- `consumes`
- `located_at`
- `supports`
- `inferred_to_interact_with`

### 2. Ontology alignment

To make the graph machine-interpretable, map concepts to ontology terms where possible.

Examples:
- taxa -> NCBI Taxonomy or GTDB
- environments -> ENVO
- compounds -> ChEBI
- functions -> GO, KEGG, EC, MetaCyc, or a project-specific functional ontology
- samples and provenance -> metadata standards and controlled vocabularies

Ontology alignment gives shared meaning.

### 3. Provenance

Every statement should know where it came from.

For example:
- observed from an assay
- computed from abundance data
- inferred by VGAE
- predicted by link model
- imported from metadata
- mapped from literature

This matters a lot for ancient DNA because inference layers can easily be confused with direct observation if provenance is not explicit.

### 4. Confidence and uncertainty

A KG should not only say that something is true.
It should also say:
- how strongly it is supported
- what method produced it
- what threshold was used
- what sample window it came from
- whether it is observed or inferred

This is critical for paleoenvironments, where many facts are probabilistic.

## Can Biolanguage Models Turn It Into a KG?

Not by themselves.

Biolanguage models are useful, but they do not create a KG automatically.

### What biolanguage models can help with

- naming and entity linking
- semantic annotation
- literature retrieval
- text-to-ontology mapping
- query expansion
- summarization
- relation suggestion

### What they cannot replace

- explicit graph schema
- ontology mapping
- provenance
- identifier normalization
- typed edges
- curated fact structure

So biolanguage models are useful as helpers, not as substitutes for KG design.

## What the KG Should Contain

You asked whether we can add more information. Yes, and we should.

### Site metadata

Add things like:
- water depth
- location
- core ID
- age
- sedimentation rate
- MIS
- SST
- redox
- oxygen state
- lithology
- salinity

These can be:
- node attributes on `Site`
- `Measurement` nodes
- edges from samples or sites to measurements

### Isotope fractions

Add values like:
- `δ13C`
- `δ15N`
- `δ18O`
- `C/N`
- radiocarbon or age-model values

These can be:
- numeric attributes
- separate measurement nodes
- assay-linked evidence nodes

### Biosynthetic gene clusters

Represent BGCs as nodes.

Possible relations:
- `Taxon -> encodes -> BGC`
- `BGC -> predicted_to_produce -> Compound`
- `BGC -> detected_in -> Sample`
- `BGC -> associated_with -> Environment`

### Metabolic information

Represent:
- pathways
- enzymes
- reactions
- metabolites
- modules

Possible relations:
- `Taxon -> has_pathway -> Pathway`
- `Taxon -> encodes -> Enzyme`
- `Enzyme -> catalyzes -> Reaction`
- `Reaction -> produces -> Compound`
- `Pathway -> part_of -> HigherOrderPathway`

### Functional annotations

Represent:
- ecological roles
- TEA states
- KEGG-like functional states
- guild tiers
- module-level functional summaries

These can sit either as attributes or as ontology-linked nodes, depending on how fine-grained you want the KG to be.

## Can All of This Live in the Heterograph?

Yes.

In practice, the heterograph is a good general container for:
- typed nodes
- typed edges
- numeric attributes
- learned embeddings
- observational and inferred facts

That means the heterograph can be the storage and computation substrate for the KG.

## What Makes It a True KG Rather Than Just a Bigger Graph

The graph becomes a true KG when it has these properties:

### 1. Canonical IDs

Every entity should have a stable identifier.

### 2. Typed relations

Edges should say what relationship they represent, not just “connected.”

### 3. Provenance

Every edge or assertion should know whether it is:
- observed
- inferred
- predicted
- annotated

### 4. Ontology grounding

The graph should map to external vocabularies where possible.

### 5. Queryability

You should be able to ask semantic questions like:
- which taxa are associated with sulfate reduction in low-oxygen sites?
- which BGCs are enriched in a site module?
- which taxa are supported by isotope evidence and damage evidence?
- which pathways co-occur with a given environmental state?

### 6. Reasoning support

The KG should support paths, joins, and inference over semantic relations.

## A Good Architecture for the Future

I think the cleanest structure is three layers:

### Layer 1: empirical heterograph

This is the current graph:
- taxa
- sites
- samples
- site similarity
- taxon similarity
- learned modules
- predicted links

### Layer 2: semantic KG overlay

Add:
- ontology-aligned entity nodes
- measured metadata
- isotope nodes
- pathway nodes
- BGC nodes
- compound nodes
- provenance-rich typed edges

### Layer 3: inference and exploration layer

Add:
- embeddings
- link prediction
- module discovery
- literature-based enrichment
- LLM-assisted query support

This keeps the empirical data honest while allowing semantics and inference to grow.

## What the Learnable KG Would Be Used For

Once the KG is built, we should be able to ask:
- what taxa are associated with which environments?
- what functions are likely active in which sediment intervals?
- which modules correspond to particular geochemical states?
- which lineages carry certain pathways or BGCs?
- which taxa have both direct evidence and inferred support?
- which biological patterns are stable across sites and which are site-specific?

That is the direction toward a learnable KG.

## Design Principles to Keep in Mind

### Separate observation from inference

Do not let a prediction look like a measurement.

### Keep provenance visible

Always know where a fact came from.

### Use ontologies early

They help prevent the graph from becoming a pile of ad hoc labels.

### Preserve uncertainty

Ancient DNA evidence is often partial, noisy, and threshold-dependent.

### Keep the empirical graph and semantic graph connected

The KG should not replace the data graph. It should sit on top of it.

## Practical Next Steps

1. Define a KG schema for nodes and edges.
2. Decide which concepts are attributes and which are nodes.
3. Map core entities to ontology identifiers.
4. Add provenance fields to every learned and observed relation.
5. Extend the heterograph to include samples, measurements, functions, metabolites, pathways, and BGCs.
6. Keep the current learned graph layer intact so the KG can reuse it.
7. Build query paths that combine graph structure and semantic constraints.

## Bottom Line

Yes, the current heterograph can be expanded into a true knowledge graph.

Biolanguage models will help with annotation, linking, retrieval, and summarization, but the real transition comes from:
- ontology grounding
- typed relations
- provenance
- confidence
- explicit semantics

That is the path to a learnable KG.

