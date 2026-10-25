"""CricAPI live cricket scores integration endpoint.
Fetches live matches and detailed scorecards securely without exposing API keys to the frontend.
Includes in-memory caching to guard against CricAPI 15-minute rate-limit blocks,
while supporting on-demand forced fresh requests.
"""
from typing import List, Optional, Dict, Any, Tuple
import time
import httpx
import logging
from fastapi import APIRouter, Query, Path
from pydantic import BaseModel

from backend.app.core.config import settings

logger = logging.getLogger("genius.cricket")

router = APIRouter(prefix="/cricket", tags=["Cricket"])

# Models
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
    status: str  # "success" | "empty" | "error" | "cached"
    message: Optional[str] = None
    matches: List[CricketMatch]

# Detailed Scorecard Models
class BatsmanScore(BaseModel):
    name: str
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    strike_rate: float = 0.0
    dismissal: str = ""

class BowlerScore(BaseModel):
    name: str
    overs: float = 0.0
    maidens: int = 0
    runs: int = 0
    wickets: int = 0
    economy: float = 0.0

class InningScorecard(BaseModel):
    inning: str
    runs: int = 0
    wickets: int = 0
    overs: float = 0.0
    batsmen: List[BatsmanScore] = []
    bowlers: List[BowlerScore] = []

class MatchScorecardResponse(BaseModel):
    status: str  # "success" | "error" | "cached"
    match_id: str
    name: str
    status_text: str = ""
    venue: str = ""
    date: str = ""
    teams: List[str] = []
    innings: List[InningScorecard] = []
    message: Optional[str] = None

# CricAPI URLs
CRICAPI_BASE_URL = "https://api.cricapi.com/v1"
CRICAPI_MATCHES_URL = f"{CRICAPI_BASE_URL}/currentMatches"
CRICAPI_SCORECARD_URL = f"{CRICAPI_BASE_URL}/match_scorecard"

# In-memory cache to prevent 15-minute rate limit blocks on CricAPI free tier
CACHE_TTL_SECONDS = 30.0

_matches_cache: Dict[str, Any] = {
    "timestamp": 0.0,
    "response": None
}

_scorecard_cache: Dict[str, Dict[str, Any]] = {}
_key_cooldowns: Dict[str, float] = {}

def reset_cricket_cache():
    """Resets in-memory cricket caches and key rotation cooldowns."""
    _matches_cache["timestamp"] = 0.0
    _matches_cache["response"] = None
    _scorecard_cache.clear()
    _key_cooldowns.clear()

def _mask_key(k: str) -> str:
    """Safely masks an API key for logs (e.g. '9c79...2497')."""
    if not k:
        return "..."
    clean = k.strip()
    if len(clean) <= 8:
        return f"...{clean[-3:]}"
    return f"{clean[:4]}...{clean[-4:]}"

def _is_rate_limit_or_key_error(status: str, reason: str) -> bool:
    """Determines whether an upstream response indicates rate-limiting, blocking, or key exhaustion."""
    if status == "success":
        return False
    r = reason.lower()
    return any(term in r for term in ("blocked", "rate", "limit", "quota", "exhausted", "hits", "invalid", "unauthorized", "expired"))

async def query_cricapi_raw(url: str, params: dict) -> dict:
    """Makes HTTP request to CricAPI and returns parsed JSON."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
    if resp.status_code != 200:
        raise httpx.HTTPStatusError(
            f"CricAPI upstream responded with HTTP {resp.status_code}",
            request=resp.request,
            response=resp
        )
    return resp.json()

async def query_cricapi_with_rotation(
    url: str,
    base_params: dict
) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
    """
    Executes a CricAPI request by rotating across configured API keys when rate limits or key errors occur.
    Returns: (data_dict, rate_limit_reason, fatal_error_msg)
    """
    keys = settings.get_cricapi_keys()
    if not keys:
        logger.warning("No CricAPI keys configured.")
        return None, None, "CricAPI key is not configured on the server. Please set CRICAPI_KEY1, CRICAPI_KEY2, or CRICAPI_KEY in .env."

    now = time.time()
    # 1. Filter out keys currently in cooldown (e.g. blocked for 15 minutes)
    active_keys = [k for k in keys if _key_cooldowns.get(k, 0.0) <= now]

    # If all keys are in cooldown, pick the one with earliest cooldown expiry
    if not active_keys:
        keys_by_expiry = sorted(keys, key=lambda k: _key_cooldowns.get(k, 0.0))
        active_keys = [keys_by_expiry[0]]
        earliest_wait = max(1, int(_key_cooldowns.get(keys_by_expiry[0], 0.0) - now))
        logger.warning(
            f"All {len(keys)} CricAPI keys are currently in cooldown. "
            f"Attempting key {_mask_key(keys_by_expiry[0])} ({earliest_wait}s remaining)."
        )

    last_rate_limit_reason: Optional[str] = None
    tried_count = 0

    for api_key in active_keys:
        tried_count += 1
        params = dict(base_params)
        params["apikey"] = api_key

        try:
            data = await query_cricapi_raw(url, params)
        except httpx.HTTPStatusError as http_err:
            if http_err.response.status_code in (429, 401, 403):
                reason = f"HTTP {http_err.response.status_code}"
                last_rate_limit_reason = reason
                _key_cooldowns[api_key] = time.time() + 900.0  # 15 min cooldown
                logger.warning(
                    f"CricAPI key {_mask_key(api_key)} rate limited or rejected ({reason}). "
                    f"Rotating to next key ({tried_count}/{len(active_keys)})..."
                )
                continue
            raise
        except httpx.TimeoutException:
            last_rate_limit_reason = "Upstream request timed out"
            logger.warning(f"CricAPI timeout on key {_mask_key(api_key)}. Rotating...")
            continue

        upstream_status = data.get("status", "")
        if upstream_status == "success":
            # Success! Clear cooldown for this key
            _key_cooldowns.pop(api_key, None)
            return data, None, None

        # Inspect failure reason
        reason = str(data.get("reason") or data.get("info", {}).get("hitsToday") or "Upstream rate limit or error")
        last_rate_limit_reason = reason

        if _is_rate_limit_or_key_error(upstream_status, reason):
            cooldown = 900.0 if "blocked" in reason.lower() else 300.0
            _key_cooldowns[api_key] = time.time() + cooldown
            logger.warning(
                f"CricAPI key {_mask_key(api_key)} rate limited ({reason}). "
                f"Rotating to next key ({tried_count}/{len(active_keys)})..."
            )
            continue
        else:
            # Request-specific error (not key/rate limit)
            return data, None, None

    # All active keys were rate-limited or failed
    return None, last_rate_limit_reason, None

async def fetch_cricapi_scores(force_refresh: bool = False) -> CricketScoresResponse:
    """Internal service function to query CricAPI currentMatches with caching and key rotation."""
    now = time.time()
    
    # 1. Return cached matches if fresh and not forcing refresh
    if not force_refresh and _matches_cache["response"] is not None:
        if (now - _matches_cache["timestamp"]) < CACHE_TTL_SECONDS:
            logger.debug("Serving cricket scores from in-memory cache.")
            return _matches_cache["response"]

    try:
        data, rate_limit_reason, fatal_error = await query_cricapi_with_rotation(
            CRICAPI_MATCHES_URL,
            {"offset": 0}
        )

        if fatal_error:
            return CricketScoresResponse(
                status="error",
                message=fatal_error,
                matches=[]
            )

        if rate_limit_reason:
            logger.warning(f"All CricAPI keys rate-limited: {rate_limit_reason}")
            # If rate-limited across all keys, fall back to cached matches if available
            if _matches_cache["response"] is not None and _matches_cache["response"].matches:
                cached_resp = _matches_cache["response"]
                return CricketScoresResponse(
                    status="success",
                    message=f"Live scores active (CricAPI rate-limit cooldown: {rate_limit_reason}).",
                    matches=cached_resp.matches
                )

            return CricketScoresResponse(
                status="error",
                message=f"Cricket score service is temporarily rate-limited ({rate_limit_reason}). Please wait before refreshing.",
                matches=[]
            )

        if not data or data.get("status") != "success":
            err_msg = str(data.get("reason") if data else "Upstream error")
            return CricketScoresResponse(
                status="error",
                message=f"Cricket score service error: {err_msg}",
                matches=[]
            )

        raw_matches = data.get("data", [])
        if not raw_matches:
            resp = CricketScoresResponse(
                status="empty",
                message="No live matches currently in progress.",
                matches=[]
            )
            _matches_cache["timestamp"] = now
            _matches_cache["response"] = resp
            return resp

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

        resp = CricketScoresResponse(
            status="success",
            message=None,
            matches=matches
        )
        _matches_cache["timestamp"] = now
        _matches_cache["response"] = resp
        return resp

    except httpx.TimeoutException:
        logger.warning("CricAPI request timed out after 10.0s")
        if not force_refresh and _matches_cache["response"] is not None:
            return _matches_cache["response"]
        return CricketScoresResponse(
            status="error",
            message="Cricket score service timed out. Please try again.",
            matches=[]
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(f"CricAPI HTTP status error: {exc}")
        if not force_refresh and _matches_cache["response"] is not None:
            return _matches_cache["response"]
        return CricketScoresResponse(
            status="error",
            message="Cricket score service returned an error status.",
            matches=[]
        )
    except Exception as exc:
        logger.error(f"Unexpected error in fetch_cricapi_scores: {type(exc).__name__}")
        if not force_refresh and _matches_cache["response"] is not None:
            return _matches_cache["response"]
        return CricketScoresResponse(
            status="error",
            message="Internal error while connecting to cricket score service.",
            matches=[]
        )


async def fetch_cricapi_scorecard(match_id: str, force_refresh: bool = False) -> MatchScorecardResponse:
    """Queries CricAPI match_scorecard endpoint for full batting and bowling breakdown."""
    now = time.time()
    
    # Check cache for this match
    if not force_refresh and match_id in _scorecard_cache:
        cached_entry = _scorecard_cache[match_id]
        if (now - cached_entry["timestamp"]) < CACHE_TTL_SECONDS:
            return cached_entry["response"]

    try:
        data, rate_limit_reason, fatal_error = await query_cricapi_with_rotation(
            CRICAPI_SCORECARD_URL,
            {"id": match_id}
        )

        if fatal_error:
            return MatchScorecardResponse(
                status="error",
                match_id=match_id,
                name="Match Scorecard",
                message=fatal_error
            )

        if rate_limit_reason or not data or data.get("status") != "success":
            err_reason = rate_limit_reason or (data.get("reason") if data else "Upstream scorecard unavailable")
            logger.warning(f"CricAPI scorecard returned non-success: {err_reason}")
            
            # Check if we have match summary info in match cache
            fallback_match = None
            if _matches_cache["response"] and _matches_cache["response"].matches:
                fallback_match = next((m for m in _matches_cache["response"].matches if m.id == match_id), None)

            # Build fallback scorecard from score summary if detailed scorecard is blocked
            innings_list = []
            if fallback_match and fallback_match.scores:
                for sc in fallback_match.scores:
                    innings_list.append(
                        InningScorecard(
                            inning=sc.inning,
                            runs=sc.runs,
                            wickets=sc.wickets,
                            overs=sc.overs,
                            batsmen=[],
                            bowlers=[]
                        )
                    )

            return MatchScorecardResponse(
                status="success" if fallback_match else "error",
                match_id=match_id,
                name=fallback_match.name if fallback_match else "Match Scorecard",
                status_text=fallback_match.status if fallback_match else err_reason,
                venue=fallback_match.venue if fallback_match else "",
                date=fallback_match.date if fallback_match else "",
                teams=fallback_match.teams if fallback_match else [],
                innings=innings_list,
                message=f"Scorecard summary (Upstream note: {err_reason})"
            )

        match_data = data.get("data", {})
        innings_raw = match_data.get("scorecard", []) or match_data.get("score", [])
        
        parsed_innings: List[InningScorecard] = []
        for inn in innings_raw:
            inn_title = inn.get("inning", "Inning")
            batting_raw = inn.get("batting", [])
            bowling_raw = inn.get("bowling", [])
            
            batsmen_list = []
            for b in batting_raw:
                b_name = b.get("batsman", {}).get("name") if isinstance(b.get("batsman"), dict) else str(b.get("batsman", "Batsman"))
                try:
                    batsmen_list.append(
                        BatsmanScore(
                            name=b_name,
                            runs=int(b.get("r", 0)),
                            balls=int(b.get("b", 0)),
                            fours=int(b.get("4s", 0)),
                            sixes=int(b.get("6s", 0)),
                            strike_rate=float(b.get("sr", 0.0)),
                            dismissal=str(b.get("dismissal-text", "") or b.get("dismissal", ""))
                        )
                    )
                except (ValueError, TypeError):
                    continue

            bowlers_list = []
            for bw in bowling_raw:
                bw_name = bw.get("bowler", {}).get("name") if isinstance(bw.get("bowler"), dict) else str(bw.get("bowler", "Bowler"))
                try:
                    bowlers_list.append(
                        BowlerScore(
                            name=bw_name,
                            overs=float(bw.get("o", 0.0)),
                            maidens=int(bw.get("m", 0)),
                            runs=int(bw.get("r", 0)),
                            wickets=int(bw.get("w", 0)),
                            economy=float(bw.get("eco", 0.0))
                        )
                    )
                except (ValueError, TypeError):
                    continue

            total_runs = int(inn.get("r", 0) or 0)
            total_wkts = int(inn.get("w", 0) or 0)
            total_overs = float(inn.get("o", 0.0) or 0.0)

            parsed_innings.append(
                InningScorecard(
                    inning=inn_title,
                    runs=total_runs,
                    wickets=total_wkts,
                    overs=total_overs,
                    batsmen=batsmen_list,
                    bowlers=bowlers_list
                )
            )

        resp = MatchScorecardResponse(
            status="success",
            match_id=match_id,
            name=str(match_data.get("name", "Match")),
            status_text=str(match_data.get("status", "")),
            venue=str(match_data.get("venue", "")),
            date=str(match_data.get("date", "")),
            teams=[str(t) for t in match_data.get("teams", [])],
            innings=parsed_innings
        )
        
        _scorecard_cache[match_id] = {
            "timestamp": now,
            "response": resp
        }
        return resp

    except Exception as exc:
        logger.error(f"Failed to fetch scorecard for {match_id}: {exc}")
        return MatchScorecardResponse(
            status="error",
            match_id=match_id,
            name="Match",
            message=f"Unable to load match scorecard: {type(exc).__name__}"
        )

# Routes
@router.get("/scores", response_model=CricketScoresResponse)
async def get_cricket_scores(
    force: bool = Query(False, description="Bypass cache and force fresh CricAPI request")
) -> CricketScoresResponse:
    """Fetch live and current cricket scores from CricAPI."""
    return await fetch_cricapi_scores(force_refresh=force)

@router.get("/all", response_model=CricketScoresResponse)
async def get_all_cricket_scores(
    force: bool = Query(False, description="Bypass cache and force fresh CricAPI request")
) -> CricketScoresResponse:
    """Fetch all current and live cricket matches with full scorecards."""
    return await fetch_cricapi_scores(force_refresh=force)

@router.get("/matches", response_model=CricketScoresResponse)
async def get_cricket_matches(
    force: bool = Query(False, description="Bypass cache and force fresh CricAPI request")
) -> CricketScoresResponse:
    """Matches listing endpoint for dedicated cricket scores dashboard."""
    return await fetch_cricapi_scores(force_refresh=force)

@router.get("/scorecard/{match_id}", response_model=MatchScorecardResponse)
async def get_match_scorecard_by_path(
    match_id: str = Path(..., description="CricAPI match UUID"),
    force: bool = Query(False, description="Bypass cache and force fresh request")
) -> MatchScorecardResponse:
    """Fetch detailed batting and bowling scorecard for a specific match."""
    return await fetch_cricapi_scorecard(match_id=match_id, force_refresh=force)

@router.get("/scorecard", response_model=MatchScorecardResponse)
async def get_match_scorecard_by_query(
    id: str = Query(..., description="CricAPI match UUID"),
    force: bool = Query(False, description="Bypass cache and force fresh request")
) -> MatchScorecardResponse:
    """Fetch detailed batting and bowling scorecard by query parameter."""
    return await fetch_cricapi_scorecard(match_id=id, force_refresh=force)
