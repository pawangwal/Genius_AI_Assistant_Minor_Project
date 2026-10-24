"""Pydantic schemas for IPL match state inputs and prediction outputs."""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator

class IPLPredictionRequest(BaseModel):
    batting_team: str = Field(..., description="Name of the team batting in the 2nd innings chase")
    bowling_team: str = Field(..., description="Name of the team defending the target score")
    city: str = Field(..., description="Host city of the match")
    target_score: int = Field(..., gt=0, le=400, description="1st innings target score (runs to beat)")
    current_score: int = Field(..., ge=0, le=400, description="Current score achieved in the chase")
    overs_completed: int = Field(..., ge=0, le=20, description="Full completed overs bowled (0-20)")
    balls_in_over: int = Field(0, ge=0, le=5, description="Additional balls bowled in current over (0-5)")
    wickets_out: int = Field(..., ge=0, le=10, description="Number of wickets fallen (0-10)")

    @model_validator(mode="after")
    def validate_match_state(self) -> "IPLPredictionRequest":
        if self.batting_team.strip() == self.bowling_team.strip():
            raise ValueError("Batting team and bowling team cannot be the same.")

        legal_balls = (self.overs_completed * 6) + self.balls_in_over
        if legal_balls > 120:
            raise ValueError(f"Total legal balls bowled ({legal_balls}) cannot exceed 120 in a 20-over match.")

        # In a standard innings, if 10 wickets are down or 120 balls bowled, the chase is concluded
        if self.overs_completed == 20 and self.balls_in_over > 0:
            raise ValueError("Innings has reached maximum 20 overs. No further balls can be bowled.")

        return self

class DerivedMatchFeatures(BaseModel):
    legal_balls_bowled: int
    balls_left: int
    runs_left: int
    wickets_left: int
    crr: float
    rrr: float
    total_runs_x: int

class IPLPredictionResponse(BaseModel):
    batting_team: str
    bowling_team: str
    city: str
    batting_win_probability: float = Field(..., ge=0.0, le=1.0)
    bowling_win_probability: float = Field(..., ge=0.0, le=1.0)
    projected_winner: str
    match_completed: bool
    status_summary: str
    derived_features: DerivedMatchFeatures
    inference_latency_ms: float
