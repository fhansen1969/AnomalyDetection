#!/usr/bin/env python3
"""Monitor anomaly detection system performance"""

import time
import json
import subprocess
from datetime import datetime

def get_system_status():
    """Get current system status"""
    try:
        result = subprocess.run(['python', 'api_client.py', 'system-status'], 
                              capture_output=True, text=True)
        return json.loads(result.stdout)
    except:
        return None

def get_detection_stats():
    """Get recent detection statistics"""
    try:
        result = subprocess.run(['python', 'api_client.py', 'list-anomalies', '--limit', '100'], 
                              capture_output=True, text=True)
        anomalies = json.loads(result.stdout)
        
        # Calculate stats
        total = len(anomalies)
        by_model = {}
        by_type = {}
        
        for anomaly in anomalies:
            model = anomaly.get('model', 'unknown')
            by_model[model] = by_model.get(model, 0) + 1
            
            # For network data
            if 'metadata' in anomaly:
                alert_type = anomaly['metadata'].get('alert_type', 'unknown')
                by_type[alert_type] = by_type.get(alert_type, 0) + 1
        
        return {
            'total': total,
            'by_model': by_model,
            'by_type': by_type
        }
    except:
        return None

def monitor_loop():
    """Main monitoring loop"""
    print("Starting system monitoring...")
    print("Press Ctrl+C to stop\n")
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
            
            # Get system status
            status = get_system_status()
            if status:
                print(f"System Status: {status.get('status', 'unknown')}")
                print(f"Active Models: {status.get('models', {}).get('active', 0)}")
            
            # Get detection stats
            stats = get_detection_stats()
            if stats:
                print(f"\nRecent Detections: {stats['total']}")
                
                if stats['by_model']:
                    print("\nBy Model:")
                    for model, count in stats['by_model'].items():
                        print(f"  - {model}: {count}")
                
                if stats['by_type']:
                    print("\nBy Type:")
                    for atype, count in sorted(stats['by_type'].items(), 
                                              key=lambda x: x[1], reverse=True)[:5]:
                        print(f"  - {atype}: {count}")
            
            # Wait before next check
            time.sleep(60)  # Check every minute
            
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    monitor_loop()
