#!/usr/bin/env python3
"""
Test extreme anomaly use cases against all models via the API.

Injects use case records from data/test/use_cases_extreme_anomalies.json
and validates that both the Autoencoder and Statistical models detect them.

Usage:
    python utils/test_use_cases.py [--api-url http://localhost:8000]
"""

import json
import sys
import time
import argparse
import requests
from pathlib import Path


USE_CASES_FILE = Path(__file__).parent.parent / "data" / "test" / "use_cases_extreme_anomalies.json"

MODELS = [
    "isolation_forest_model",
    "statistical_model",
    "autoencoder_model",
    "gan_model",
    "one_class_svm_model",
    "ensemble_model",
]


def load_use_cases():
    with open(USE_CASES_FILE) as f:
        data = json.load(f)

    records = []
    names = []
    for uc in data["use_cases"]:
        if "record" in uc:
            records.append(uc["record"])
            names.append(uc["name"])
        elif "records" in uc:
            for rec in uc["records"]:
                records.append(rec)
                names.append(uc["name"])
    return records, names, data["use_cases"]


def detect_with_model(api_url, model_name, records):
    """Submit detection request and wait for result."""
    payload = {"items": records}
    resp = requests.post(f"{api_url}/models/{model_name}/detect", json=payload, timeout=30)
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text}"}

    job = resp.json()
    job_id = job.get("job_id")
    if not job_id:
        return {"error": f"No job_id: {job}"}

    # Poll for completion
    for _ in range(60):
        time.sleep(0.5)
        status_resp = requests.get(f"{api_url}/jobs/{job_id}", timeout=10)
        if status_resp.status_code != 200:
            continue
        status = status_resp.json()
        if status.get("status") in ("completed", "failed"):
            return status.get("result", {})

    return {"error": "timeout"}


def main():
    parser = argparse.ArgumentParser(description="Test extreme anomaly use cases")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")

    # Verify API is up
    try:
        health = requests.get(f"{api_url}/health", timeout=5).json()
        if not health.get("initialized"):
            print("ERROR: API not initialized")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to API: {e}")
        sys.exit(1)

    print("=" * 70)
    print("EXTREME ANOMALY USE CASE VALIDATION")
    print("=" * 70)

    records, names, use_cases = load_use_cases()
    print(f"\nLoaded {len(records)} records from {len(use_cases)} use cases\n")

    # Run detection for each model
    results = {}
    for model in MODELS:
        print(f"Testing {model}...", end=" ", flush=True)
        result = detect_with_model(api_url, model, records)
        detected = result.get("anomalies_detected", 0)
        results[model] = result
        print(f"{detected}/{len(records)} detected")

    # Summary table
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"\n{'Model':<30} {'Detected':>10} {'Rate':>10}")
    print("-" * 50)

    for model in MODELS:
        result = results[model]
        if "error" in result:
            print(f"{model:<30} {'ERROR':>10} {result['error']}")
        else:
            detected = result.get("anomalies_detected", 0)
            rate = f"{100 * detected / len(records):.1f}%"
            print(f"{model:<30} {detected:>10} {rate:>10}")

    # Focus on target models
    print("\n" + "=" * 70)
    print("TARGET MODEL ANALYSIS (Autoencoder + Statistical)")
    print("=" * 70)

    for target in ["autoencoder_model", "statistical_model"]:
        result = results.get(target, {})
        detected = result.get("anomalies_detected", 0)
        samples = result.get("sample_anomalies", [])

        print(f"\n--- {target} ---")
        print(f"  Detected: {detected}/{len(records)}")

        if samples:
            print(f"  Sample anomalies:")
            for s in samples[:5]:
                score = s.get("score", "?")
                rec_id = s.get("id", s.get("original_data", {}).get("id", "?"))
                details = s.get("details", {})
                print(f"    - id={rec_id}, score={score}")
                if "reconstruction_error" in details:
                    print(f"      reconstruction_error={details['reconstruction_error']:.6f}")
                if "raw_z_score" in details:
                    print(f"      raw_z_score={details['raw_z_score']:.4f}")
        else:
            print(f"  No anomalies detected - model may need threshold tuning")

    # Ensemble breakdown
    ens_result = results.get("ensemble_model", {})
    ens_samples = ens_result.get("sample_anomalies", [])
    if ens_samples:
        print(f"\n--- ensemble_model ---")
        print(f"  Detected: {ens_result.get('anomalies_detected', 0)}/{len(records)}")
        for s in ens_samples[:3]:
            details = s.get("details", {})
            individual = details.get("individual_scores", [])
            if individual:
                models_str = ", ".join(f"{i['model']}={i['score']:.3f}" for i in individual)
                print(f"    combined={details.get('combined_score', '?'):.3f} [{models_str}]")

    # Final verdict
    print("\n" + "=" * 70)
    auto_detected = results.get("autoencoder_model", {}).get("anomalies_detected", 0)
    stat_detected = results.get("statistical_model", {}).get("anomalies_detected", 0)

    if auto_detected > 0 and stat_detected > 0:
        print("PASS: Both Autoencoder and Statistical models detect extreme anomalies")
    elif auto_detected > 0:
        print("PARTIAL: Autoencoder detects, Statistical does not (may need threshold tuning)")
    elif stat_detected > 0:
        print("PARTIAL: Statistical detects, Autoencoder does not (may need threshold tuning)")
    else:
        print("FAIL: Neither model detects extreme anomalies - further investigation needed")
    print("=" * 70)


if __name__ == "__main__":
    main()
