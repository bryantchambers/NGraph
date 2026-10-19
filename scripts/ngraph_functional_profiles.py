"""Depth profiles and graph centrality; neither is a causal activity measure."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import rankdata


def physical_core(core):
    return str(core).removesuffix("_R1").removesuffix("_R2")


def set_logratio(clr, members, universe=None):
    """Difference of means is invariant to the original CLR centering term."""
    universe = list(clr.columns if universe is None else universe)
    selected = [c for c in members if c in universe]
    other = [c for c in universe if c not in set(selected)]
    if not selected or not other:
        return pd.Series(np.nan, index=clr.index)
    return clr[selected].mean(axis=1) - clr[other].mean(axis=1)


def module_profiles(clr, abundance, metadata, memberships):
    meta = metadata.set_index("sample").reindex(clr.index)
    if meta.core.isna().any():
        raise ValueError("Missing core metadata for functional profile samples")
    rows = []
    for module, group in memberships.groupby("module_id", sort=True):
        taxa = [t for t in group.taxon if t in clr]
        ratios = set_logratio(clr, taxa)
        for sample in clr.index:
            info = meta.loc[sample]
            rows.append(dict(module_id=module, sample=sample, core=info.core,
                physical_core=physical_core(info.core), depth_cm=info.get("depth_in_core_cm", np.nan),
                y_bp=info.get("y_bp", np.nan), age_kyr=info.get("y_bp", np.nan)/1000,
                mean_clr=float(clr.loc[sample, taxa].mean()), module_logratio=ratios.loc[sample],
                module_members=len(taxa), detected_members=int((abundance.loc[sample, taxa]>0).sum()),
                abundance_mode=info.get("abundance_mode", "unknown"),
                status="observed_relative_module_profile"))
    return pd.DataFrame(rows)


def module_affinity(clr, abundance, metadata, memberships, *, min_levels=8, min_positive=5):
    """Equal physical-core affinity with leave-one-out member profiles.

    GeoB repeated libraries are averaged at their shared depth using EXISTING
    CLR values; global centering is preserved. No absent taxon gets a zero rank.
    """
    meta = metadata.set_index("sample").reindex(clr.index).copy()
    meta["physical_core"] = meta.core.map(physical_core)
    modules = memberships.groupby("module_id").taxon.apply(list).to_dict()
    accumulated = {module: {taxon: [] for taxon in clr.columns} for module in modules}
    support = []
    for core, samples in meta.groupby("physical_core", sort=True):
        valid = samples.depth_in_core_cm.notna()
        samples = samples.loc[valid]
        if len(samples) == 0: continue
        depths = samples.depth_in_core_cm
        x = clr.loc[samples.index].groupby(depths).mean().sort_index()
        a = abundance.loc[samples.index].groupby(depths).mean().reindex(x.index)
        if len(x) < min_levels: continue
        sd = x.std(ddof=0)
        eligible = (a.gt(0).sum() >= min_positive) & sd.gt(0) & np.isfinite(sd)
        z = (x.loc[:, eligible] - x.loc[:, eligible].mean()) / sd[eligible]
        for module, members in modules.items():
            local = [t for t in members if t in z]
            if len(local) < 4: continue
            total = z[local].sum(axis=1)
            for taxon in z:
                profile = (total-z[taxon])/(len(local)-1) if taxon in local else total/len(local)
                if profile.std(ddof=0) <= 0: continue
                correlation = float(np.corrcoef(z[taxon], profile)[0, 1])
                if np.isfinite(correlation):
                    accumulated[module][taxon].append(np.arctanh(np.clip(correlation, -.999999, .999999)))
                    support.append(dict(module_id=module,taxon=taxon,physical_core=core,affinity=correlation,
                                        unique_depths=len(z),positive_levels=int(a[taxon].gt(0).sum())))
    affinity = pd.DataFrame({m:{t:np.tanh(np.mean(v)) if v else np.nan for t,v in taxa.items()}
                             for m,taxa in accumulated.items()}).reindex(clr.columns)
    return affinity, pd.DataFrame(support)


def moving_block_indices(n, rng, block_length=None):
    length = min(n, block_length or max(1, int(np.ceil(np.sqrt(n)))))
    if n == 0: return np.array([], dtype=int)
    starts = rng.integers(0, n, size=int(np.ceil(n / length)))
    return np.concatenate([(s+np.arange(length)) % n for s in starts])[:n]


def module_centrality(edges, memberships, clr, abundance, metadata, *, bootstraps=200, seed=42, cutoff=.55):
    """Actual weighted edges; bootstrap ranks conditional on fixed membership.

    Normalize within-core positive strength by eligible module size minus one.
    R1/R2 resampling uses the same physical-depth blocks. Unsupported/isolated
    nodes can be displayed but never receive a stable central-candidate label.
    """
    rng = np.random.default_rng(seed)
    meta = metadata.set_index("sample").reindex(clr.index)
    assignment = memberships.set_index("taxon").module_id.to_dict()
    modules = memberships.groupby("module_id").taxon.apply(list).to_dict()
    core_data = {}
    physical_depths = {}
    for core, group in meta.groupby("core", sort=True):
        ordered = group.sort_values(["depth_in_core_cm", "y_bp"], kind="stable")
        samples = ordered.index
        x, a = clr.loc[samples], abundance.loc[samples]
        eligible = a.gt(0).sum().ge(5) & x.var(ddof=0).gt(0)
        core_data[core] = (x.loc[:, eligible], a, ordered)
        physical_depths.setdefault(physical_core(core), set()).update(ordered.depth_in_core_cm.dropna())
    bootstrap_indices = {}
    for core, depths in physical_depths.items():
        depths = sorted(depths)
        bootstrap_indices[core] = [np.asarray(depths)[moving_block_indices(len(depths),rng)] for _ in range(bootstraps)]
    rows = []
    for core, (x, a, ordered) in core_data.items():
        local_edges = edges.loc[edges.source_core == core]
        for module, members in modules.items():
            taxa = [t for t in members if t in x]
            if not taxa: continue
            lookup = {t:i for i,t in enumerate(taxa)}
            positive = np.zeros(len(taxa)); negative = np.zeros(len(taxa)); degree = np.zeros(len(taxa),dtype=int)
            for edge in local_edges.itertuples():
                if edge.taxon_from not in lookup or edge.taxon_to not in lookup: continue
                weight = float(edge.signed_weight)
                for taxon in (edge.taxon_from,edge.taxon_to):
                    i=lookup[taxon]; degree[i]+=1
                    if weight>0: positive[i]+=weight
                    else: negative[i]+=abs(weight)
            normalizer = max(1,len(taxa)-1)
            percentile = rankdata(positive, method="average")/len(taxa)
            rank_samples=[]
            values=x[taxa].to_numpy(float)
            raw_values=a[taxa].to_numpy(float)
            depth_to_rows={depth:np.flatnonzero(ordered.depth_in_core_cm.to_numpy()==depth)
                           for depth in ordered.depth_in_core_cm.dropna().unique()}
            for depths in bootstrap_indices[physical_core(core)]:
                indices=np.concatenate([depth_to_rows[d] for d in depths if d in depth_to_rows]) if any(d in depth_to_rows for d in depths) else np.array([],dtype=int)
                if len(indices)<3 or len(taxa)<2:
                    rank_samples.append(np.full(len(taxa),np.nan)); continue
                selected=values[indices]
                sd=selected.std(axis=0)
                # Reapply the graph's actual support/CLR-variance predicate.
                # Raw-constant profiles remain an explicit denominator QC
                # diagnostic, rather than an undocumented bootstrap filter.
                valid=(sd>0) & (np.ptp(selected,axis=0)>0) & np.isfinite(selected).all(axis=0) & ((raw_values[indices]>0).sum(axis=0)>=5)
                if valid.sum()<2:
                    rank_samples.append(np.full(len(taxa),np.nan)); continue
                standardized=np.zeros_like(selected)
                standardized[:,valid]=(selected[:,valid]-selected[:,valid].mean(axis=0))/sd[valid]
                correlations=standardized.T@standardized/len(selected)
                np.fill_diagonal(correlations,0)
                strengths=np.where(correlations>=cutoff,correlations,0).sum(axis=1)
                ranks=rankdata(strengths,method="average")/len(taxa)
                ranks[strengths<=0]=0
                ranks[~valid]=np.nan
                rank_samples.append(ranks)
            ranks=np.asarray(rank_samples)
            minimum=max(5,int(np.ceil(.10*len(x))))
            for i,taxon in enumerate(taxa):
                observed=int(a[taxon].gt(0).sum())
                frequency=float(np.mean(ranks[:,i]>=.90)) if len(ranks) else np.nan
                valid_ranks=ranks[:,i][np.isfinite(ranks[:,i])] if len(ranks) else np.array([])
                eligible=observed>=minimum
                rows.append(dict(module_id=module,taxon=taxon,core=core,physical_core=physical_core(core),
                    positive_strength=positive[i]/normalizer,negative_strength=negative[i]/normalizer,degree=int(degree[i]),
                    centrality_percentile=float(percentile[i]),n_positive_samples=observed,min_positive_samples=minimum,
                    eligible=eligible,bootstrap_top_decile_frequency=frequency,
                    rank_lower=float(np.quantile(valid_ranks,.025)) if len(valid_ranks) else np.nan,
                    rank_upper=float(np.quantile(valid_ranks,.975)) if len(valid_ranks) else np.nan,
                    central_candidate=bool(eligible and positive[i]>0 and frequency>=.8),
                    bootstrap_replicates=len(ranks),informative_bootstrap_replicates=len(valid_ranks),status="core_specific_conditional_centrality"))
    result=pd.DataFrame(rows)
    if len(result):
        aggregate=[]
        numeric=["positive_strength","negative_strength","degree","centrality_percentile",
                 "bootstrap_top_decile_frequency","rank_lower","rank_upper"]
        for (module,taxon),group in result.groupby(["module_id","taxon"],sort=True):
            physical=group.groupby("physical_core")[numeric].mean()
            values=physical.mean().to_dict()
            qualified=group.loc[group.eligible & group.positive_strength.gt(0)]
            values.update(module_id=module,taxon=taxon,core="all",physical_core="all",eligible=len(qualified)>0,
                n_positive_samples=int(group.n_positive_samples.sum()),min_positive_samples=5,
                central_candidate=bool(len(qualified)>0 and physical.bootstrap_top_decile_frequency.mean()>=.8),
                supporting_physical_cores=len(physical),bootstrap_replicates=bootstraps,
                status="equal_physical_core_summary")
            aggregate.append(values)
        result=pd.concat([result,pd.DataFrame(aggregate)],ignore_index=True)
    return result
