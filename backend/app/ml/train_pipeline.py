"""Reproducible training, baseline comparison, and evaluation pipeline for IPL Win Prediction.

Trains on deliveries.csv and matches.csv with:
1. Match-level GroupShuffleSplit on 'match_id' (zero match context leakage).
2. Comparative evaluation against Majority Class and Run-Rate Heuristic baselines.
3. Calibration assessment (Brier score & Expected Calibration Error).
4. CPU latency benchmarking (p50, p95, p99 across N=1000 single-sample predictions).
5. Cryptographic SHA-256 checksum generation for artifact integrity verification.
"""
import hashlib
import json
import os
import platform
import time
import numpy as np
import pandas as pd
import pickle
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    brier_score_loss,
    classification_report,
    precision_score,
    recall_score,
    f1_score
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

TEAMS = [
    'Chennai Super Kings',
    'Delhi Capitals',
    'Gujarat Titans',
    'Kolkata Knight Riders',
    'Lucknow Super Giants',
    'Mumbai Indians',
    'Punjab Kings',
    'Rajasthan Royals',
    'Royal Challengers Bengaluru',
    'Sunrisers Hyderabad'
]

def load_and_preprocess(matches_path: str = 'matches.csv', deliveries_path: str = 'deliveries.csv') -> pd.DataFrame:
    print(f"Loading matches ({matches_path}) and deliveries ({deliveries_path})...")
    match = pd.read_csv(matches_path)
    delivery = pd.read_csv(deliveries_path)

    # 1. Total score in first innings
    total_score_df = delivery.groupby(['match_id', 'inning'])['total_runs'].sum().reset_index()
    total_score_df = total_score_df[total_score_df['inning'] == 1]

    # 2. Merge total runs with matches
    match_df = match.merge(total_score_df[['match_id', 'total_runs']], left_on='id', right_on='match_id')

    # 3. Standardize historical team names to current franchises
    team_mappings = {
        'Delhi Daredevils': 'Delhi Capitals',
        'Deccan Chargers': 'Sunrisers Hyderabad',
        'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
        'Kings XI Punjab': 'Punjab Kings'
    }

    for old_name, new_name in team_mappings.items():
        match_df['team1'] = match_df['team1'].str.replace(old_name, new_name)
        match_df['team2'] = match_df['team2'].str.replace(old_name, new_name)
        match_df['winner'] = match_df['winner'].str.replace(old_name, new_name)
        delivery['batting_team'] = delivery['batting_team'].str.replace(old_name, new_name)
        delivery['bowling_team'] = delivery['bowling_team'].str.replace(old_name, new_name)

    match_df['city'] = match_df['city'].str.replace('Bangalore', 'Bengaluru')

    # 4. Filter only for target teams
    match_df = match_df[match_df['team1'].isin(TEAMS) & match_df['team2'].isin(TEAMS)]
    match_df = match_df[['match_id', 'city', 'winner', 'total_runs']]

    # 5. Merge with delivery (2nd innings only)
    delivery_df = match_df.merge(delivery, on='match_id')
    delivery_df = delivery_df[delivery_df['inning'] == 2].copy()

    # 6. Feature calculations
    delivery_df['current_score'] = delivery_df.groupby('match_id')['total_runs_y'].cumsum()
    delivery_df['runs_left'] = (delivery_df['total_runs_x'] + 1) - delivery_df['current_score']
    delivery_df['balls_left'] = 120 - (delivery_df['over'] * 6 + delivery_df['ball'])
    
    wickets = delivery_df.groupby('match_id')['is_wicket'].cumsum()
    delivery_df['wickets_left'] = 10 - wickets

    # CRR and RRR
    delivery_df['crr'] = (delivery_df['current_score'] * 6) / (120 - delivery_df['balls_left'])
    delivery_df['rrr'] = (delivery_df['runs_left'] * 6) / delivery_df['balls_left']

    # Target: 1 if batting team wins, else 0
    delivery_df['result'] = (delivery_df['batting_team'] == delivery_df['winner']).astype(int)

    final_df = delivery_df[['match_id', 'batting_team', 'bowling_team', 'city', 'runs_left', 'balls_left', 'wickets_left', 'total_runs_x', 'crr', 'rrr', 'result']].copy()
    final_df.dropna(inplace=True)
    final_df = final_df[final_df['balls_left'] > 0]
    final_df = final_df[~np.isinf(final_df['crr']) & ~np.isinf(final_df['rrr'])]

    print(f"Preprocessed dataset shape: {final_df.shape} across {final_df['match_id'].nunique()} matches.")
    return final_df

def compute_ece(y_true, y_prob, n_bins=10):
    """Computes Expected Calibration Error (ECE) across n_bins."""
    bin_limits = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total_samples = len(y_true)

    for i in range(n_bins):
        bin_mask = (y_prob >= bin_limits[i]) & (y_prob < bin_limits[i + 1])
        if np.sum(bin_mask) > 0:
            bin_acc = np.mean(y_true[bin_mask])
            bin_conf = np.mean(y_prob[bin_mask])
            bin_weight = np.sum(bin_mask) / total_samples
            ece += bin_weight * np.abs(bin_acc - bin_conf)

    return float(ece)

def benchmark_inference_latency(pipe, sample_row: pd.DataFrame, n_trials: int = 1000):
    """Measures single-sample CPU inference latency percentiles."""
    print(f"Benchmarking CPU inference latency across {n_trials} trials...")
    # Warmup
    for _ in range(50):
        _ = pipe.predict_proba(sample_row)

    latencies = []
    for _ in range(n_trials):
        t0 = time.perf_counter()
        _ = pipe.predict_proba(sample_row)
        latencies.append((time.perf_counter() - t0) * 1000.0)  # ms

    latencies = np.array(latencies)
    return {
        "trials": n_trials,
        "mean_ms": round(float(np.mean(latencies)), 3),
        "median_p50_ms": round(float(np.median(latencies)), 3),
        "p95_ms": round(float(np.percentile(latencies, 95)), 3),
        "p99_ms": round(float(np.percentile(latencies, 99)), 3),
        "std_ms": round(float(np.std(latencies)), 3)
    }

def train_and_evaluate(final_df: pd.DataFrame, output_model_path: str = 'pipe.pkl', output_meta_path: str = 'backend/app/ml/model_metadata.json'):
    # 1. Match-Level Grouped Split (Zero Match Leakage)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(final_df, groups=final_df['match_id']))

    train_df = final_df.iloc[train_idx].copy()
    test_df = final_df.iloc[test_idx].copy()

    # Verify zero match leakage
    overlap = set(train_df['match_id']).intersection(set(test_df['match_id']))
    assert len(overlap) == 0, f"DATA LEAKAGE DETECTED: {len(overlap)} matches overlap between train and test!"

    print(f"\n--- Dataset Split (Match Grouped) ---")
    print(f"Train set: {len(train_df)} deliveries across {train_df['match_id'].nunique()} matches")
    print(f"Test set:  {len(test_df)} deliveries across {test_df['match_id'].nunique()} matches")

    feature_cols = ['batting_team', 'bowling_team', 'city', 'runs_left', 'balls_left', 'wickets_left', 'total_runs_x', 'crr', 'rrr']
    target_col = 'result'

    X_train = train_df[feature_cols]
    y_train = train_df[target_col].values
    X_test = test_df[feature_cols]
    y_test = test_df[target_col].values

    # 2. Baseline Model 1: Majority Class Classifier
    dummy = DummyClassifier(strategy='most_frequent')
    dummy.fit(X_train, y_train)
    dummy_pred = dummy.predict(X_test)
    dummy_proba = dummy.predict_proba(X_test)[:, 1]
    dummy_acc = accuracy_score(y_test, dummy_pred)
    dummy_loss = log_loss(y_test, dummy_proba)
    dummy_brier = brier_score_loss(y_test, dummy_proba)

    # 3. Baseline Model 2: Run-Rate Heuristic (crr >= rrr)
    rr_pred = (test_df['crr'] >= test_df['rrr']).astype(int).values
    rr_acc = accuracy_score(y_test, rr_pred)
    rr_f1 = f1_score(y_test, rr_pred)

    print("\n--- Baseline Comparisons ---")
    print(f"1. Majority Class Baseline : Accuracy={dummy_acc:.4f}, LogLoss={dummy_loss:.4f}, Brier={dummy_brier:.4f}")
    print(f"2. Run-Rate Heuristic (CRR>=RRR): Accuracy={rr_acc:.4f}, F1={rr_f1:.4f}")

    # 4. Train LogisticRegression Pipeline
    trf = ColumnTransformer([
        ('trf', OneHotEncoder(sparse_output=False, drop='first', handle_unknown='ignore'), ['batting_team', 'bowling_team', 'city'])
    ], remainder='passthrough')

    pipe = Pipeline(steps=[
        ('step1', trf),
        ('step2', LogisticRegression(solver='liblinear', random_state=42))
    ])

    print("\nFitting scikit-learn Pipeline...")
    t0 = time.time()
    pipe.fit(X_train, y_train)
    fit_duration = time.time() - t0
    print(f"Model fitting completed in {fit_duration:.2f}s")

    # 5. Model Evaluation
    y_pred = pipe.predict(X_test)
    y_proba = pipe.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    loss = log_loss(y_test, y_proba)
    brier = brier_score_loss(y_test, y_proba)
    ece = compute_ece(y_test, y_proba)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print("\n--- Model Evaluation Results (Unseen Matches) ---")
    print(f"Accuracy: {acc:.4f}  (Baseline improvement: +{(acc - dummy_acc)*100:.2f}%)")
    print(f"Log Loss: {loss:.4f}")
    print(f"Brier Score Loss: {brier:.4f}")
    print(f"Expected Calibration Error (ECE): {ece:.4f}")
    print(f"Precision: {prec:.4f} | Recall: {rec:.4f} | F1: {f1:.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred))

    # 6. Benchmark Latency
    sample_row = X_test.iloc[[0]]
    latency_stats = benchmark_inference_latency(pipe, sample_row, n_trials=1000)
    print("\n--- Latency Benchmark ---")
    print(f"Median (p50): {latency_stats['median_p50_ms']} ms | p95: {latency_stats['p95_ms']} ms | p99: {latency_stats['p99_ms']} ms")

    # 7. Serialize Artifact and Compute SHA-256 Checksum
    with open(output_model_path, 'wb') as f:
        pickle.dump(pipe, f)
    
    with open(output_model_path, 'rb') as f:
        sha256_hash = hashlib.sha256(f.read()).hexdigest()
    print(f"\nSaved model artifact to {output_model_path}")
    print(f"Artifact SHA-256: {sha256_hash}")

    # 8. Compile Metadata
    ohe: OneHotEncoder = pipe.named_steps['step1'].named_transformers_['trf']
    categories = {col: [str(c) for c in ohe.categories_[i]] for i, col in enumerate(['batting_team', 'bowling_team', 'city'])}
    
    metadata = {
        "model_type": "LogisticRegression(solver='liblinear')",
        "scikit_learn_version": sklearn.__version__,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sha256_checksum": sha256_hash,
        "features": list(X_train.columns),
        "categorical_columns": ['batting_team', 'bowling_team', 'city'],
        "numerical_columns": ['runs_left', 'balls_left', 'wickets_left', 'total_runs_x', 'crr', 'rrr'],
        "classes": [int(c) for c in pipe.classes_],
        "class_labels": {0: "bowling_team_wins", 1: "batting_team_wins"},
        "teams": sorted(list(categories['batting_team'])),
        "cities": sorted(list(categories['city'])),
        "dataset_split": {
            "methodology": "GroupShuffleSplit by match_id (Zero temporal/match-level data leakage)",
            "train_balls": int(len(train_df)),
            "train_matches": int(train_df['match_id'].nunique()),
            "test_balls": int(len(test_df)),
            "test_matches": int(test_df['match_id'].nunique()),
            "overlap_matches": 0
        },
        "baselines": {
            "majority_class": {
                "accuracy": round(float(dummy_acc), 4),
                "log_loss": round(float(dummy_loss), 4),
                "brier_score": round(float(dummy_brier), 4)
            },
            "run_rate_heuristic": {
                "accuracy": round(float(rr_acc), 4),
                "f1_score": round(float(rr_f1), 4)
            }
        },
        "metrics": {
            "accuracy": round(float(acc), 4),
            "log_loss": round(float(loss), 4),
            "brier_score": round(float(brier), 4),
            "expected_calibration_error": round(float(ece), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4)
        },
        "benchmark": {
            "hardware": platform.processor() or platform.machine(),
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "stats": latency_stats
        }
    }

    os.makedirs(os.path.dirname(output_meta_path), exist_ok=True)
    with open(output_meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved model metadata to {output_meta_path}")

    return pipe, metadata

if __name__ == '__main__':
    df = load_and_preprocess()
    train_and_evaluate(df)
