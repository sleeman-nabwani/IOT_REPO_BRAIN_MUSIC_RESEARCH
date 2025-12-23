"""
KNN Training Module

Trains a K-Nearest Neighbors regressor to predict the next BPM
based on a sliding window of previous steps.

This is Phase 2 of the KNN research pipeline.

Output:
    - knn_performance.png: Prediction vs actual comparison chart
"""
import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import matplotlib.pyplot as plt
from pathlib import Path
from analyze_data import load_all_sessions

# Output directories for results
RESULTS_DIR = Path(__file__).parent / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
MODELS_DIR = RESULTS_DIR / "models"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

def prepare_dataset(df, window_size=3):
    """
    Creates X (features) and y (target) from the walking_bpm data.
    X = [step_t-3, step_t-2, step_t-1]
    y = step_t
    """
    data = df['walking_bpm'].values
    X, y = [], []
    
    for i in range(len(data) - window_size):
        X.append(data[i : i + window_size])
        y.append(data[i + window_size])
        
    return np.array(X), np.array(y)

def train_knn_model():
    # 1. Load Data
    print("Loading data...")
    logs_dir = r"../server/logs/Default"
    df = load_all_sessions(logs_dir)
    
    if df.empty:
        print("No data found! Creating a DUMMY model to allow app startup.")
        # Create synthetic data so we can at least train a valid model structure
        data = []
        for i in range(50):
            data.append({"walking_bpm": 100 + (i % 5)}) # pattern: 100, 101, 102, 103, 104...
        df = pd.DataFrame(data)


    # Filter Valid Data
    df = df[df['walking_bpm'] > 0]
    print(f"Training on {len(df)} steps.")

    # 2. Auto-Tune: Find optimal lookback window
    print("\nAuto-tuning lookback window...")
    print("-" * 40)
    
    best_window = 3
    best_mae = float('inf')
    results = []
    
    for window in range(2, 11):  # Test windows 2-10
        X, y = prepare_dataset(df, window_size=window)
        if len(X) < 10:
            continue
            
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        knn_temp = KNeighborsRegressor(n_neighbors=5, weights='distance')
        knn_temp.fit(X_train, y_train)
        
        predictions = knn_temp.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        r2 = r2_score(y_test, predictions)
        
        results.append((window, mae, r2))
        print(f"  Window={window}: MAE={mae:.2f} BPM, R²={r2:.3f}")
        
        if mae < best_mae:
            best_mae = mae
            best_window = window
    
    print("-" * 40)
    print(f"[DONE] Best window: {best_window} (MAE={best_mae:.2f} BPM)")
    print()
    
    # 3. Train final model with best window
    WINDOW_SIZE = best_window
    X, y = prepare_dataset(df, window_size=WINDOW_SIZE)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 4. Train KNN
    knn = KNeighborsRegressor(n_neighbors=5, weights='distance')
    knn.fit(X_train, y_train)
    
    # 5. Evaluate
    predictions = knn.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)
    
    print(f"\n" + "="*50)
    print(f"  MODEL PERFORMANCE REPORT")
    print(f"="*50)
    print(f"Mean Absolute Error (MAE): {mae:.2f} BPM")
    print(f"R^2 Score: {r2:.3f}")
    print(f"\n[INFO] HOW TO INTERPRET:")
    print(f"   MAE < 5 BPM  -> Excellent (Usable in production)")
    print(f"   MAE 5-10 BPM -> Good (Noticeable but helpful)")
    print(f"   MAE > 10 BPM -> Poor (Need more/better data)")
    print(f"\n   R^2 > 0.7 -> Strong prediction")
    print(f"   R^2 0.3-0.7 -> Moderate prediction")
    print(f"   R^2 < 0.3 -> Weak prediction")
    print(f"="*50)
    
    # 6. Visualize Prediction vs Reality (subset)
    plt.figure(figsize=(12, 5))
    plt.plot(y_test[:100], label='Actual Next Step', marker='o', markersize=4)
    plt.plot(predictions[:100], label='KNN Prediction', linestyle='--', linewidth=2)
    plt.title(f'KNN Prediction vs Actual - MAE: {mae:.2f} BPM, R²: {r2:.3f}')
    plt.xlabel('Step Index')
    plt.ylabel('BPM')
    plt.legend()
    plt.grid(True, alpha=0.3)
    output_path = PLOTS_DIR / "knn_performance.png"
    plt.savefig(output_path)
    print(f"\nSaved '{output_path}'")
    
    # 7. Export Model
    import joblib
    model_path = MODELS_DIR / "knn_model.joblib"
    joblib.dump({"model": knn, "window": WINDOW_SIZE}, model_path)
    print(f"Model exported to '{model_path}'")
    print(f"\nExample: Input {X_test[0].tolist()} -> Predicted {knn.predict([X_test[0]])[0]:.1f} BPM")
    
    return knn, WINDOW_SIZE

if __name__ == "__main__":
    train_knn_model()
