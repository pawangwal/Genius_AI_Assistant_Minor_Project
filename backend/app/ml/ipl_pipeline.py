"""IPL Model Pipeline Service: loads pipeline artifact, computes derived features, and executes win probability inference."""
import os
import time
import pickle
import logging
from typing import Optional, Tuple
import pandas as pd
import numpy as np
from backend.app.ml.schemas import IPLPredictionRequest, IPLPredictionResponse, DerivedMatchFeatures
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class IPLModelService:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.IPL_MODEL_PATH
        self.pipeline = None
        self._is_loaded = False

    def load(self) -> bool:
        """Loads the serialized scikit-learn pipeline after cryptographic SHA-256 integrity verification."""
        import hashlib
        import json

        if not os.path.exists(self.model_path):
            logger.error(f"IPL model artifact not found at: {self.model_path}")
            self._is_loaded = False
            return False

        # Independent trust anchor verification: verify against trusted configuration anchor
        trusted_sha256 = settings.IPL_MODEL_TRUSTED_SHA256
        if not trusted_sha256 or len(str(trusted_sha256).strip()) != 64:
            logger.critical("SECURITY ALERT: Missing or malformed trusted SHA-256 anchor! Refusing to load model.")
            self._is_loaded = False
            return False

        try:
            with open(self.model_path, "rb") as f:
                content = f.read()

            actual_sha256 = hashlib.sha256(content).hexdigest()
            if actual_sha256 != str(trusted_sha256).strip().lower():
                logger.critical(
                    f"SECURITY ALERT: Model artifact integrity verification failed against trusted anchor! "
                    f"Expected SHA-256: {trusted_sha256}, Actual: {actual_sha256}. Refusing to unpickle."
                )
                self._is_loaded = False
                return False

            logger.info(f"Model artifact SHA-256 verified against trusted anchor ({actual_sha256[:12]}...).")

            self.pipeline = pickle.loads(content)
            self._is_loaded = True
            logger.info(f"Successfully loaded IPL pipeline from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to verify/unpickle IPL model artifact: {e}")
            self._is_loaded = False
            return False

    @property
    def is_ready(self) -> bool:
        return self._is_loaded and self.pipeline is not None

    def compute_features(self, req: IPLPredictionRequest) -> Tuple[DerivedMatchFeatures, pd.DataFrame]:
        """Calculates derived features following the exact training specifications."""
        legal_balls_bowled = (req.overs_completed * 6) + req.balls_in_over
        balls_left = max(0, 120 - legal_balls_bowled)
        runs_left = max(0, req.target_score - req.current_score)
        wickets_left = max(0, 10 - req.wickets_out)

        # Current Run Rate (runs per over completed)
        if legal_balls_bowled > 0:
            crr = (req.current_score * 6.0) / float(legal_balls_bowled)
        else:
            crr = 0.0

        # Required Run Rate (runs needed per over remaining)
        if balls_left > 0:
            rrr = (runs_left * 6.0) / float(balls_left)
        else:
            rrr = 999.0 if runs_left > 0 else 0.0

        total_runs_x = req.target_score

        derived = DerivedMatchFeatures(
            legal_balls_bowled=legal_balls_bowled,
            balls_left=balls_left,
            runs_left=runs_left,
            wickets_left=wickets_left,
            crr=round(crr, 4),
            rrr=round(rrr, 4),
            total_runs_x=total_runs_x
        )

        # Build single-row DataFrame with the exact column order expected by ColumnTransformer
        df = pd.DataFrame([{
            "batting_team": req.batting_team,
            "bowling_team": req.bowling_team,
            "city": req.city,
            "runs_left": runs_left,
            "balls_left": balls_left,
            "wickets_left": wickets_left,
            "total_runs_x": total_runs_x,
            "crr": crr,
            "rrr": rrr
        }])

        return derived, df

    def predict(self, req: IPLPredictionRequest) -> IPLPredictionResponse:
        """Executes win probability prediction with complete boundary handling."""
        if not self.is_ready:
            raise RuntimeError("IPL model pipeline is not loaded or ready.")

        start_time = time.perf_counter()
        derived, df = self.compute_features(req)

        # Deterministic Boundary Case 1: Target reached
        if req.current_score >= req.target_score:
            batting_prob = 1.0
            bowling_prob = 0.0
            projected_winner = req.batting_team
            completed = True
            summary = f"{req.batting_team} has successfully chased the target of {req.target_score}."
        
        # Deterministic Boundary Case 2: All wickets lost before target
        elif req.wickets_out >= 10:
            batting_prob = 0.0
            bowling_prob = 1.0
            projected_winner = req.bowling_team
            completed = True
            summary = f"{req.batting_team} is all out. {req.bowling_team} wins defending {req.target_score}."

        # Deterministic Boundary Case 3: Overs exhausted before target
        elif derived.balls_left == 0 and req.current_score < req.target_score:
            batting_prob = 0.0
            bowling_prob = 1.0
            projected_winner = req.bowling_team
            completed = True
            summary = f"All 20 overs bowled. {req.bowling_team} defends the total."

        # Standard ML Inference
        else:
            proba = self.pipeline.predict_proba(df)[0]
            # Class 0: Bowling team wins | Class 1: Batting team wins
            bowling_prob = round(float(proba[0]), 4)
            batting_prob = round(float(proba[1]), 4)
            
            # Ensure probabilities sum exactly to 1.0
            total = batting_prob + bowling_prob
            if total > 0:
                batting_prob = round(batting_prob / total, 4)
                bowling_prob = round(1.0 - batting_prob, 4)

            completed = False
            if batting_prob >= 0.5:
                projected_winner = req.batting_team
                summary = f"{req.batting_team} has a {batting_prob*100:.1f}% chance of victory needing {derived.runs_left} off {derived.balls_left} balls."
            else:
                projected_winner = req.bowling_team
                summary = f"{req.bowling_team} is favored with a {bowling_prob*100:.1f}% win chance defending {derived.runs_left} runs with {derived.wickets_left} wickets remaining."

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return IPLPredictionResponse(
            batting_team=req.batting_team,
            bowling_team=req.bowling_team,
            city=req.city,
            batting_win_probability=batting_prob,
            bowling_win_probability=bowling_prob,
            projected_winner=projected_winner,
            match_completed=completed,
            status_summary=summary,
            derived_features=derived,
            inference_latency_ms=latency_ms
        )

# Global singleton service
ipl_service = IPLModelService()
