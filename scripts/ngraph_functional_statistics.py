"""Taxon-level capability enrichment with explicit conditional nulls.

Genes are reference evidence, never independent observations. The primary null
shuffles whole capability rows, retaining their co-occurrence and module sizes.
This is a coarsened taxonomy/detection-conditioned exploratory test, not a full
phylogenetic model or a measurement of metabolic activity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, beta

SEED = 42


def bh_adjust(p_values):
    p = np.asarray(p_values, dtype=float)
    result = np.full(p.shape, np.nan)
    if np.isinf(p).any() or ((p[np.isfinite(p)] < 0) | (p[np.isfinite(p)] > 1)).any():
        raise ValueError("p values must be missing or within [0,1]")
    valid = np.flatnonzero(np.isfinite(p))
    if not len(valid):
        return result
    order = valid[np.argsort(p[valid], kind="stable")]
    corrected = p[order] * len(order) / np.arange(1, len(order) + 1)
    result[order] = np.minimum(1, np.minimum.accumulate(corrected[::-1])[::-1])
    return result


@dataclass(frozen=True)
class Requirement:
    kind: str
    children: tuple = ()
    value: str = ""


class ModuleDefinition:
    """Parse KEGG AND steps, alternatives, complexes and optional subunits.

    Whitespace separates essential steps; '+' denotes a required complex;
    commas denote alternatives. '--' and unsupported identifiers remain
    unresolved. Completeness counts fulfilled essential steps on the best
    supported route, not a proportion of individual KO hits.
    """
    def __init__(self, text):
        self.text = str(text).strip()
        self.tokens = re.findall(r"K\d{5}|M\d{5}|--|[(),+\-]|\s+|[^\s(),+\-]+", self.text)
        self.tokens = [" " if x.isspace() else x for x in self.tokens]
        self.index = 0
        self.tree = self._and()
        self._spaces()
        if self.index != len(self.tokens):
            raise ValueError(f"Unparsed KEGG definition: {self.text}")

    def _spaces(self):
        while self.index < len(self.tokens) and self.tokens[self.index] == " ":
            self.index += 1

    def _peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _or(self):
        terms = [self._complex()]
        while self._peek() == ",":
            self.index += 1
            terms.append(self._complex())
        return terms[0] if len(terms) == 1 else Requirement("or", tuple(terms))

    def _and(self):
        self._spaces()
        terms = [self._or()]
        while self._peek() == " ":
            self._spaces()
            if self._peek() in (None, ")", ","):
                break
            terms.append(self._or())
        return terms[0] if len(terms) == 1 else Requirement("and", tuple(terms))

    def _complex(self):
        terms = [self._atom()]
        while self._peek() in ("+", "-"):
            optional = self._peek() == "-"
            self.index += 1
            item = self._atom()
            terms.append(Requirement("optional", (item,)) if optional else item)
        return terms[0] if len(terms) == 1 else Requirement("complex", tuple(terms))

    def _atom(self):
        self._spaces()
        token = self._peek()
        if token is None or token in (",", ")", "+"):
            raise ValueError(f"Missing requirement in {self.text}")
        self.index += 1
        if token == "(":
            item = self._route_or()
            self._spaces()
            if self._peek() != ")":
                raise ValueError(f"Unbalanced KEGG definition: {self.text}")
            self.index += 1
            return item
        if token == "-":
            return Requirement("optional", (self._atom(),))
        return Requirement("ko" if re.fullmatch(r"K\d{5}", token) else "unknown", value=token)

    def _route_or(self):
        # Within an explicit parenthesized route, commas separate whole routes:
        # ((K1,K2) K3,K4) permits K4 alone. Outside parentheses the common bare
        # K1,K2 K3 form is an alternative first step followed by essential K3.
        terms = [self._route_and()]
        while self._peek() == ",":
            self.index += 1
            terms.append(self._route_and())
        return terms[0] if len(terms) == 1 else Requirement("or", tuple(terms))

    def _route_and(self):
        self._spaces()
        terms = [self._complex()]
        while self._peek() == " ":
            self._spaces()
            if self._peek() in (None, ")", ","): break
            terms.append(self._complex())
        return terms[0] if len(terms) == 1 else Requirement("and", tuple(terms))

    def evaluate(self, kos: Iterable[str]):
        kos = set(kos)
        def prune(states):
            # Retain the maximal fulfilled count at EACH possible route length.
            # Choosing local fractions can select the wrong whole-path route.
            best = {}
            for present, required, unknown, missing in states:
                key = (required, unknown)
                value = (present, required, unknown, missing)
                if key not in best or (present,-len(missing),sorted(missing)) > (best[key][0],-len(best[key][3]),sorted(best[key][3])):
                    best[key] = value
            return list(best.values())
        def visit(node):
            if node.kind == "ko":
                return [(int(node.value in kos), 1, False, frozenset() if node.value in kos else frozenset([node.value]))]
            if node.kind == "unknown":
                return [(0, 1, True, frozenset())]
            if node.kind == "optional":
                return [(0, 0, False, frozenset())]
            children = [visit(c) for c in node.children]
            if node.kind == "or":
                return prune([s for alternatives in children for s in alternatives])
            states = [(0,0,False,frozenset())]
            for options in children:
                states = prune([(p+a,r+b,u or v,missing | absent)
                    for p,r,u,missing in states for a,b,v,absent in options])
            if node.kind == "complex":
                return prune([(int(p==r and not u),1,u,missing) for p,r,u,missing in states if r>0]) or [(0,0,False,frozenset())]
            return states
        states = visit(self.tree)
        present, required, unknown, missing = max(states,key=lambda v:(v[0]/max(v[1],1),not v[2],-len(v[3])))
        complete = any(r and p==r and not u for p,r,u,_ in states)
        unresolved = not complete and any(u for _,_,u,_ in states)
        completeness = present / required if required else np.nan
        return {"completeness": completeness, "is_complete": complete,
                "unresolved_definition": unresolved, "essential_steps": required,
                "fulfilled_steps": present, "missing_kos": sorted(missing)}


def matched_groups(metadata, min_child=20, *, extra_covariates=(), extra_strata=()):
    """Freeze domain/phylum/support; coarsen detection covariates only.

    Duplicate/tied covariate values never split into arbitrary different bins.
    KO richness is deliberately absent from the primary matching variables.
    """
    frame = metadata.reset_index(drop=True).copy()
    for column in ("domain", "phylum", "tad_support", *extra_strata):
        frame[column] = frame[column].fillna("unknown").astype(str)
    cov = frame[["prevalence_samples", "physical_core_count", *extra_covariates]].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(cov).all() or (cov < 0).any():
        raise ValueError("Matching covariates must be known finite nonnegative values")
    scale = cov.std(axis=0)
    scale[scale == 0] = 1
    cov = (cov - cov.mean(axis=0)) / scale
    groups = []
    def split(indices):
        dispersion = np.std(cov[indices], axis=0)
        # Stable sorting breaks dispersion ties in favour of prevalence.
        for column in np.argsort(-dispersion, kind="stable"):
            values = cov[indices, column]
            median = np.median(values)
            left, right = indices[values <= median], indices[values > median]
            if len(left) >= min_child and len(right) >= min_child:
                split(left); split(right)
                return
        groups.append(np.asarray(indices, dtype=int))
    for _, members in frame.groupby(["domain", "phylum", "tad_support", *extra_strata], sort=True, dropna=False):
        split(members.index.to_numpy())
    return groups


def exchangeable_fraction(labels, groups, module):
    mask = np.asarray(labels) == module
    denominator = int(mask.sum())
    if not denominator:
        return 0.0
    exchangeable = sum(int(mask[g].sum()) for g in groups if len(np.unique(np.asarray(labels)[g])) > 1)
    return exchangeable / denominator


def ks_high_affinity(scores, carriers):
    """One-sided carrier/noncarrier ECDF difference, preserving ties."""
    scores = np.asarray(scores, dtype=float)
    carriers = np.asarray(carriers, dtype=bool)
    finite = np.isfinite(scores)
    scores, carriers = scores[finite], carriers[finite]
    if carriers.sum() == 0 or (~carriers).sum() == 0:
        return np.nan
    values = np.unique(scores)
    positive = np.searchsorted(np.sort(scores[carriers]), values, side="right") / carriers.sum()
    negative = np.searchsorted(np.sort(scores[~carriers]), values, side="right") / (~carriers).sum()
    return float(np.max(negative - positive))


def enrich_capabilities(carriage, labels, metadata, *, permutations=None, seed=SEED,
                        annotation_coverage=None, min_global_carriers=5, min_members=20,
                        min_coverage=.70, min_exchangeable=.50, progress=None, annotation_burden_sensitivity=False, declared_modules=None):
    """Return the complete primary family and an exact Fisher baseline.

    Columns/functions are filtered by GLOBAL carrier and noncarrier support,
    never by observed module enrichment. Permutations are fixed before testing.
    """
    if carriage.index.has_duplicates or carriage.columns.has_duplicates:
        raise ValueError("Duplicate annotation units or function identifiers")
    if isinstance(labels,pd.Series) and not labels.index.equals(carriage.index):
        raise ValueError("Membership index does not match annotation units")
    if np.asarray(pd.isna(labels)).any():
        raise ValueError("Unknown module memberships are not testable")
    labels = np.asarray(labels, dtype=str)
    if len(labels) != len(carriage) or len(metadata) != len(labels):
        raise ValueError("Unaligned carriage, memberships and matching metadata")
    if carriage.isna().any().any():
        raise ValueError("Unknown annotations must be removed from the eligible universe")
    values=carriage.to_numpy()
    if not ((values==0)|(values==1)).all():
        raise ValueError("Capability carriage must contain explicit binary decisions")
    modules = sorted(set(declared_modules) if declared_modules is not None else np.unique(labels))
    if not set(labels)<=set(modules):
        raise ValueError("Observed module is outside the declared correction family")
    counts = carriage.astype(bool).sum(axis=0)
    eligible = (counts >= min_global_carriers) & ((len(labels) - counts) >= min_global_carriers)
    carriage = carriage.loc[:, eligible].astype(bool)
    functions = carriage.columns.tolist()
    H = len(modules) * len(functions)
    B = int(permutations) if permutations is not None else max(100000, 400 * H)
    if B < 1:
        raise ValueError("Permutation budget must be positive")
    if not H:
        return pd.DataFrame(), {"hypotheses": 0, "permutations": 0, "seed": seed}
    groups = matched_groups(metadata,extra_covariates=("ko_richness",) if annotation_burden_sensitivity else (),
                            extra_strata=("reference_quality_status",) if annotation_burden_sensitivity else ())
    matrix = carriage.to_numpy(dtype=np.int16)
    membership = np.vstack([labels == m for m in modules]).astype(np.int16)
    observed = membership.astype(np.int64) @ matrix
    exceed = np.zeros_like(observed, dtype=np.int64)
    rng = np.random.default_rng(seed)
    # Sufficient counts avoid materializing an entire shuffled gene inventory.
    # Annotation rows always move together for every capability.
    informative = [g for g in groups if len(np.unique(labels[g])) > 1]
    null_sum=np.zeros_like(observed,dtype=float)
    null_square_sum=np.zeros_like(observed,dtype=float)
    # Permuting memberships is algebraically equivalent to moving whole
    # annotation rows in the inverse permutation. Batch BLAS avoids repeatedly
    # allocating tiny integer products, while preserving every stratum margin.
    numeric_matrix=matrix.astype(float)
    next_progress=10000
    for offset in range(0,B,128):
        batch=min(128,B-offset)
        orders=np.broadcast_to(np.arange(len(labels)),(batch,len(labels))).copy()
        for group in informative:
            orders[:,group]=rng.permuted(np.broadcast_to(group,(batch,len(group))),axis=1)
        permuted_membership=membership[:,orders].transpose(1,0,2).reshape(batch*len(modules),len(labels)).astype(float)
        simulated=(permuted_membership @ numeric_matrix).reshape(batch,len(modules),len(functions))
        exceed+=(simulated>=observed[None,:,:]).sum(axis=0)
        null_sum+=simulated.sum(axis=0)
        null_square_sum+=np.square(simulated).sum(axis=0)
        if progress and offset+batch>=next_progress:
            progress(offset+batch,B);next_progress+=10000
    null_mean=null_sum/B
    null_variance=np.maximum(0,(null_square_sum-B*np.square(null_mean))/max(1,B-1))
    null_sd=np.sqrt(null_variance)
    z_score=np.divide(observed-null_mean,null_sd,out=np.full(observed.shape,np.nan),where=null_sd>0)
    rows = []
    coverage = annotation_coverage or {}
    total_counts = matrix.sum(axis=0)
    for mi, module in enumerate(modules):
        n = int(membership[mi].sum())
        outside = len(labels) - n
        exchangeable = exchangeable_fraction(labels, groups, module)
        for fi, function in enumerate(functions):
            a = int(observed[mi, fi]); b = n - a
            c = int(total_counts[fi]) - a; d = outside - c
            odds, fisher_p = fisher_exact([[a, b], [c, d]], alternative="greater")
            difference = a / n - c / outside if n and outside else np.nan
            rows.append(dict(module_id=module, function_id=function, test_method="matched_permutation",
                             carrier_count=a, module_annotated_count=n, background_carrier_count=c,
                             background_annotated_count=outside, odds_ratio=odds,
                             prevalence_difference=difference, statistic=difference,
                             p_value=(1 + exceed[mi, fi]) / (B + 1), fisher_p_value=fisher_p,
                             permutation_z_score=z_score[mi,fi],null_carrier_count_mean=null_mean[mi,fi],
                             null_carrier_count_sd=null_sd[mi,fi],
                             null_variance_status="variable" if null_sd[mi,fi]>0 else "zero_variance",
                             annotation_coverage=float(coverage.get(module, 1)),
                             exchangeable_fraction=exchangeable, permutations=B))
    result = pd.DataFrame(rows)
    result["q_value"] = bh_adjust(result.p_value)
    result["fisher_q_value"] = bh_adjust(result.fisher_p_value)
    # BY is a separately labelled arbitrary-dependence sensitivity, not the
    # declared BH primary procedure. Modules and pathways share carriers.
    harmonic=sum(1/i for i in range(1,len(result)+1))
    result["by_q_value"]=np.minimum(1,result.q_value*harmonic)
    successes=exceed.ravel()
    lower=np.where(successes==0,0,beta.ppf(.025,successes,B-successes+1))
    upper=np.where(successes==B,1,beta.ppf(.975,successes+1,B-successes))
    result["p_value_mc_lower"]=lower
    result["p_value_mc_upper"]=upper
    result["q_value_mc_upper_diagnostic"]=bh_adjust(upper)
    result["exceedance_count"]=successes
    result["minimum_attainable_p"]=1/(B+1)
    reasons = []
    for row in result.itertuples():
        failed = []
        if row.module_annotated_count < min_members: failed.append("insufficient_members")
        if row.annotation_coverage < min_coverage: failed.append("insufficient_coverage")
        if row.exchangeable_fraction < min_exchangeable: failed.append("null_not_informative")
        if row.carrier_count < 5: failed.append("insufficient_carriers")
        if not np.isfinite(row.prevalence_difference) or row.prevalence_difference < .10: failed.append("small_frequency_effect")
        if np.isnan(row.odds_ratio) or row.odds_ratio < 1.5: failed.append("small_odds_effect")
        if row.q_value > .05: failed.append("not_significant")
        elif row.q_value_mc_upper_diagnostic > .05: failed.append("monte_carlo_boundary_uncertain")
        reasons.append(";".join(failed) if failed else "qualified_exploratory")
    result["status"] = reasons
    result["publish_kg"] = result.status == "qualified_exploratory"
    group_records = [{"group_id": i, "members": list(map(int, g)),
                      "exchangeable": len(np.unique(labels[g])) > 1} for i, g in enumerate(groups)]
    return result, {"hypotheses": H, "permutations": B, "seed": seed, "groups": group_records,
                    "correction_family": "all_declared_network_modules_by_globally_eligible_KEGG_framework", "declared_modules": modules, "null": "matched_whole_annotation_rows",
                    "p_value_rule": "(1+exceedances)/(1+fixed_permutations)",
                    "minimum_attainable_p": 1/(B+1), "family_wise_first_rank_resolution": H/(B+1),
                    "mc_interval": "pointwise_95_percent_Clopper_Pearson; transformed_upper_q_is_diagnostic_not_simultaneous_FDR_bound",
                    "dependence_sensitivity": "Benjamini_Yekutieli_separate_from_primary_BH",
                    "annotation_burden_sensitivity": annotation_burden_sensitivity,
                    "z_score": "observed_minus_empirical_null_mean_over_empirical_null_sd; undefined_for_constant_null",
                    "abundance_weighting": False, "permutation_batch_size": 128}


def ks_statistics_matrix(scores, carriage):
    """All one-sided KS scores with a fixed sort and exact tie endpoints."""
    scores=np.asarray(scores,float); matrix=np.asarray(carriage,bool)
    if matrix.ndim!=2 or len(scores)!=len(matrix) or not np.isfinite(scores).all():
        raise ValueError("KS requires aligned finite scores and annotation rows")
    if not len(scores): return np.full(matrix.shape[1],np.nan)
    order=np.argsort(scores,kind="stable")
    endpoints=np.flatnonzero(np.r_[np.diff(scores[order])!=0,True])
    counts=matrix.sum(axis=0)
    cumulative=np.cumsum(matrix[order],axis=0,dtype=np.int64)[endpoints]
    with np.errstate(divide="ignore",invalid="ignore"):
        differences=((endpoints[:,None]+1-cumulative)/(len(scores)-counts))-cumulative/counts
    result=np.max(differences,axis=0)
    result[(counts==0)|(counts==len(scores))]=np.nan
    return result


def ks_enrichment(carriage, affinity, metadata, *, permutations=100000, seed=SEED, progress=None):
    """Matched empirical KS tests; one frozen finite universe per module.

    Sort/tie positions are fixed before permutations. Whole annotation rows
    move together; scores and pathway carrier totals are held fixed.
    """
    if not carriage.index.equals(affinity.index) or len(metadata)!=len(carriage):
        raise ValueError("Unaligned KS annotation, affinity or metadata units")
    if carriage.isna().any().any() or permutations<1:
        raise ValueError("KS requires known carriage and a positive fixed budget")
    rows=[];rng=np.random.default_rng(seed)
    for module in sorted(affinity.columns):
        finite=np.isfinite(affinity[module].to_numpy(float))
        scores=affinity.loc[finite,module].to_numpy(float)
        cap=carriage.loc[finite].astype(bool)
        meta=metadata.iloc[np.flatnonzero(finite)].reset_index(drop=True)
        if not len(cap): continue
        groups=matched_groups(meta)
        counts=cap.sum()
        columns=cap.columns[(counts>=5)&((len(cap)-counts)>=5)]
        if not len(columns): continue
        matrix=cap[columns].to_numpy(bool)
        order=np.argsort(scores,kind="stable")
        endpoints=np.flatnonzero(np.r_[np.diff(scores[order])!=0,True])
        totals=matrix.sum(axis=0)
        def statistics(values):
            cumulative=np.cumsum(values[order],axis=0,dtype=np.int64)[endpoints]
            return np.max((endpoints[:,None]+1-cumulative)/(len(scores)-totals)-cumulative/totals,axis=0)
        observed=statistics(matrix);exceed=np.zeros(len(columns),dtype=np.int64)
        for iteration in range(permutations):
            permuted=np.arange(len(matrix))
            for group in groups: permuted[group]=rng.permutation(group)
            simulated=statistics(matrix[permuted])
            exceed+=simulated>=observed
            if progress and (iteration+1)%10000==0: progress(module,iteration+1,permutations)
        for i,function in enumerate(columns):
            carriers=matrix[:,i]
            rows.append(dict(module_id=module,function_id=function,test_method="matched_ks",
                statistic=observed[i],p_value=(1+exceed[i])/(permutations+1),
                median_affinity_difference=float(np.median(scores[carriers])-np.median(scores[~carriers])),
                carrier_count=int(carriers.sum()),finite_affinity_universe=len(scores),
                permutations=permutations,exceedance_count=int(exceed[i]),publish_kg=False))
    result=pd.DataFrame(rows)
    if len(result):
        result["q_value"]=bh_adjust(result.p_value)
        result["by_q_value"]=np.minimum(1,result.q_value*sum(1/i for i in range(1,len(result)+1)))
    return result


def ko_fisher_baseline(carriage, labels, *, min_global_carriers=5):
    """Secondary exact KO over-representation; separate family and no KG gate."""
    if carriage.isna().any().any() or len(carriage)!=len(labels):
        raise ValueError("KO baseline requires known full-proteome units")
    if isinstance(labels,pd.Series) and not labels.index.equals(carriage.index):
        raise ValueError("KO membership index differs from annotation units")
    labels=np.asarray(labels,str);counts=carriage.astype(bool).sum()
    functions=carriage.columns[(counts>=min_global_carriers)&((len(labels)-counts)>=min_global_carriers)]
    rows=[]
    for module in sorted(set(labels)):
        inside=labels==module;n=int(inside.sum());outside=len(labels)-n
        for function in functions:
            a=int(carriage.loc[inside,function].sum());c=int(counts[function])-a
            odds,p=fisher_exact([[a,n-a],[c,outside-c]],alternative="greater")
            rows.append(dict(module_id=module,function_id=function,function_namespace="KEGG_KO",test_method="secondary_KO_Fisher",
                carrier_count=a,module_annotated_count=n,background_carrier_count=c,background_annotated_count=outside,
                odds_ratio=odds,p_value=p,publish_kg=False))
    result=pd.DataFrame(rows)
    if len(result):
        result["q_value"]=bh_adjust(result.p_value)
        result["by_q_value"]=np.minimum(1,result.q_value*sum(1/i for i in range(1,len(result)+1)))
    return result
