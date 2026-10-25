"""CricAPI live cricket scores integration endpoint.
Fetches live matches securely without exposing API keys to the frontend.
"""
from typing import List, Optional
import httpx
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.config import settings

logger = logging.getLogger("genius.cricket")

router = APIRouter(prefix="/cricket", tags=["Cricket"])

class CricketInningScore(BaseModel):
    runs: int = 0
    wickets: int = 0
    overs: float = 0.0
    inning: str = ""

class CricketMatch(BaseModel):
    id: str
    name: str
    teams: List[str]
    match_type: str
    scores: List[CricketInningScore]
    status: str
    venue: str
    date: str
    match_ended: bool

class CricketScoresResponse(BaseModel):
    status: str  # "success" | "empty" | "error"
    message: Optional[str] = None
    matches: List[CricketMatch]

CRICAPI_URL = "https://api.cricapi.com/v1/currentMatches"

async def query_cricapi_raw(api_key: str) -> dict:
    """Makes HTTP request to CricAPI and returns parsed JSON."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            CRICAPI_URL,
            params={"apikey": api_key, "offset": 0}
        )
    if resp.status_code != 200:
        raise httpx.HTTPStatusError(
            f"CricAPI upstream responded with HTTP {resp.status_code}",
            request=resp.request,
            response=resp
        )
    return resp.json()

async def fetch_cricapi_scores() -> CricketScoresResponse:
    """Internal service function to query CricAPI and format match items."""
    api_key = settings.CRICAPI_KEY
    if not api_key or not api_key.strip():
        logger.warning("CricAPI key is not configured.")
        return CricketScoresResponse(
            status="error",
            message="CricAPI key is not configured on the server. Please set CRICAPI_KEY in .env.",
            matches=[]
        )

    try:
        data = await query_cricapi_raw(api_key)

        if data.get("status") != "success":
            err_reason = data.get("info", {}).get("hitsToday") or data.get("reason", "Unknown upstream error")
            logger.warning(f"CricAPI upstream status not success: {err_reason}")
            return CricketScoresResponse(
                status="error",
                message="Cricket score service is temporarily unavailable or hit usage limit.",
                matches=[]
            )

        raw_matches = data.get("data", [])
        if not raw_matches:
            return CricketScoresResponse(
                status="empty",
                message="No live matches currently in progress.",
                matches=[]
            )

        matches: List[CricketMatch] = []
        for m in raw_matches:
            scores_list: List[CricketInningScore] = []
            for sc in m.get("score", []):
                try:
                    scores_list.append(
                        CricketInningScore(
                            runs=int(sc.get("r", 0)),
                            wickets=int(sc.get("w", 0)),
                            overs=float(sc.get("o", 0.0)),
                            inning=str(sc.get("inning", ""))
                        )
                    )
                except (ValueError, TypeError):
                    continue

            matches.append(
                CricketMatch(
                    id=str(m.get("id", "")),
                    name=str(m.get("name", "Match")),
                    teams=[str(t) for t in m.get("teams", [])],
                    match_type=str(m.get("matchType", "match")).upper(),
                    scores=scores_list,
                    status=str(m.get("status", "")),
                    venue=str(m.get("venue", "Unknown Venue")),
                    date=str(m.get("date", "")),
                    match_ended=bool(m.get("matchEnded", False))
                )
            )

        return CricketScoresResponse(
            status="success",
            message=None,
            matches=matches
        )

    except httpx.TimeoutException:
        logger.warning("CricAPI request timed out after 10.0s")
        return CricketScoresResponse(
            status="error",
            message="Cricket score service timed out. Please try again.",
            matches=[]
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(f"CricAPI HTTP status error: {exc}")
        return CricketScoresResponse(
            status="error",
            message="Cricket score service returned an error status.",
            matches=[]
        )
    except httpx.RequestError as exc:
        logger.warning(f"CricAPI network error: {type(exc).__name__}")
        return CricketScoresResponse(
            status="error",
            message="Network error while connecting to cricket score service.",
            matches=[]
        )
    except Exception as exc:
        logger.error(f"Unexpected error in fetch_cricapi_scores: {type(exc).__name__}")
        return CricketScoresResponse(
            status="error",
            message="Internal error while parsing cricket scores.",
            matches=[]
        )

@router.get("/scores", response_model=CricketScoresResponse)
async def get_cricket_scores() -> CricketScoresResponse:
    """Fetch live and current cricket scores from CricAPI."""
    return await fetch_cricapi_scores()

@router.get("/all", response_model=CricketScoresResponse)
async def get_all_cricket_scores() -> CricketScoresResponse:
    """Fetch all current and live cricket matches with full scorecards."""
    return await fetch_cricapi_scores()

@router.get("/matches", response_model=CricketScoresResponse)
async def get_cricket_matches() -> CricketScoresResponse:
    """Matches listing endpoint for dedicated cricket scores dashboard."""
    return await fetch_cricapi_scores()
