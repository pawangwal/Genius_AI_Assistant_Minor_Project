"""Comprehensive test suite for IPL inference pipeline semantics, boundaries, and validation."""
import pytest

@pytest.mark.asyncio
async def test_ipl_prediction_valid_match_state(async_client):
    """Standard in-progress chase prediction returns valid probabilities summing to 1.0."""
    payload = {
        "batting_team": "Chennai Super Kings",
        "bowling_team": "Mumbai Indians",
        "city": "Chennai",
        "target_score": 165,
        "current_score": 120,
        "overs_completed": 15,
        "balls_in_over": 0,
        "wickets_out": 3
    }
    resp = await async_client.post("/api/v1/predictions/ipl", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["batting_team"] == "Chennai Super Kings"
    assert data["bowling_team"] == "Mumbai Indians"
    assert data["match_completed"] is False
    assert 0.0 <= data["batting_win_probability"] <= 1.0
    assert 0.0 <= data["bowling_win_probability"] <= 1.0
    assert round(data["batting_win_probability"] + data["bowling_win_probability"], 2) == 1.0
    assert data["projected_winner"] in ["Chennai Super Kings", "Mumbai Indians"]
    assert data["derived_features"]["runs_left"] == 45
    assert data["derived_features"]["balls_left"] == 30
    assert data["derived_features"]["wickets_left"] == 7
    assert data["derived_features"]["crr"] == 8.0
    assert data["derived_features"]["rrr"] == 9.0

@pytest.mark.asyncio
async def test_ipl_prediction_boundary_target_reached(async_client):
    """When target score is reached, batting win probability is 1.0 and match is completed."""
    payload = {
        "batting_team": "Royal Challengers Bengaluru",
        "bowling_team": "Kolkata Knight Riders",
        "city": "Bengaluru",
        "target_score": 180,
        "current_score": 181,
        "overs_completed": 19,
        "balls_in_over": 2,
        "wickets_out": 4
    }
    resp = await async_client.post("/api/v1/predictions/ipl", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_completed"] is True
    assert data["batting_win_probability"] == 1.0
    assert data["bowling_win_probability"] == 0.0
    assert data["projected_winner"] == "Royal Challengers Bengaluru"

@pytest.mark.asyncio
async def test_ipl_prediction_boundary_all_out(async_client):
    """When 10 wickets are lost before target, bowling team wins with 1.0 probability."""
    payload = {
        "batting_team": "Delhi Capitals",
        "bowling_team": "Rajasthan Royals",
        "city": "Delhi",
        "target_score": 200,
        "current_score": 150,
        "overs_completed": 17,
        "balls_in_over": 3,
        "wickets_out": 10
    }
    resp = await async_client.post("/api/v1/predictions/ipl", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_completed"] is True
    assert data["batting_win_probability"] == 0.0
    assert data["bowling_win_probability"] == 1.0
    assert data["projected_winner"] == "Rajasthan Royals"

@pytest.mark.asyncio
async def test_ipl_prediction_boundary_overs_exhausted(async_client):
    """When all 20 overs are bowled without reaching target, bowling team wins."""
    payload = {
        "batting_team": "Punjab Kings",
        "bowling_team": "Sunrisers Hyderabad",
        "city": "Hyderabad",
        "target_score": 175,
        "current_score": 160,
        "overs_completed": 20,
        "balls_in_over": 0,
        "wickets_out": 6
    }
    resp = await async_client.post("/api/v1/predictions/ipl", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_completed"] is True
    assert data["batting_win_probability"] == 0.0
    assert data["bowling_win_probability"] == 1.0

@pytest.mark.asyncio
async def test_ipl_prediction_zero_balls_bowled(async_client):
    """Zero overs bowled (ball 1 of chase) handles CRR calculation without division by zero."""
    payload = {
        "batting_team": "Gujarat Titans",
        "bowling_team": "Lucknow Super Giants",
        "city": "Ahmedabad",
        "target_score": 190,
        "current_score": 0,
        "overs_completed": 0,
        "balls_in_over": 0,
        "wickets_out": 0
    }
    resp = await async_client.post("/api/v1/predictions/ipl", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["derived_features"]["crr"] == 0.0
    assert data["derived_features"]["rrr"] == 9.5
    assert data["derived_features"]["balls_left"] == 120

@pytest.mark.asyncio
async def test_ipl_prediction_validation_same_team(async_client):
    """Batting team and bowling team cannot be the same."""
    payload = {
        "batting_team": "Mumbai Indians",
        "bowling_team": "Mumbai Indians",
        "city": "Mumbai",
        "target_score": 180,
        "current_score": 50,
        "overs_completed": 5,
        "balls_in_over": 0,
        "wickets_out": 1
    }
    resp = await async_client.post("/api/v1/predictions/ipl", json=payload)
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_ipl_prediction_validation_invalid_overs(async_client):
    """Cannot have overs_completed > 20 or balls_in_over > 5."""
    payload = {
        "batting_team": "Chennai Super Kings",
        "bowling_team": "Mumbai Indians",
        "city": "Chennai",
        "target_score": 180,
        "current_score": 50,
        "overs_completed": 21,
        "balls_in_over": 0,
        "wickets_out": 1
    }
    resp = await async_client.post("/api/v1/predictions/ipl", json=payload)
    assert resp.status_code == 422

def test_ipl_artifact_integrity_verification(tmp_path):
    """Loading an artifact with an unverified/tampered SHA-256 checksum fails closed against trusted anchor."""
    from backend.app.ml.ipl_pipeline import IPLModelService

    fake_model = tmp_path / "tampered.pkl"
    fake_model.write_bytes(b"tampered_fake_pickle_data")

    service = IPLModelService(model_path=str(fake_model))
    loaded = service.load()
    assert loaded is False
    assert service.is_ready is False

def test_ipl_artifact_empty_or_malformed_trusted_anchor_fails_closed(tmp_path):
    """Empty or malformed trusted SHA-256 anchor strictly fails closed and refuses to unpickle."""
    from backend.app.ml.ipl_pipeline import IPLModelService
    from unittest.mock import patch

    fake_model = tmp_path / "dummy.pkl"
    fake_model.write_bytes(b"dummy_data")

    service = IPLModelService(model_path=str(fake_model))

    # Empty trusted anchor
    with patch("backend.app.ml.ipl_pipeline.settings.IPL_MODEL_TRUSTED_SHA256", ""):
        assert service.load() is False
        assert service.is_ready is False

    # Malformed (short) trusted anchor
    with patch("backend.app.ml.ipl_pipeline.settings.IPL_MODEL_TRUSTED_SHA256", "abc123"):
        assert service.load() is False
        assert service.is_ready is False
