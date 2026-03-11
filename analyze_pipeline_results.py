#!/usr/bin/env python3
"""
Pipeline Results Analyzer
Analyzes results from pipeline execution including training, testing, validation, and detection.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api_client import AnomalyDetectionClient
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False
    print("⚠️  API client not available, will analyze static reports only")

API_URL = "http://localhost:8000"

def analyze_master_pipeline_reports():
    """Analyze master pipeline summary reports."""
    print("\n" + "="*70)
    print("MASTER PIPELINE REPORTS ANALYSIS")
    print("="*70)
    
    reports_dir = Path("reports/master_pipeline")
    if not reports_dir.exists():
        print("❌ No master pipeline reports found")
        return None
    
    # Find all summary reports
    reports = sorted(reports_dir.glob("summary_*.md"), reverse=True)
    
    if not reports:
        print("❌ No summary reports found")
        return None
    
    print(f"\n📊 Found {len(reports)} master pipeline report(s)")
    
    # Analyze most recent report
    latest_report = reports[0]
    print(f"\n📄 Latest Report: {latest_report.name}")
    print(f"   Generated: {datetime.fromtimestamp(latest_report.stat().st_mtime)}")
    
    with open(latest_report, 'r') as f:
        content = f.read()
        print("\n" + content)
    
    return latest_report

def analyze_training_reports():
    """Analyze training pipeline reports."""
    print("\n" + "="*70)
    print("TRAINING REPORTS ANALYSIS")
    print("="*70)
    
    reports_dir = Path("reports/training")
    if not reports_dir.exists():
        print("❌ No training reports found")
        return None
    
    reports = sorted(reports_dir.glob("*.md"), reverse=True)
    
    if not reports:
        print("❌ No training reports found")
        return None
    
    print(f"\n📊 Found {len(reports)} training report(s)")
    
    for report in reports[:3]:  # Show top 3
        print(f"\n📄 {report.name}")
        with open(report, 'r') as f:
            content = f.read()
            # Extract key information
            if "Models Trained" in content:
                print("   ✓ Models were trained")
            if "Training completed" in content:
                print("   ✓ Training completed successfully")
            if "Failed" in content or "Error" in content:
                print("   ⚠️  Contains errors or failures")
    
    return reports[0] if reports else None

def analyze_test_reports():
    """Analyze test pipeline reports."""
    print("\n" + "="*70)
    print("TEST REPORTS ANALYSIS")
    print("="*70)
    
    reports_dir = Path("reports/test")
    if not reports_dir.exists():
        print("❌ No test reports found")
        return None
    
    reports = sorted(reports_dir.glob("*.md"), reverse=True)
    txt_reports = sorted(reports_dir.glob("*.txt"), reverse=True)
    
    print(f"\n📊 Found {len(reports)} markdown report(s) and {len(txt_reports)} text report(s)")
    
    if reports:
        latest = reports[0]
        print(f"\n📄 Latest Test Report: {latest.name}")
        with open(latest, 'r') as f:
            content = f.read()
            print("\n" + content[:500] + "..." if len(content) > 500 else content)
    
    return reports[0] if reports else None

def analyze_detection_logs():
    """Analyze detection pipeline logs."""
    print("\n" + "="*70)
    print("DETECTION PIPELINE LOGS ANALYSIS")
    print("="*70)
    
    logs_dir = Path("logs")
    detection_logs = sorted(logs_dir.glob("detect_pipeline_*.log"), reverse=True)
    
    if not detection_logs:
        print("❌ No detection pipeline logs found")
        return None
    
    print(f"\n📊 Found {len(detection_logs)} detection log(s)")
    
    latest_log = detection_logs[0]
    print(f"\n📄 Latest Detection Log: {latest_log.name}")
    print(f"   Size: {latest_log.stat().st_size / 1024:.1f} KB")
    
    with open(latest_log, 'r') as f:
        lines = f.readlines()
        print(f"   Total lines: {len(lines)}")
        
        # Analyze log content
        stages = defaultdict(int)
        errors = []
        successes = []
        
        for i, line in enumerate(lines):
            if "[STAGE]" in line:
                stage = line.split("[STAGE]")[1].strip()
                stages[stage] += 1
            if "[SUCCESS]" in line:
                successes.append((i+1, line.strip()))
            if "[ERROR]" in line or "Error" in line or "Failed" in line:
                errors.append((i+1, line.strip()))
        
        print(f"\n📈 Stages Executed:")
        for stage, count in stages.items():
            print(f"   - {stage}: {count} occurrence(s)")
        
        print(f"\n✅ Successes: {len(successes)}")
        if successes:
            print("   Recent successes:")
            for line_num, msg in successes[-5:]:
                print(f"   Line {line_num}: {msg[:80]}")
        
        print(f"\n❌ Errors: {len(errors)}")
        if errors:
            print("   Recent errors:")
            for line_num, msg in errors[-5:]:
                print(f"   Line {line_num}: {msg[:80]}")
        
        # Show last 20 lines
        print(f"\n📋 Last 20 lines of log:")
        print("-" * 70)
        for line in lines[-20:]:
            print(line.rstrip())
    
    return latest_log

def analyze_api_results():
    """Analyze current API state and results."""
    if not API_AVAILABLE:
        print("\n⚠️  API client not available, skipping API analysis")
        return None
    
    print("\n" + "="*70)
    print("API RESULTS ANALYSIS")
    print("="*70)
    
    try:
        client = AnomalyDetectionClient(API_URL)
        
        # Health check
        print("\n🏥 API Health Check:")
        health = client.health_check()
        print(json.dumps(health, indent=2))
        
        # System status
        print("\n📊 System Status:")
        status = client.system_status()
        print(json.dumps(status, indent=2))
        
        # List models
        print("\n🤖 Available Models:")
        models = client.list_models()
        for model in models:
            if isinstance(model, dict):
                print(f"   - {model.get('name', 'Unknown')}: {model.get('status', 'Unknown')}")
            else:
                print(f"   - {model}")
        
        # List anomalies
        print("\n🔍 Detected Anomalies:")
        anomalies = client.list_anomalies(limit=50)
        print(f"   Total anomalies: {len(anomalies)}")
        
        if anomalies:
            # Group by severity
            severity_counts = defaultdict(int)
            model_counts = defaultdict(int)
            
            for anomaly in anomalies:
                severity = anomaly.get('severity', 'Unknown')
                model = anomaly.get('model', 'Unknown')
                severity_counts[severity] += 1
                model_counts[model] += 1
            
            print("\n   Severity Breakdown:")
            for severity, count in sorted(severity_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"   - {severity}: {count}")
            
            print("\n   Model Breakdown:")
            for model, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"   - {model}: {count}")
            
            # Top anomalies
            print("\n   Top 5 Anomalies (by score):")
            sorted_anomalies = sorted(anomalies, key=lambda x: x.get('score', 0), reverse=True)
            for i, anomaly in enumerate(sorted_anomalies[:5], 1):
                print(f"\n   {i}. ID: {anomaly.get('id', 'N/A')}")
                print(f"      Score: {anomaly.get('score', 'N/A'):.4f}")
                print(f"      Severity: {anomaly.get('severity', 'N/A')}")
                print(f"      Model: {anomaly.get('model', 'N/A')}")
                print(f"      Time: {anomaly.get('detection_time', 'N/A')}")
        
        # List jobs
        print("\n📋 Recent Jobs:")
        jobs = client.list_jobs(limit=10)
        print(f"   Total jobs: {len(jobs)}")
        
        job_statuses = defaultdict(int)
        for job in jobs:
            status = job.get('status', 'Unknown')
            job_statuses[status] += 1
        
        print("\n   Job Status Breakdown:")
        for status, count in sorted(job_statuses.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {status}: {count}")
        
        # Correlation statistics
        print("\n🔗 Correlation Statistics:")
        try:
            corr_stats = client.get_correlation_statistics()
            print(json.dumps(corr_stats, indent=2))
        except Exception as e:
            print(f"   ⚠️  Could not retrieve correlation statistics: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        return False

def generate_summary_report():
    """Generate a comprehensive summary report."""
    print("\n" + "="*70)
    print("GENERATING COMPREHENSIVE SUMMARY")
    print("="*70)
    
    summary = {
        "analysis_time": datetime.now().isoformat(),
        "reports_analyzed": {},
        "api_available": API_AVAILABLE,
        "findings": []
    }
    
    # Analyze reports
    master_report = analyze_master_pipeline_reports()
    training_report = analyze_training_reports()
    test_report = analyze_test_reports()
    detection_log = analyze_detection_logs()
    
    summary["reports_analyzed"] = {
        "master_pipeline": str(master_report) if master_report else None,
        "training": str(training_report) if training_report else None,
        "test": str(test_report) if test_report else None,
        "detection_log": str(detection_log) if detection_log else None
    }
    
    # Analyze API if available
    if API_AVAILABLE:
        api_result = analyze_api_results()
        summary["api_analysis"] = api_result
    
    # Generate findings
    findings = []
    
    if master_report:
        findings.append("✅ Master pipeline reports found")
    else:
        findings.append("⚠️  No master pipeline reports found")
    
    if training_report:
        findings.append("✅ Training reports found")
    else:
        findings.append("⚠️  No training reports found")
    
    if detection_log:
        findings.append("✅ Detection pipeline logs found")
    else:
        findings.append("⚠️  No detection pipeline logs found")
    
    summary["findings"] = findings
    
    # Save summary
    summary_file = Path("reports/pipeline_analysis_summary.json")
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Summary saved to: {summary_file}")
    
    return summary

def main():
    """Main execution function."""
    print("="*70)
    print("PIPELINE RESULTS ANALYZER")
    print("="*70)
    print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run analysis
    summary = generate_summary_report()
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

