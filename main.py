"""
Automated Insight Generation Engine - CLI Runner
Executes the analytical pipeline and generates deliverable files.
"""

import argparse
import os
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.data_loader import (
    load_dataset,
    print_dataset_summary,
    validate_schema,
)
from src.analyzer import (
    compute_correlation_matrix,
    detect_outliers_iqr,
    detect_outliers_zscore,
    detect_trends,
    flag_high_correlations,
)
from src.insight_generator import generate_all_insights


def main():
    parser = argparse.ArgumentParser(
        description="Automated Insight Generation Engine for District Healthcare Performance"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=os.path.join("data", "healthcare_data.csv"),
        help="Path to input healthcare performance CSV",
    )
    parser.add_argument(
        "--trend-threshold",
        type=float,
        default=10.0,
        help="Significant trend percent change threshold (default: 10.0%%)",
    )
    parser.add_argument(
        "--outlier-method",
        type=str,
        choices=["iqr", "zscore", "both"],
        default="both",
        help="Outlier detection algorithm (default: both)",
    )
    parser.add_argument(
        "--z-threshold",
        type=float,
        default=2.5,
        help="Z-score threshold for outlier detection (default: 2.5)",
    )
    parser.add_argument(
        "--iqr-multiplier",
        type=float,
        default=1.5,
        help="IQR multiplier for outlier detection (default: 1.5)",
    )
    parser.add_argument(
        "--corr-threshold",
        type=float,
        default=0.70,
        help="Absolute Pearson correlation threshold (default: 0.70)",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default=".",
        help="Directory to save output files (default: current directory)",
    )

    args = parser.parse_args()

    # 1. Part A - Loading and validation
    if not os.path.exists(args.file):
        print(f"Error: Dataset not found at '{args.file}'")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("   AUTOMATED INSIGHT GENERATION ENGINE — EXECUTION PIPELINE   ")
    print("=" * 70)

    df = load_dataset(args.file)
    is_valid, missing_cols = validate_schema(df)
    if not is_valid:
        print(f"Schema Warning: Missing recommended columns {missing_cols}")

    print_dataset_summary(df)

    # 2. Part B - Trend Detection
    print("\n" + "=" * 60)
    print("PART B: TREND DETECTION")
    print("=" * 60)
    trends = detect_trends(df, threshold_pct=args.trend_threshold)
    sig_trends = trends[trends["is_significant"]]
    print(f"Total trend observations computed: {len(trends)}")
    print(f"Significant trends flagged (>= {args.trend_threshold}%): {len(sig_trends)}")
    if not sig_trends.empty:
        print(sig_trends[["district", "indicator", "prev_val", "current_val", "change_pct"]].to_string(index=False))

    # 3. Part C - Outlier Detection
    print("\n" + "=" * 60)
    print("PART C: OUTLIER DETECTION")
    print("=" * 60)
    if args.outlier_method in ["iqr", "both"]:
        iqr_outliers = detect_outliers_iqr(df, iqr_multiplier=args.iqr_multiplier)
        print(f"\n[IQR Method (multiplier={args.iqr_multiplier})] Outliers found: {len(iqr_outliers)}")
        if not iqr_outliers.empty:
            print(iqr_outliers[["district", "indicator", "month", "value", "lower_bound", "upper_bound"]].to_string(index=False))

    if args.outlier_method in ["zscore", "both"]:
        z_outliers = detect_outliers_zscore(df, z_threshold=args.z_threshold)
        print(f"\n[Z-Score Method (threshold={args.z_threshold})] Outliers found: {len(z_outliers)}")
        if not z_outliers.empty:
            print(z_outliers[["district", "indicator", "month", "value", "benchmark_mean", "z_score"]].to_string(index=False))

    # 4. Part D - Correlation Detection
    print("\n" + "=" * 60)
    print("PART D: CORRELATION DETECTION")
    print("=" * 60)
    corr_matrix = compute_correlation_matrix(df)
    print("\n--- Pearson Correlation Matrix ---")
    print(corr_matrix.to_string())

    flagged_corr = flag_high_correlations(corr_matrix, threshold=args.corr_threshold)
    print(f"\nPairs with |r| >= {args.corr_threshold}: {len(flagged_corr)}")
    if not flagged_corr.empty:
        print(flagged_corr[["indicator_pair", "correlation_r", "abs_r"]].to_string(index=False))

    print("\nSTATISTICAL LIMITATION NOTE:")
    print("With only 2 months x 6 districts = 12 rows, Pearson correlation is fragile and highly")
    print("sensitive to individual anomalies. Correlation indicates co-movement, not causation.")

    # 5. Part E - Automated Insight Generation
    print("\n" + "=" * 60)
    print("PART E: AUTOMATED INSIGHT GENERATION")
    print("=" * 60)
    insights = generate_all_insights(
        df,
        trend_threshold_pct=args.trend_threshold,
        outlier_method=args.outlier_method,
        z_threshold=args.z_threshold,
        iqr_multiplier=args.iqr_multiplier,
        corr_threshold=args.corr_threshold,
    )
    print(f"Total Insights Generated: {len(insights)}")
    print("\nBreakdown by Severity:")
    print(insights["severity"].value_counts().to_string())

    print("\nBreakdown by Insight Type:")
    print(insights["type"].value_counts().to_string())

    print("\n--- Generated Insights ---")
    for _, row in insights.iterrows():
        print(f"[{row['insight_id']}] ({row['severity'].upper()}) [{row['type'].upper()}] {row['explanation']}")

    # 6. Export deliverables
    os.makedirs(args.export_dir, exist_ok=True)
    corr_csv_path = os.path.join(args.export_dir, "correlation_matrix.csv")
    insights_csv_path = os.path.join(args.export_dir, "sample_insights.csv")
    insights_json_path = os.path.join(args.export_dir, "sample_insights.json")

    corr_matrix.to_csv(corr_csv_path)
    insights.to_csv(insights_csv_path, index=False)
    insights.to_json(insights_json_path, orient="records", indent=2)

    print("\n" + "=" * 60)
    print("DELIVERABLES EXPORTED SUCCESSFULLY")
    print("=" * 60)
    print(f"1. Correlation Matrix CSV: {corr_csv_path}")
    print(f"2. Sample Insights CSV:    {insights_csv_path}")
    print(f"3. Sample Insights JSON:   {insights_json_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
