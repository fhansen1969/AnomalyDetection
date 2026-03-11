import json
from datetime import datetime, timedelta
import random

# Scenario 1: Coordinated DDoS attack
ddos_records = []
attack_time = datetime.now()
attack_sources = [f"203.0.113.{i}" for i in range(50, 60)]
target_server = "web-server-01"

for i, source in enumerate(attack_sources):
    for j in range(5):  # 5 records per source
        record = {
            "timestamp": (attack_time + timedelta(seconds=i*2+j)).isoformat(),
            "src_ip": source,
            "dst_ip": "192.168.1.10",
            "location": target_server,
            "metadata": {
                "alert_type": "DDoS_suspected",
                "correlation_group": "ddos_attack_1"
            },
            "features": {
                "bytes_in": random.randint(5000000, 10000000),
                "connection_count": random.randint(500, 2000),
                "error_rate": round(random.uniform(0.5, 0.9), 3)
            }
        }
        ddos_records.append(record)

# Scenario 2: Lateral movement
lateral_records = []
compromised_host = "192.168.1.50"
movement_time = datetime.now() - timedelta(hours=2)
target_hosts = ["192.168.1.51", "192.168.1.52", "192.168.1.53", "192.168.1.54"]

for i, target in enumerate(target_hosts):
    record = {
        "timestamp": (movement_time + timedelta(minutes=i*15)).isoformat(),
        "src_ip": compromised_host,
        "dst_ip": target,
        "metadata": {
            "alert_type": "brute_force_attack",
            "correlation_group": "lateral_movement_1"
        },
        "features": {
            "failed_logins": random.randint(100, 500),
            "connection_count": random.randint(20, 50)
        }
    }
    lateral_records.append(record)

# Scenario 3: Data exfiltration chain
exfil_records = []
exfil_time = datetime.now() - timedelta(hours=1)
exfil_stages = [
    {"type": "sql_injection_attempt", "target": "database-server-01"},
    {"type": "privilege_escalation", "target": "database-server-01"},
    {"type": "data_exfiltration_suspected", "target": "database-server-01"}
]

for i, stage in enumerate(exfil_stages):
    record = {
        "timestamp": (exfil_time + timedelta(minutes=i*10)).isoformat(),
        "src_ip": "185.45.67.100",
        "location": stage["target"],
        "metadata": {
            "alert_type": stage["type"],
            "correlation_group": "exfiltration_chain_1"
        }
    }
    exfil_records.append(record)

# Combine all scenarios
all_scenarios = ddos_records + lateral_records + exfil_records

# Add some noise (unrelated records)
for i in range(20):
    noise_record = {
        "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat(),
        "src_ip": f"10.0.0.{random.randint(1, 254)}",
        "dst_ip": f"192.168.1.{random.randint(1, 254)}",
        "metadata": {
            "alert_type": "normal_traffic"
        }
    }
    all_scenarios.append(noise_record)

# Save correlation test data
with open("correlation_test_scenarios.json", "w") as f:
    json.dump(all_scenarios, f, indent=2)

print(f"Generated {len(all_scenarios)} correlation test records")
print(f"  - DDoS attack: {len(ddos_records)} records")
print(f"  - Lateral movement: {len(lateral_records)} records")
print(f"  - Exfiltration chain: {len(exfil_records)} records")
