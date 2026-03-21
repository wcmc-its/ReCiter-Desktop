"""
preprocessing.py — Shared feature computation for ReCiter scoring models.

Adapted from ReCiter---Scoring/paper/src/preprocessing.py for standalone use.
"""

import os
import re
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

# Thresholds for identity signal strength
STRONG_EMAIL = float(os.getenv("STRONG_EMAIL", "0.90"))
STRONG_ORCID = float(os.getenv("STRONG_ORCID", "0.90"))
STRONG_AFFIL = float(os.getenv("STRONG_AFFIL", "0.95"))

_log = logging.getLogger(__name__)


# ── Name frequency data ──────────────────────────────────────────────────────

def _load_name_frequency():
    freq_path = Path(__file__).parent.parent / "data" / "name_frequency.json"
    if freq_path.exists():
        with open(freq_path, "r") as f:
            table = json.load(f)
        scores = [v["score"] for v in table.values()]
        median = sorted(scores)[len(scores) // 2] if scores else 0.0
        _log.info(f"Loaded name frequency table: {len(table):,} names (median={median:.4f})")
        return table, median
    return {}, 0.0


_NAME_FREQ_TABLE, _NAME_FREQ_MEDIAN = _load_name_frequency()


def _name_frequency_score(first_name):
    if not _NAME_FREQ_TABLE or not first_name or not isinstance(first_name, str):
        return 0.0
    first_name = first_name.strip().lower().replace(".", "")
    tokens = [t for t in re.split(r"[\s\-]+", first_name) if len(t) > 1]
    if not tokens:
        return 0.0
    scores = [
        _NAME_FREQ_TABLE[t]["score"] if t in _NAME_FREQ_TABLE else _NAME_FREQ_MEDIAN
        for t in tokens
    ]
    return sum(scores) / len(scores)


# ── Feature column definitions ───────────────────────────────────────────────

FEEDBACK_IDENTITY_BASE_FEATURES = [
    "feedbackScoreCites", "feedbackScoreCoAuthorName", "feedbackScoreEmail",
    "feedbackScoreInstitution", "feedbackScoreJournal", "feedbackScoreJournalSubField",
    "feedbackScoreKeyword", "feedbackScoreOrcid", "feedbackScoreOrcidCoAuthor",
    "feedbackScoreOrganization", "feedbackScoreTargetAuthorName", "feedbackScoreYear",
    "articleCountScore", "authorCountScore", "discrepancyDegreeYearScore", "emailMatchScore",
    "genderScoreIdentityArticleDiscrepancy", "grantMatchScore", "journalSubfieldScore",
    "nameMatchFirstScore", "nameMatchLastScore", "nameMatchMiddleScore", "nameMatchModifierScore",
    "organizationalUnitMatchingScore", "scopusNonTargetAuthorInstitutionalAffiliationScore",
    "targetAuthorInstitutionalAffiliationMatchTypeScore",
    "pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore",
    "relationshipPositiveMatchScore", "relationshipNegativeMatchScore", "relationshipIdentityCount",
    "countAccepted", "countRejected",
]

IDENTITY_ONLY_BASE_FEATURES = [
    "articleCountScore", "authorCountScore", "discrepancyDegreeYearScore", "emailMatchScore",
    "genderScoreIdentityArticleDiscrepancy", "grantMatchScore", "journalSubfieldScore",
    "nameMatchFirstScore", "nameMatchLastScore", "nameMatchMiddleScore", "nameMatchModifierScore",
    "organizationalUnitMatchingScore",
    "scopusNonTargetAuthorInstitutionalAffiliationScore",
    "targetAuthorInstitutionalAffiliationMatchTypeScore",
    "pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore",
    "relationshipPositiveMatchScore", "relationshipNegativeMatchScore", "relationshipIdentityCount",
]

DERIVED_FEATURES_IDENTITY_SHARED = [
    "identityStrength", "netEvidenceCount", "ambiguityRisk",
    "nameInstitutionInteraction", "worstSingleEvidence", "nameQualityMin",
    "firstNameFrequencyScore",
]

DERIVED_FEATURES_FEEDBACK = [
    "acceptanceRateLowerBound", "feedbackConfidence",
    "uncertainRejectionRisk", "feedbackDensity",
] + DERIVED_FEATURES_IDENTITY_SHARED

DERIVED_FEATURES_IDENTITY_ONLY = list(DERIVED_FEATURES_IDENTITY_SHARED)

FEEDBACK_IDENTITY_FEATURES = FEEDBACK_IDENTITY_BASE_FEATURES + DERIVED_FEATURES_FEEDBACK
IDENTITY_ONLY_FEATURES = IDENTITY_ONLY_BASE_FEATURES + DERIVED_FEATURES_IDENTITY_ONLY


# ── Statistical functions ────────────────────────────────────────────────────

def wilson_lower_bound(successes: float, failures: float, confidence: float = 0.95) -> float:
    n = successes + failures
    if n == 0:
        return 0.5
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = successes / n
    denominator = 1 + z**2 / n
    centre = p + z**2 / (2 * n)
    spread = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    lower = (centre - spread) / denominator
    return max(0.0, min(1.0, lower))


# ── Derived feature computation ──────────────────────────────────────────────

_POSITIVE_EVIDENCE_FEATURES = [
    "nameMatchFirstScore", "emailMatchScore", "grantMatchScore",
    "journalSubfieldScore", "organizationalUnitMatchingScore",
    "targetAuthorInstitutionalAffiliationMatchTypeScore",
    "pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore",
    "scopusNonTargetAuthorInstitutionalAffiliationScore",
    "relationshipPositiveMatchScore",
    "genderScoreIdentityArticleDiscrepancy",
]

_NEGATIVE_EVIDENCE_FEATURES = [
    "nameMatchFirstScore", "nameMatchMiddleScore", "nameMatchModifierScore",
    "targetAuthorInstitutionalAffiliationMatchTypeScore",
    "discrepancyDegreeYearScore", "genderScoreIdentityArticleDiscrepancy",
    "relationshipNegativeMatchScore", "articleCountScore",
]

_WORST_EVIDENCE_FEATURES = [
    "nameMatchFirstScore", "nameMatchMiddleScore",
    "targetAuthorInstitutionalAffiliationMatchTypeScore",
    "discrepancyDegreeYearScore", "genderScoreIdentityArticleDiscrepancy",
]


def _compute_identity_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    pos_count = sum((df[f] > 0).astype(int) for f in _POSITIVE_EVIDENCE_FEATURES)
    neg_count = sum((df[f] < 0).astype(int) for f in _NEGATIVE_EVIDENCE_FEATURES)
    df["netEvidenceCount"] = pos_count - neg_count

    df["ambiguityRisk"] = df["articleCountScore"] * (1 - df["identityStrength"])

    best_affil = np.maximum(
        df["targetAuthorInstitutionalAffiliationMatchTypeScore"],
        df["pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore"],
    )
    df["nameInstitutionInteraction"] = df["nameMatchFirstScore"] * best_affil

    df["worstSingleEvidence"] = np.minimum.reduce([df[f] for f in _WORST_EVIDENCE_FEATURES])

    df["nameQualityMin"] = np.minimum.reduce([
        df["nameMatchFirstScore"], df["nameMatchLastScore"], df["nameMatchMiddleScore"],
    ])

    if _NAME_FREQ_TABLE and "identityFirstName" in df.columns:
        df["firstNameFrequencyScore"] = df["identityFirstName"].map(_name_frequency_score)
    else:
        df["firstNameFrequencyScore"] = 0.0

    return df


def compute_derived_features_feedback_identity(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["acceptanceRateLowerBound"] = df.apply(
        lambda row: wilson_lower_bound(row["countAccepted"], row["countRejected"]), axis=1
    )

    total_feedback = df["countAccepted"] + df["countRejected"]
    df["feedbackConfidence"] = np.log1p(total_feedback)

    email_strength = (df["emailMatchScore"].fillna(0).clip(0, 1) / STRONG_EMAIL).clip(0, 1)
    orcid_strength = (df["feedbackScoreOrcid"].fillna(0).clip(0, 1) / STRONG_ORCID).clip(0, 1)
    affil_strength = np.maximum(
        df["targetAuthorInstitutionalAffiliationMatchTypeScore"].fillna(0).clip(0, 1),
        df["pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore"].fillna(0).clip(0, 1),
    ) / STRONG_AFFIL
    affil_strength = affil_strength.clip(0, 1)
    df["identityStrength"] = np.maximum.reduce([email_strength, orcid_strength, affil_strength])

    df = _compute_identity_engineered_features(df)

    confidence_factor = 1 - np.exp(-total_feedback / 10)
    df["uncertainRejectionRisk"] = (
        (1 - df["acceptanceRateLowerBound"])
        * (1 - df["identityStrength"])
        * confidence_factor
    )

    feedback_cols = [
        "feedbackScoreCites", "feedbackScoreCoAuthorName", "feedbackScoreEmail",
        "feedbackScoreInstitution", "feedbackScoreJournal", "feedbackScoreJournalSubField",
        "feedbackScoreKeyword", "feedbackScoreOrcid", "feedbackScoreOrcidCoAuthor",
        "feedbackScoreOrganization", "feedbackScoreTargetAuthorName", "feedbackScoreYear",
    ]
    df["feedbackDensity"] = (df[feedback_cols] != 0).sum(axis=1) / len(feedback_cols)

    return df


def compute_derived_features_identity_only(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    email_strength = (df["emailMatchScore"].fillna(0).clip(0, 1) / STRONG_EMAIL).clip(0, 1)
    affil_strength = np.maximum(
        df["targetAuthorInstitutionalAffiliationMatchTypeScore"].fillna(0).clip(0, 1),
        df["pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore"].fillna(0).clip(0, 1),
    ) / STRONG_AFFIL
    affil_strength = affil_strength.clip(0, 1)
    df["identityStrength"] = np.maximum(email_strength, affil_strength)

    df = _compute_identity_engineered_features(df)
    return df


# ── Inference pipelines ──────────────────────────────────────────────────────

def preprocess_for_inference_feedback_identity(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[FEEDBACK_IDENTITY_BASE_FEATURES] = df[FEEDBACK_IDENTITY_BASE_FEATURES].fillna(0)
    df = compute_derived_features_feedback_identity(df)
    return df


def preprocess_for_inference_identity_only(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[IDENTITY_ONLY_BASE_FEATURES] = df[IDENTITY_ONLY_BASE_FEATURES].fillna(0)
    df = compute_derived_features_identity_only(df)
    return df
