# Research Module

Experimental scripts for **Predictive BPM Estimation** using machine learning.

## Goal

Instead of reacting to steps *after* they happen, can we **predict** the user's next BPM based on their walking pattern? This would allow the music to anticipate tempo changes.

## Scripts

### 1. `analyze_data.py` - Data Exploration
- Loads all session CSVs from `server/logs/Default`
- Generates distribution histograms
- Creates correlation plots (User BPM vs Music BPM)

**Output:** `bpm_distribution.png`

### 2. `train_knn.py` - KNN Model Training
- Uses a **sliding window** approach (last 3 steps → predict next)
- Trains a K-Nearest Neighbors regressor
- Evaluates with Mean Absolute Error (MAE)

**Output:** `knn_performance.png`

## Usage

```bash
cd research
python analyze_data.py   # Visualize the data
python train_knn.py      # Train and evaluate KNN
```

## Next Steps

- [ ] Export trained model with `joblib` for integration
- [ ] Test different window sizes (3, 5, 10 steps)
- [ ] Compare with simple moving average baseline
- [ ] Add cross-validation for robust evaluation
