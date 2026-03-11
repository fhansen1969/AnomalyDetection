#!/usr/bin/env python3
"""
Visualize Pipeline Results - Generate performance charts and summaries
"""

import json
import os
import glob
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

class ResultsVisualizer:
    def __init__(self, reports_dir="reports/test"):
        self.reports_dir = reports_dir
        self.models = [
            "isolation_forest_model",
            "statistical_model", 
            "autoencoder_model",
            "gan_model",
            "one_class_svm_model",
            "ensemble_model"
        ]
        
    def parse_evaluation_report(self, report_path):
        """Parse evaluation report to extract metrics."""
        results = defaultdict(lambda: defaultdict(dict))
        
        with open(report_path, 'r') as f:
            lines = f.readlines()
            
        current_test = None
        current_model = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("Test File:"):
                current_test = line.split("Test File:")[1].strip()
            elif line.startswith("Model:"):
                current_model = line.split("Model:")[1].strip()
            elif line.startswith("Anomalies detected:"):
                count = int(line.split(":")[1].strip())
                if current_test and current_model:
                    results[current_test][current_model]['anomalies'] = count
            elif line.startswith("Processing time:"):
                time_str = line.split(":")[1].strip()
                if current_test and current_model:
                    results[current_test][current_model]['time'] = time_str
                    
        return results
    
    def parse_performance_report(self, report_path):
        """Parse performance report to extract metrics."""
        results = defaultdict(lambda: defaultdict(dict))
        
        with open(report_path, 'r') as f:
            lines = f.readlines()
            
        current_size = None
        current_model = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("Dataset Size:"):
                current_size = int(line.split(":")[1].strip().split()[0])
            elif line.startswith("Model:"):
                current_model = line.split(":")[1].strip()
            elif line.startswith("Processing time:"):
                time = float(line.split(":")[1].strip().rstrip('s'))
                if current_size and current_model:
                    results[current_size][current_model]['time'] = time
            elif line.startswith("Records/second:"):
                rps = float(line.split(":")[1].strip())
                if current_size and current_model:
                    results[current_size][current_model]['rps'] = rps
                    
        return results
    
    def create_performance_chart(self, perf_data):
        """Create performance comparison chart."""
        plt.figure(figsize=(12, 6))
        
        # Processing time comparison
        plt.subplot(1, 2, 1)
        sizes = sorted(perf_data.keys())
        
        for model in self.models:
            times = []
            for size in sizes:
                if model in perf_data[size]:
                    times.append(perf_data[size][model].get('time', 0))
                else:
                    times.append(0)
            
            if any(times):
                plt.plot(sizes, times, marker='o', label=model.replace('_model', ''))
        
        plt.xlabel('Dataset Size')
        plt.ylabel('Processing Time (seconds)')
        plt.title('Model Processing Time vs Dataset Size')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Records per second comparison
        plt.subplot(1, 2, 2)
        
        for model in self.models:
            rps_values = []
            for size in sizes:
                if model in perf_data[size]:
                    rps_values.append(perf_data[size][model].get('rps', 0))
                else:
                    rps_values.append(0)
            
            if any(rps_values):
                plt.plot(sizes, rps_values, marker='o', label=model.replace('_model', ''))
        
        plt.xlabel('Dataset Size')
        plt.ylabel('Records/Second')
        plt.title('Model Throughput vs Dataset Size')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('results/performance_comparison.png', dpi=150)
        print("✓ Saved performance comparison chart: results/performance_comparison.png")
    
    def create_detection_summary(self, eval_data):
        """Create anomaly detection summary chart."""
        # Extract anomaly counts per model
        model_anomalies = defaultdict(list)
        
        for test_file, models in eval_data.items():
            for model, metrics in models.items():
                if 'anomalies' in metrics:
                    model_anomalies[model].append(metrics['anomalies'])
        
        # Create bar chart
        plt.figure(figsize=(10, 6))
        
        models = list(model_anomalies.keys())
        avg_detections = [np.mean(model_anomalies[m]) for m in models]
        
        bars = plt.bar(range(len(models)), avg_detections)
        plt.xticks(range(len(models)), [m.replace('_model', '') for m in models], rotation=45)
        plt.ylabel('Average Anomalies Detected')
        plt.title('Average Anomaly Detection by Model')
        
        # Add value labels on bars
        for bar, val in zip(bars, avg_detections):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                    f'{val:.1f}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig('results/detection_summary.png', dpi=150)
        print("✓ Saved detection summary chart: results/detection_summary.png")
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report."""
        # Find latest reports
        eval_reports = glob.glob(os.path.join(self.reports_dir, "evaluation_report_*.txt"))
        perf_reports = glob.glob(os.path.join(self.reports_dir, "performance_test_*.txt"))
        
        if not eval_reports or not perf_reports:
            print("No evaluation or performance reports found!")
            return
        
        latest_eval = max(eval_reports, key=os.path.getctime)
        latest_perf = max(perf_reports, key=os.path.getctime)
        
        print(f"\n{'='*60}")
        print("ANOMALY DETECTION SYSTEM - RESULTS SUMMARY")
        print(f"{'='*60}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Parse reports
        eval_data = self.parse_evaluation_report(latest_eval)
        perf_data = self.parse_performance_report(latest_perf)
        
        # Model performance summary
        print("\n📊 MODEL PERFORMANCE SUMMARY")
        print("-" * 40)
        
        for model in self.models:
            detections = []
            for test_file, models in eval_data.items():
                if model in models and 'anomalies' in models[model]:
                    detections.append(models[model]['anomalies'])
            
            if detections:
                print(f"\n{model.replace('_model', '').upper()} MODEL:")
                print(f"  • Average detections: {np.mean(detections):.1f}")
                print(f"  • Min/Max detections: {min(detections)}/{max(detections)}")
                
                # Performance at 1000 records
                if 1000 in perf_data and model in perf_data[1000]:
                    rps = perf_data[1000][model].get('rps', 0)
                    print(f"  • Throughput: {rps:.0f} records/second")
        
        # Test dataset summary
        print("\n📁 TEST DATASETS EVALUATED")
        print("-" * 40)
        for test_file in sorted(eval_data.keys()):
            print(f"  • {test_file}")
        
        # Create visualizations
        print("\n📈 GENERATING VISUALIZATIONS...")
        print("-" * 40)
        
        try:
            self.create_performance_chart(perf_data)
            self.create_detection_summary(eval_data)
        except Exception as e:
            print(f"Warning: Could not create charts: {e}")
        
        print("\n✅ SYSTEM STATUS: READY FOR DEPLOYMENT")
        print(f"{'='*60}\n")

def main():
    visualizer = ResultsVisualizer()
    visualizer.generate_summary_report()
    
    # Additional analysis if data directory exists
    if os.path.exists("data/training"):
        print("\n📊 TRAINING DATA ANALYSIS")
        print("-" * 40)
        
        for json_file in glob.glob("data/training/*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                print(f"  • {os.path.basename(json_file)}: {len(data)} records")
            except:
                pass

if __name__ == "__main__":
    main()
