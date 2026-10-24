"""IPL prediction endpoints."""
from fastapi import APIRouter, HTTPException, status
from backend.app.ml.schemas import IPLPredictionRequest, IPLPredictionResponse
from backend.app.ml.ipl_pipeline import ipl_service

router = APIRouter(prefix="/predictions", tags=["ML Predictions"])

@router.post("/ipl", response_model=IPLPredictionResponse, status_code=status.HTTP_200_OK)
async def predict_ipl_match(request: IPLPredictionRequest):
    """Predicts IPL 2nd innings chase win probabilities given current match context."""
    if not ipl_service.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IPL prediction model is currently unavailable."
        )

    try:
        result = ipl_service.predict(request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(e)}"
        )
