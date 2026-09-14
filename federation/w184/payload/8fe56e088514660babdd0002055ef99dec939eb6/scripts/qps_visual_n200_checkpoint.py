#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.linalg import eigh, eigvalsh, inv
from scipy.stats import chi2, spearmanr

FEATURES = [
    "typographic_hierarchy", "whitespace_grid", "figure_quality", "table_readability",
    "colour_discipline", "diagram_consistency", "branding_restraint", "captions_citations",
    "metadata_versioning", "export_print_fidelity", "information_density", "executive_legibility",
]
FORMATS = ["HTML", "PDF", "PPTX", "XLSX"]
POST_INPUTS = [
    ("W163", "ocd-adr/40_implementation/QPS_VISUAL_N104_PILOT_PROVENANCE.csv", 4),
    ("W169", "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W169_PROVENANCE.csv", 8),
    ("W170", "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W170_PROVENANCE.csv", 8),
    ("W173", "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W173_AUTH_RECONCILED.csv", 27),
    ("W174", "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W174_PROVENANCE.csv", 9),
    ("W176_PPTX", "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W176_PPTX_AUTH_RECONCILED.csv", 16),
    ("W176_XLSX", "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W176_XLSX_AUTH_RECONCILED.csv", 17),
    ("W176_HTML", "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W176_HTML_AUTH_RECONCILED.csv", 11),
]
N100_SHARDS = [f"ocd-adr/40_implementation/QPS_VISUAL_CENSUS_RAW_PROVENANCE_N112_{f}.csv" for f in FORMATS]
N100_MATRIX = "ocd-adr/40_implementation/QPS_VISUAL_CENSUS_DERIVED_ARTIFACT_N100.generated.csv"
N100_RECEIPT = "ocd-adr/40_implementation/QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json"


def fail(msg: str) -> None:
    raise SystemExit(f"W184_FAIL: {msg}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def bool_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(True, index=df.index)
    return df[col].astype(str).str.strip().str.lower().isin({"true", "1", "yes", "pass"})


def normalized_family(row: pd.Series) -> str:
    explicit = str(row.get("family_key", "")).strip()
    if explicit and explicit.lower() != "nan":
        return explicit.lower()
    artifact = str(row["artifact_id"]).strip().lower()
    return re.sub(r"\s+", "_", artifact)


def normalize_post(df: pd.DataFrame, cohort: str) -> pd.DataFrame:
    ren = {}
    if "source_hash" not in df.columns and "source_sha256" in df.columns:
        ren["source_sha256"] = "source_hash"
    if "render_hash" not in df.columns and "render_sha256" in df.columns:
        ren["render_sha256"] = "render_hash"
    if "observation_id" not in df.columns and "selection_id" in df.columns:
        ren["selection_id"] = "observation_id"
    df = df.rename(columns=ren).copy()
    required = ["observation_id", "artifact_id", "artifact_format", "source_hash", "render_hash", *FEATURES]
    missing = [c for c in required if c not in df.columns]
    if missing:
        fail(f"{cohort} missing columns {missing}")
    for c in ["observation_id", "artifact_id", "artifact_format", "source_hash", "render_hash"]:
        if df[c].isna().any() or df[c].astype(str).str.strip().eq("").any():
            fail(f"{cohort} blank identity/provenance value in {c}")
    if not bool_series(df, "content_parity_pass").all():
        fail(f"{cohort} contains content-parity non-PASS row")
    if not bool_series(df, "visual_release_eligible").all():
        fail(f"{cohort} contains visual-release ineligible row")
    numeric = df[FEATURES].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        fail(f"{cohort} contains missing/non-numeric visual feature")
    if ((numeric < 0) | (numeric > 10)).any().any():
        fail(f"{cohort} contains visual feature outside 0..10")
    df[FEATURES] = numeric
    df["artifact_format"] = df["artifact_format"].astype(str).str.upper().str.strip()
    if not set(df["artifact_format"]).issubset(FORMATS):
        fail(f"{cohort} contains unknown format {sorted(set(df['artifact_format']) - set(FORMATS))}")
    df["cohort"] = cohort
    df["family_exact_key"] = df.apply(normalized_family, axis=1)
    return df


def metrics(df: pd.DataFrame) -> dict:
    X = df[FEATURES].to_numpy(float)
    n, p = X.shape
    Z = (X - X.mean(0)) / X.std(0, ddof=1)
    R = np.corrcoef(Z, rowvar=False)
    if not np.isfinite(R).all():
        fail("non-finite correlation matrix")
    Ri = inv(R)
    P = np.empty_like(R)
    for i in range(p):
        for j in range(p):
            P[i, j] = 1.0 if i == j else -Ri[i, j] / math.sqrt(Ri[i, i] * Ri[j, j])
    r2 = np.sum(np.triu(R, 1) ** 2)
    p2 = np.sum(np.triu(P, 1) ** 2)
    kmo = float(r2 / (r2 + p2))
    msa = []
    for i in range(p):
        rr = np.delete(R[i] ** 2, i).sum()
        pp = np.delete(P[i] ** 2, i).sum()
        msa.append(float(rr / (rr + pp)))
    det = float(np.linalg.det(R))
    if det <= 0:
        fail(f"non-positive correlation determinant {det}")
    bartlett_chi2 = float(-(n - 1 - (2 * p + 5) / 6) * np.log(det))
    bartlett_df = p * (p - 1) // 2
    bartlett_p = float(chi2.sf(bartlett_chi2, bartlett_df))
    vals, vecs = eigh(R)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    loadings = vecs * np.sqrt(vals)
    for j in range(p):
        if loadings[:, j].sum() < 0:
            loadings[:, j] *= -1
            vecs[:, j] *= -1
    means = X.mean(0)
    pressure = 0.7 * (10 - means) + 0.3 * np.abs(loadings[:, 0]) * 10
    ranks = np.empty(p, int)
    for pos, idx in enumerate(np.argsort(pressure)[::-1], 1):
        ranks[idx] = pos
    return {
        "X": X, "Z": Z, "R": R, "eigenvalues": vals, "loadings": loadings,
        "means": means, "pressure": pressure, "ranks": ranks,
        "KMO": kmo, "MSA": msa, "bartlett_chi2": bartlett_chi2,
        "bartlett_df": bartlett_df, "bartlett_p": bartlett_p,
    }


def congruence(a: np.ndarray, b: np.ndarray) -> float:
    if np.dot(a, b) < 0:
        a = -a
    return float(np.dot(a, b) / np.sqrt(np.dot(a, a) * np.dot(b, b)))


def parallel95() -> dict[int, np.ndarray]:
    p = len(FEATURES)
    rng = np.random.default_rng(777)
    out = {}
    for n in [60, 80, 100, 200]:
        eig = np.empty((5000, p))
        for s in range(5000):
            Y = rng.standard_normal((n, p))
            Y = (Y - Y.mean(0)) / Y.std(0, ddof=1)
            eig[s] = eigvalsh(np.corrcoef(Y, rowvar=False))[::-1]
        out[n] = np.quantile(eig, 0.95, axis=0)
    return out


def collision_values(series: pd.Series) -> list[str]:
    vc = series.astype(str).value_counts()
    return sorted(vc[vc > 1].index.tolist())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output-dir", type=Path, default=Path("artifacts/w184_n200_checkpoint"))
    args = ap.parse_args()
    root = args.repo_root.resolve()
    out = args.output_dir
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)

    matrix_path = root / N100_MATRIX
    receipt_path = root / N100_RECEIPT
    if not matrix_path.is_file():
        fail(f"missing generated frozen N100 matrix; run ocd-adr/40_implementation/qps_visual_pca_generate_all.py first: {matrix_path}")
    if not receipt_path.is_file():
        fail(f"missing frozen N100 generation receipt: {receipt_path}")
    frozen_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if frozen_receipt.get("artifact_N") != 100 or frozen_receipt.get("format_counts") != {f: 25 for f in FORMATS}:
        fail("frozen N100 generation receipt is not exact balanced 25/format N100")

    n100 = pd.read_csv(matrix_path)
    if len(n100) != 100:
        fail(f"generated N100 matrix row count {len(n100)} != 100")
    if n100["artifact_format"].value_counts().to_dict() != {f: 25 for f in FORMATS}:
        fail(f"generated N100 matrix is not 25/format: {n100['artifact_format'].value_counts().to_dict()}")
    if n100[FEATURES].apply(pd.to_numeric, errors="coerce").isna().any().any():
        fail("generated N100 matrix feature missingness")

    raw_n100 = []
    input_hashes = {N100_MATRIX: sha256(matrix_path), N100_RECEIPT: sha256(receipt_path)}
    for rel in N100_SHARDS:
        p = root / rel
        if not p.is_file():
            fail(f"missing frozen N100 shard {rel}")
        d = pd.read_csv(p)
        for c in ["artifact_id", "artifact_format", "source_hash", "render_hash"]:
            if c not in d.columns:
                fail(f"N100 shard {rel} missing {c}")
        raw_n100.append(d)
        input_hashes[rel] = sha256(p)
    raw_n100 = pd.concat(raw_n100, ignore_index=True)
    frozen_source = set(raw_n100["source_hash"].astype(str))
    frozen_render = set(raw_n100["render_hash"].astype(str))
    frozen_artifact = set((raw_n100["artifact_format"].astype(str).str.upper() + "::" + raw_n100["artifact_id"].astype(str)).tolist())

    post_parts = []
    cohort_counts = {}
    for cohort, rel, expected in POST_INPUTS:
        p = root / rel
        if not p.is_file():
            fail(f"missing post-N100 accepted input {rel}")
        d = normalize_post(pd.read_csv(p), cohort)
        if len(d) != expected:
            fail(f"{cohort} row count {len(d)} != expected {expected}")
        post_parts.append(d)
        cohort_counts[cohort] = len(d)
        input_hashes[rel] = sha256(p)
    post = pd.concat(post_parts, ignore_index=True)

    if len(post) != 100:
        fail(f"post-N100 accepted row count {len(post)} != 100")
    post_counts = post["artifact_format"].value_counts().to_dict()
    if post_counts != {f: 25 for f in FORMATS}:
        fail(f"post-N100 balance gate failed: {post_counts}")
    if post["observation_id"].duplicated().any():
        fail(f"duplicate post-N100 observation IDs: {sorted(post.loc[post['observation_id'].duplicated(False),'observation_id'].astype(str).unique())}")

    post_source_dups = collision_values(post["source_hash"])
    post_render_dups = collision_values(post["render_hash"])
    if post_source_dups:
        fail(f"duplicate source_hash within post-N100 accepted population: {post_source_dups}")
    if post_render_dups:
        fail(f"duplicate render_hash within post-N100 accepted population: {post_render_dups}")
    frozen_source_collision = sorted(set(post["source_hash"].astype(str)) & frozen_source)
    frozen_render_collision = sorted(set(post["render_hash"].astype(str)) & frozen_render)
    if frozen_source_collision:
        fail(f"post-N100 source_hash collision with frozen N100: {frozen_source_collision}")
    if frozen_render_collision:
        fail(f"post-N100 render_hash collision with frozen N100: {frozen_render_collision}")

    post_artifact_key = post["artifact_format"].astype(str) + "::" + post["artifact_id"].astype(str)
    artifact_dups = collision_values(post_artifact_key)
    if artifact_dups:
        fail(f"duplicate artifact key within post-N100 accepted population: {artifact_dups}")
    frozen_artifact_collision = sorted(set(post_artifact_key) & frozen_artifact)
    if frozen_artifact_collision:
        fail(f"post-N100 artifact key collision with frozen N100: {frozen_artifact_collision}")

    # Exact-family gate: use explicit family_key where governed; otherwise exact normalized artifact_id.
    # This is intentionally narrower than semantic/version-family inference. Every input tranche already
    # passed its governed family-version admission gate; this global checkpoint does not invent missing N100 family labels.
    family_key = post["artifact_format"].astype(str) + "::" + post["family_exact_key"].astype(str)
    family_dups = collision_values(family_key)
    if family_dups:
        fail(f"duplicate exact family key within post-N100 accepted population: {family_dups}")

    post_matrix = post[["artifact_format", "artifact_id", *FEATURES]].copy()
    post_matrix.insert(0, "cohort", post["cohort"].values)
    n100_matrix = n100[["artifact_format", "artifact_id", *FEATURES]].copy()
    n100_matrix.insert(0, "cohort", "N100_CONTROL")
    combined = pd.concat([n100_matrix, post_matrix], ignore_index=True)
    combined_counts = combined["artifact_format"].value_counts().to_dict()
    if len(combined) != 200 or combined_counts != {f: 50 for f in FORMATS}:
        fail(f"combined N200 balance failed N={len(combined)} counts={combined_counts}")
    combined.insert(0, "derived_observation_id", [f"N200-P{i:03d}" for i in range(1, 201)])

    m100 = metrics(n100)
    m200 = metrics(combined)
    p = len(FEATURES)
    pa = parallel95()[200]
    retained = m200["eigenvalues"] > pa
    load_congruence = [congruence(m200["loadings"][:, i], m100["loadings"][:, i]) for i in range(3)]
    pressure_rho = float(spearmanr(m200["ranks"], m100["ranks"]).statistic)
    pc1_drift_pp = float(abs(m200["eigenvalues"][0] / p * 100 - m100["eigenvalues"][0] / p * 100))
    pc3_margin = float(m200["eigenvalues"][2] - pa[2])
    pc3_ratio = float(m200["eigenvalues"][2] / pa[2])
    if retained[2]:
        pc3_state = "CANDIDATE_EVIDENCE_ONLY_NOT_CONTROL_OR_RETAINED_UNDER_RECURSIVE_POLICY"
    else:
        pc3_state = "MONITOR_NOT_RETAINED"

    matrix_out = out / "QPS_VISUAL_CENSUS_DERIVED_ARTIFACT_N200.generated.csv"
    eigen_out = out / "QPS_VISUAL_PCA_PROVENANCE_N200_EIGEN.csv"
    load_out = out / "QPS_VISUAL_PCA_PROVENANCE_N200_LOADINGS_PRESSURE.csv"
    conv_out = out / "QPS_VISUAL_PCA_N100_N200_CONVERGENCE.csv"
    receipt_out = out / "QPS_VISUAL_PCA_N200_GENERATION_RECEIPT.json"

    combined.to_csv(matrix_out, index=False)
    pd.DataFrame({
        "component": np.arange(1, p + 1),
        "eigenvalue": m200["eigenvalues"],
        "explained_pct": m200["eigenvalues"] / p * 100,
        "cumulative_pct": np.cumsum(m200["eigenvalues"]) / p * 100,
        "parallel95": pa,
        "retained_PA95": retained,
    }).to_csv(eigen_out, index=False)
    pd.DataFrame({
        "dimension": FEATURES,
        "mean_maturity": m200["means"],
        "PC1_loading": m200["loadings"][:, 0],
        "PC2_loading": m200["loadings"][:, 1],
        "PC3_loading": m200["loadings"][:, 2],
        "visual_reverse_pressure": m200["pressure"],
        "visual_reverse_pressure_rank": m200["ranks"],
        "MSA": m200["MSA"],
    }).to_csv(load_out, index=False)
    pd.DataFrame([
        {
            "checkpoint": "N100_CONTROL", "N": 100, "per_format": 25,
            "KMO": m100["KMO"], "PC1_explained_pct": m100["eigenvalues"][0] / p * 100,
            "PC2_explained_pct": m100["eigenvalues"][1] / p * 100,
            "PC3_explained_pct": m100["eigenvalues"][2] / p * 100,
            "PC1_loading_congruence_to_N100": 1.0, "PC2_loading_congruence_to_N100": 1.0,
            "PC3_loading_congruence_to_N100": 1.0, "visual_reverse_pressure_spearman_to_N100": 1.0,
        },
        {
            "checkpoint": "N200_MEASURED", "N": 200, "per_format": 50,
            "KMO": m200["KMO"], "PC1_explained_pct": m200["eigenvalues"][0] / p * 100,
            "PC2_explained_pct": m200["eigenvalues"][1] / p * 100,
            "PC3_explained_pct": m200["eigenvalues"][2] / p * 100,
            "PC1_loading_congruence_to_N100": load_congruence[0],
            "PC2_loading_congruence_to_N100": load_congruence[1],
            "PC3_loading_congruence_to_N100": load_congruence[2],
            "visual_reverse_pressure_spearman_to_N100": pressure_rho,
        },
    ]).to_csv(conv_out, index=False)

    receipt = {
        "schema": "qps-visual-pca-n200-generation-receipt/0.1",
        "status": "PASS_EXACT_BALANCE_DEDUPE_AND_N200_STATISTICS",
        "artifact_N": 200,
        "format_counts": combined_counts,
        "post_N100_counts": post_counts,
        "post_N100_cohort_counts": cohort_counts,
        "features": FEATURES,
        "dedupe": {
            "post_source_hash_duplicates": 0,
            "post_render_hash_duplicates": 0,
            "post_artifact_key_duplicates": 0,
            "post_exact_family_key_duplicates": 0,
            "post_source_collision_with_frozen_N100": 0,
            "post_render_collision_with_frozen_N100": 0,
            "post_artifact_key_collision_with_frozen_N100": 0,
            "family_gate_basis": "POST_EXPLICIT_FAMILY_KEY_ELSE_EXACT_ARTIFACT_ID_FALLBACK_WITHIN_FORMAT_PLUS_INHERITED_PER_TRANCHE_FAMILY_VERSION_ADMISSION",
            "semantic_family_inference": "NOT_INVENTED_FOR_FROZEN_N100",
        },
        "adequacy": {
            "KMO": m200["KMO"],
            "MSA": dict(zip(FEATURES, m200["MSA"])),
            "minimum_MSA": min(m200["MSA"]),
            "minimum_MSA_dimension": FEATURES[int(np.argmin(m200["MSA"]))],
            "bartlett_chi_square": m200["bartlett_chi2"],
            "bartlett_df": m200["bartlett_df"],
            "bartlett_p_value": m200["bartlett_p"],
        },
        "PCA": {
            "eigenvalues": m200["eigenvalues"].tolist(),
            "explained_pct": (m200["eigenvalues"] / p * 100).tolist(),
            "parallel95_N200": pa.tolist(),
            "retained_PA95": retained.tolist(),
        },
        "convergence_to_N100": {
            "PC1_loading_congruence": load_congruence[0],
            "PC2_loading_congruence": load_congruence[1],
            "PC3_loading_congruence": load_congruence[2],
            "PC1_explained_variance_abs_drift_percentage_points": pc1_drift_pp,
            "visual_reverse_pressure_rank_spearman": pressure_rho,
        },
        "PC3": {
            "eigenvalue": float(m200["eigenvalues"][2]),
            "PA95": float(pa[2]),
            "margin_eigen_minus_PA95": pc3_margin,
            "eigen_to_PA95_ratio": pc3_ratio,
            "passes_N200_PA95": bool(retained[2]),
            "state": pc3_state,
            "recursive_policy": "A_SINGLE_N200_PA95_PASS_IS_CANDIDATE_EVIDENCE_ONLY; RETENTION_REQUIRES_SUBSEQUENT_BALANCED_CONFIRMATION_PLUS_CONGRUENCE_POLE_CONFOUNDING_AND_SEMANTIC_GATES",
        },
        "visual_reverse_pressure": pd.DataFrame({
            "dimension": FEATURES, "pressure": m200["pressure"], "rank": m200["ranks"]
        }).sort_values("rank").to_dict("records"),
        "randomness": {
            "parallel_analysis_seed": 777,
            "parallel_analysis_simulations_per_N": 5000,
            "parallel_stream_order": [60, 80, 100, 200],
            "PA95_definition": "95TH_PERCENTILE_ORDERED_RANDOM_CORRELATION_EIGENVALUE_NOT_CONFIDENCE_INTERVAL",
        },
        "inputs_sha256": input_hashes,
        "outputs_sha256": {},
        "authority": {
            "N100_control": "FROZEN_REFERENCE",
            "N200": "MEASURED_CHECKPOINT_PENDING_REVIEW_AND_ATOMIC_CONTROL_PROMOTION",
            "project_global_PCA": "WITHHELD",
            "true_Bradley_Terry_fit": "NOT_PERFORMED",
            "visual_reverse_pressure_method": "NON_BT_WEIGHTED_SCALAR_PRIORITY",
            "repo_local_runner_923": "INDEPENDENT_NON_COMPENSATING",
        },
        "formal_credit_delta": {
            "engineering": 0, "compliance": 0, "negotiation": 0,
            "acceptance": 0, "release": 0, "project_global_PCA": 0,
        },
    }
    for pth in [matrix_out, eigen_out, load_out, conv_out]:
        receipt["outputs_sha256"][pth.name] = sha256(pth)
    receipt_out.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": receipt["status"],
        "N": 200,
        "per_format": combined_counts,
        "KMO": m200["KMO"],
        "minimum_MSA": min(m200["MSA"]),
        "PC1_pct": receipt["PCA"]["explained_pct"][0],
        "PC2_pct": receipt["PCA"]["explained_pct"][1],
        "PC3_pct": receipt["PCA"]["explained_pct"][2],
        "PC3_eigen": receipt["PC3"]["eigenvalue"],
        "PC3_PA95": receipt["PC3"]["PA95"],
        "PC3_state": receipt["PC3"]["state"],
        "PC1_congruence_to_N100": load_congruence[0],
        "pressure_spearman_to_N100": pressure_rho,
        "outputs": receipt["outputs_sha256"],
        "receipt_sha256": sha256(receipt_out),
    }, indent=2))


if __name__ == "__main__":
    main()
