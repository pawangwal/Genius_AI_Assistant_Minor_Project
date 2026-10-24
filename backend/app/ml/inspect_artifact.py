"""Deep artifact inspection for pipe.pkl.

Extracts:
1. Pipeline steps and classes
2. Feature names and column transformer mappings
3. OneHotEncoder categories and drop strategy
4. Classifier coefficients, intercepts, and target class labels
5. Test prediction with sample input to verify reproducible output
"""
import pickle
import sys
import pandas as pd
import numpy as np

def inspect_pipeline(pickle_path: str = "pipe.pkl"):
    print(f"--- Loading Artifact: {pickle_path} ---")
    try:
        with open(pickle_path, "rb") as f:
            pipe = pickle.load(f)
    except Exception as e:
        print(f"Error loading {pickle_path}: {e}")
        sys.exit(1)

    print(f"Pipeline Object: {type(pipe)}")
    print(f"Steps: {pipe.steps}")
    
    # Step 1: ColumnTransformer
    step1 = pipe.named_steps.get("step1")
    print(f"\nStep 1 (Transformer): {type(step1)}")
    if step1:
        print(f"Transformers: {step1.transformers}")
        for name, trf, cols in step1.transformers:
            print(f"  Name: {name}, Columns: {cols}")
            if hasattr(trf, "categories_"):
                print(f"  OHE Categories count: {[len(c) for c in trf.categories_]}")
                for i, col in enumerate(cols):
                    print(f"    Categories for {col} ({len(trf.categories_[i])}): {list(trf.categories_[i])[:10]}...")
            if hasattr(trf, "drop_"):
                print(f"  Drop strategy: {getattr(trf, 'drop', None)}")

    # Step 2: Classifier
    step2 = pipe.named_steps.get("step2")
    print(f"\nStep 2 (Classifier): {type(step2)}")
    if step2:
        print(f"Classes: {getattr(step2, 'classes_', None)}")
        print(f"Solver: {getattr(step2, 'solver', None)}")
        if hasattr(step2, "coef_"):
            print(f"Coefficients shape: {step2.coef_.shape}")

    # Test sample inference
    print("\n--- Running Verification Inference ---")
    test_df = pd.DataFrame([{
        "batting_team": "Chennai Super Kings",
        "bowling_team": "Mumbai Indians",
        "city": "Chennai",
        "runs_left": 35,
        "balls_left": 24,
        "wickets_left": 6,
        "total_runs_x": 160,
        "crr": 7.8125,
        "rrr": 8.75
    }])
    
    try:
        pred_class = pipe.predict(test_df)
        pred_proba = pipe.predict_proba(test_df)
        print(f"Test Input:\n{test_df.to_dict(orient='records')[0]}")
        print(f"Predicted Class: {pred_class[0]}")
        print(f"Predicted Probabilities: {pred_proba[0]} (Classes: {getattr(step2, 'classes_', [0, 1])})")
        print("Pipeline verification successful!")
    except Exception as e:
        print(f"Test inference failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "pipe.pkl"
    inspect_pipeline(path)
