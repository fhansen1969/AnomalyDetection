# generate_network_training_data.py
import json
import random
from datetime import datetime, timedelta
import numpy as np

def generate_network_training_data(num_records=200):
    """Generate network traffic anomaly training data."""
    
    # Server types and locations
    locations = [
        "web-server-01", "web-server-02", "web-server-03",
        "database-server-01", "database-server-02", "database-server-03",
        "login-server-01", "login-server-02", "login-server-03",
        "api-gateway-01", "api-gateway-02", "api-gateway-03",
        "file-server-01", "file-server-02", "file-server-03",
        "mail-server-01", "app-server-01", "app-server-02",
        "cache-server-01", "proxy-server-01", "backup-server-01"
    ]
    
    # IP ranges
    internal_ips = ["192.168.1.", "10.0.0.", "172.16.0.", "10.10.0."]
    external_ips = ["203.0.113.", "198.51.100.", "185.45.67.", "134.22.89.", "89.123.45."]
    
    # Alert types
    alert_types = [
        "normal_traffic",
        "DDoS_suspected",
        "data_exfiltration_suspected",
        "brute_force_attack",
        "sql_injection_attempt",
        "port_scan_detected",
        "malware_communication",
        "unusual_protocol",
        "bandwidth_spike",
        "connection_flood"
    ]
    
    # Metadata templates
    metadata_templates = {
        "DDoS_suspected": {"protocol": "HTTP", "port": 80},
        "data_exfiltration_suspected": {"query_type": "SELECT_ALL", "database": "customer_records"},
        "brute_force_attack": {"target_user": "admin", "auth_method": "password"},
        "sql_injection_attempt": {"payload": "'; DROP TABLE users; --", "endpoint": "/api/v1/search"},
        "port_scan_detected": {"scan_type": "SYN", "ports_scanned": 65535},
        "malware_communication": {"malware_family": "TrickBot", "c2_server": "malicious.com"},
        "unusual_protocol": {"protocol": "ICMP", "packet_size": 65000},
        "bandwidth_spike": {"normal_bandwidth": 1000000, "spike_bandwidth": 50000000},
        "connection_flood": {"connections_per_second": 10000, "source_country": "Unknown"}
    }
    
    records = []
    base_time = datetime.now() - timedelta(hours=24)
    
    for i in range(num_records):
        # 70% normal traffic, 30% anomalous
        is_anomaly = random.random() < 0.3
        
        if is_anomaly:
            alert_type = random.choice([at for at in alert_types if at != "normal_traffic"])
        else:
            alert_type = "normal_traffic"
        
        # Generate IPs
        if random.random() < 0.7:  # 70% internal source
            src_ip = random.choice(internal_ips) + str(random.randint(1, 254))
            dst_ip = random.choice(internal_ips) + str(random.randint(1, 254))
        else:  # 30% external source
            src_ip = random.choice(external_ips) + str(random.randint(1, 254))
            dst_ip = random.choice(internal_ips) + str(random.randint(1, 254))
        
        # Generate features based on alert type
        if alert_type == "normal_traffic":
            features = {
                "bytes_in": random.randint(1000, 50000),
                "bytes_out": random.randint(1000, 50000),
                "packet_count": random.randint(10, 500),
                "connection_count": random.randint(1, 20),
                "error_rate": round(random.uniform(0, 0.05), 3),
                "cpu_usage": round(random.uniform(10, 60), 1),
                "memory_usage": round(random.uniform(20, 70), 1),
                "response_time": random.randint(10, 500),
                "failed_logins": 0,
                "unique_ips": random.randint(1, 10)
            }
        elif alert_type == "DDoS_suspected":
            features = {
                "bytes_in": random.randint(5000000, 10000000),
                "bytes_out": random.randint(100, 1000),
                "packet_count": random.randint(5000, 20000),
                "connection_count": random.randint(500, 2000),
                "error_rate": round(random.uniform(0.3, 0.8), 3),
                "cpu_usage": round(random.uniform(85, 100), 1),
                "memory_usage": round(random.uniform(80, 100), 1),
                "response_time": random.randint(3000, 10000),
                "failed_logins": random.randint(0, 100),
                "unique_ips": random.randint(50, 500)
            }
        elif alert_type == "data_exfiltration_suspected":
            features = {
                "bytes_in": random.randint(500, 5000),
                "bytes_out": random.randint(10000000, 50000000),
                "packet_count": random.randint(1000, 5000),
                "connection_count": random.randint(1, 5),
                "error_rate": round(random.uniform(0, 0.05), 3),
                "cpu_usage": round(random.uniform(70, 90), 1),
                "memory_usage": round(random.uniform(60, 85), 1),
                "response_time": random.randint(1000, 5000),
                "failed_logins": 0,
                "unique_ips": random.randint(1, 3)
            }
        elif alert_type == "brute_force_attack":
            features = {
                "bytes_in": random.randint(1000, 5000),
                "bytes_out": random.randint(500, 2000),
                "packet_count": random.randint(20, 100),
                "connection_count": random.randint(20, 50),
                "error_rate": round(random.uniform(0.7, 0.95), 3),
                "cpu_usage": round(random.uniform(30, 60), 1),
                "memory_usage": round(random.uniform(40, 70), 1),
                "response_time": random.randint(50, 300),
                "failed_logins": random.randint(100, 1000),
                "unique_ips": random.randint(1, 5)
            }
        elif alert_type == "sql_injection_attempt":
            features = {
                "bytes_in": random.randint(2000, 10000),
                "bytes_out": random.randint(500, 2000),
                "packet_count": random.randint(10, 50),
                "connection_count": random.randint(5, 15),
                "error_rate": round(random.uniform(0.5, 0.9), 3),
                "cpu_usage": round(random.uniform(40, 70), 1),
                "memory_usage": round(random.uniform(50, 75), 1),
                "response_time": random.randint(2000, 5000),
                "failed_logins": 0,
                "unique_ips": random.randint(1, 5)
            }
        elif alert_type == "port_scan_detected":
            features = {
                "bytes_in": random.randint(500, 2000),
                "bytes_out": random.randint(200, 1000),
                "packet_count": random.randint(5, 20),
                "connection_count": random.randint(100, 300),
                "error_rate": round(random.uniform(0.02, 0.1), 3),
                "cpu_usage": round(random.uniform(60, 80), 1),
                "memory_usage": round(random.uniform(55, 75), 1),
                "response_time": random.randint(200, 800),
                "failed_logins": 0,
                "unique_ips": 1
            }
        else:  # Other anomaly types
            features = {
                "bytes_in": random.randint(1000, 1000000),
                "bytes_out": random.randint(1000, 1000000),
                "packet_count": random.randint(50, 5000),
                "connection_count": random.randint(10, 200),
                "error_rate": round(random.uniform(0.1, 0.7), 3),
                "cpu_usage": round(random.uniform(50, 95), 1),
                "memory_usage": round(random.uniform(45, 90), 1),
                "response_time": random.randint(500, 4000),
                "failed_logins": random.randint(0, 50),
                "unique_ips": random.randint(1, 50)
            }
        
        # Build metadata
        metadata = {"alert_type": alert_type}
        if alert_type in metadata_templates:
            metadata.update(metadata_templates[alert_type])
        
        # Create record
        record = {
            "timestamp": (base_time + timedelta(
                minutes=i * 5,  # 5-minute intervals
                seconds=random.randint(0, 59)
            )).isoformat(),
            "source": "network_monitor",
            "location": random.choice(locations),
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "features": features,
            "metadata": metadata,
            "normalized": True,
            "normalized_timestamp": datetime.now().isoformat(),
            "extracted_features": {
                "feature_normalized": True
            }
        }
        
        records.append(record)
    
    return records

# Generate and save
if __name__ == "__main__":
    network_data = generate_network_training_data(200)
    
    with open("network_training_200.json", "w") as f:
        json.dump(network_data, f, indent=2)
    
    print(f"Generated {len(network_data)} network traffic records")
    
    # Show statistics
    alert_counts = {}
    for record in network_data:
        alert = record["metadata"]["alert_type"]
        alert_counts[alert] = alert_counts.get(alert, 0) + 1
    
    print("\nAlert type distribution:")
    for alert in sorted(alert_counts.keys()):
        print(f"  {alert}: {alert_counts[alert]} records")
