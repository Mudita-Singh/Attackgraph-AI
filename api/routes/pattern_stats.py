"""
API Routes for Pattern Stats (Phase 18 & Section 34)
Exposes GET /pattern-stats and GET /pattern-stats/{pattern_key}
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import PatternStats
from api.schemas import PatternStatsResponse
from graph.pattern_learning import get_pattern_prior

router = APIRouter(tags=["pattern-stats"])

@router.get("/pattern-stats", response_model=List[PatternStatsResponse])
def get_all_pattern_stats(db: Session = Depends(get_db)):
    """Retrieve all PatternStats rows with computed priors."""
    rows = db.query(PatternStats).all()
    results = []
    for row in rows:
        prior_info = get_pattern_prior(row.pattern_key, db)
        results.append(PatternStatsResponse(
            pattern_key=row.pattern_key,
            times_verified=row.times_verified,
            times_refuted=row.times_refuted,
            prior_confidence=prior_info["prior_confidence"],
            observation_count=prior_info["observation_count"],
            last_updated=row.last_updated
        ))
    return results

@router.get("/pattern-stats/{pattern_key:path}", response_model=PatternStatsResponse)
def get_single_pattern_stats(pattern_key: str, db: Session = Depends(get_db)):
    """Retrieve PatternStats for a specific pattern_key."""
    prior_info = get_pattern_prior(pattern_key, db)
    row = db.query(PatternStats).filter(PatternStats.pattern_key == pattern_key).first()
    return PatternStatsResponse(
        pattern_key=pattern_key,
        times_verified=prior_info["times_verified"],
        times_refuted=prior_info["times_refuted"],
        prior_confidence=prior_info["prior_confidence"],
        observation_count=prior_info["observation_count"],
        last_updated=row.last_updated if row else None
    )
