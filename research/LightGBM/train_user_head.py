"""
Lightweight CLI to train a per-user calibration head on top of the base
LightGBM model. You can point it at:
  - a CSV file with at least 'walking_bpm' (and optionally 'session_id'), or
  - a directory containing session_data.csv files, or
  - a user name, in which case it will look under server/logs/<user_name>.

Usage:
    python train_user_head.py --path path/to/user.csv|user_dir [--base-model ...] [--suffix user123]
    python train_user_head.py --user "Sonic wesh wesh" [--base-model ...] [--suffix user123]
"""
import argparse
from pathlib import Path

import pandas as pd

from train_lgbm import (
    filter_bpm_range,
    filter_true_steps,
    train_user_calibration,
    load_all_sessions,
    BASE_DIR,
)


def main():
    parser = argparse.ArgumentParser(description="Train per-user calibration head for LightGBM.")
    parser.add_argument(
        "--path",
        help="Path to user CSV or directory containing session_data.csv files.",
    )
    parser.add_argument(
        "--user",
        help="User name; looks under server/logs/<user> for session_data.csv files.",
    )
    parser.add_argument(
        "--base-model",
        default=str(Path(__file__).parent / "results" / "models" / "lgbm_model.joblib"),
        help="Path to base LightGBM model artifact (joblib).",
    )
    parser.add_argument("--suffix", default="user", help="Identifier suffix for the saved head file.")
    args = parser.parse_args()

    if not args.path and not args.user:
        raise ValueError("Provide either --path or --user.")

    if args.user and not args.path:
        user_path = BASE_DIR / "server" / "logs" / args.user
    else:
        user_path = Path(args.path)

    if not user_path.exists():
        raise FileNotFoundError(f"User path not found: {user_path}")

    if user_path.is_dir():
        # Load all session_data.csv under this directory
        df = load_all_sessions(str(user_path))
    else:
        df = pd.read_csv(user_path)
        if "session_id" not in df.columns:
            df["session_id"] = "user_session"

    if "walking_bpm" not in df.columns:
        raise ValueError("Data must contain 'walking_bpm' column.")

    df = filter_bpm_range(df)
    df = filter_true_steps(df)
    calibrator, head_path = train_user_calibration(
        df,
        base_model_path=Path(args.base_model),
        output_suffix=args.suffix,
    )
    print(f"Saved user head: {head_path}")


if __name__ == "__main__":
    main()

