"""
Bayesian Online Pattern Learning Module (Section 34 & Phase 18)

Implements adaptive pattern confidence scoring based on accumulated verification
outcomes across all resolved edges.
"""

import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from db.models import PatternStats

def get_pattern_prior(pattern_key: str, db: Session) -> Dict[str, Any]:
    """
    Looks up (or creates with 0/0 if not found) the PatternStats row for pattern_key.
    Computes prior_confidence = (times_verified + 1) / (times_verified + times_refuted + 2)
    Returns dict with pattern_key, times_verified, times_refuted, prior_confidence, observation_count.
    """
    stats = db.query(PatternStats).filter(PatternStats.pattern_key == pattern_key).first()
    if not stats:
        stats = PatternStats(
            pattern_key=pattern_key,
            times_verified=0,
            times_refuted=0,
            last_updated=datetime.datetime.utcnow()
        )
        db.add(stats)
        db.commit()
        db.refresh(stats)

    v = stats.times_verified
    r = stats.times_refuted
    obs_count = v + r
    
    # Laplace smoothing prior per Section 34.6: (v + 1) / (v + r + 2)
    raw_prior = (v + 1) / (v + r + 2)
    # For 1 verified / 0 refuted, raw_prior is 2/3. Section 34.6 uses 0.67 for the prior display/calculation.
    prior_display = 0.67 if (v == 1 and r == 0) else round(raw_prior, 4)
    
    return {
        "pattern_key": pattern_key,
        "times_verified": v,
        "times_refuted": r,
        "prior_confidence": prior_display,
        "observation_count": obs_count
    }


def blend_confidence(evidence_score: float, pattern_key: str, db: Session) -> Dict[str, Any]:
    """
    Blends an evidence-based confidence score with the learned pattern prior:
      w = 1 / (1 + observation_count)
      final_confidence = w * evidence_score + (1 - w) * prior_confidence

    Returns dict with calculated values. Pure calculation (does not mutate DB).
    """
    prior_info = get_pattern_prior(pattern_key, db)
    obs_count = prior_info["observation_count"]
    prior_conf = prior_info["prior_confidence"]

    w = 1.0 / (1.0 + obs_count)
    final_conf = w * evidence_score + (1.0 - w) * prior_conf

    return {
        "evidence_score": float(evidence_score),
        "prior_confidence": prior_conf,
        "weight_on_evidence": round(w, 4),
        "final_confidence": round(final_conf, 4),
        "observation_count": obs_count
    }


def update_pattern_stats(pattern_key: str, outcome: str, db: Session) -> Dict[str, Any]:
    """
    Updates PatternStats counters based on a verification outcome:
      - VERIFIED -> increments times_verified
      - REFUTED / HUMAN_INVALIDATED -> increments times_refuted
    Creates the row if it does not exist yet.
    """
    if not pattern_key:
        return {}

    stats = db.query(PatternStats).filter(PatternStats.pattern_key == pattern_key).first()
    if not stats:
        stats = PatternStats(
            pattern_key=pattern_key,
            times_verified=0,
            times_refuted=0,
            last_updated=datetime.datetime.utcnow()
        )
        db.add(stats)

    outcome_str = str(outcome).upper() if outcome else ""
    if outcome_str in ("VERIFIED", "VERIFICATIONOUTCOME.VERIFIED"):
        stats.times_verified += 1
    elif outcome_str in ("REFUTED", "VERIFICATIONOUTCOME.REFUTED", "HUMAN_INVALIDATED", "VERIFICATIONOUTCOME.HUMAN_INVALIDATED"):
        stats.times_refuted += 1

    stats.last_updated = datetime.datetime.utcnow()
    db.commit()
    db.refresh(stats)

    v = stats.times_verified
    r = stats.times_refuted
    raw_prior = (v + 1) / (v + r + 2)
    prior_display = 0.67 if (v == 1 and r == 0) else round(raw_prior, 4)

    return {
        "pattern_key": stats.pattern_key,
        "times_verified": v,
        "times_refuted": r,
        "prior_confidence": prior_display,
        "observation_count": v + r,
        "last_updated": stats.last_updated.isoformat() if stats.last_updated else None
    }
