#!/usr/bin/env python3
"""
Generate realistic test data matching the training data schemas.

The training data contains two record types:
  - SentinelOne endpoint telemetry (86 fields, ~2.4% of records)
  - Solarwinds monitoring data (7 fields, ~97.6% of records)

Produces:
  - data/test/test_data.json: 1000 records (80% normal, 20% anomalous)
  - data/validation/validation_data.json: held-out validation split from training data
"""

import json
import copy
import random
import uuid
import os
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAINING_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "training", "training_data.json")
TEST_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "test", "test_data.json")
VALIDATION_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "validation", "validation_data.json")

# Solarwinds status values
SW_STATUS_NORMAL = [1, 2]  # Up / Warning
SW_STATUS_ANOMALOUS = [3, 4, 9, 10, 12]  # Down, Shutdown, Unmanaged, etc.


def load_training_records():
    """Load all raw_data records from training batches, separated by type."""
    with open(TRAINING_DATA_PATH, "r") as f:
        data = json.load(f)

    sentinel = []
    solarwinds = []
    for batch in data:
        for rec in batch.get("raw_data", []):
            if len(rec.keys()) > 50 and "computerName" in rec:
                sentinel.append(rec)
            else:
                solarwinds.append(rec)
    return sentinel, solarwinds


def random_ts(base: str = None, offset_hours: int = 0, jitter_hours: int = 48) -> str:
    """Generate a random timestamp near a base timestamp string."""
    if base:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(base, fmt)
                break
            except ValueError:
                continue
        else:
            dt = datetime.utcnow()
    else:
        dt = datetime.utcnow()

    delta = timedelta(hours=offset_hours + random.randint(-jitter_hours, jitter_hours))
    return (dt + delta).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def random_ip():
    return f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def random_external_ip():
    return f"64.6.{random.randint(40,50)}.{random.randint(1,254)}"


# ---------------------------------------------------------------------------
# SentinelOne record generators
# ---------------------------------------------------------------------------

def make_normal_sentinel(template: dict) -> dict:
    """Normal SentinelOne endpoint record."""
    rec = copy.deepcopy(template)
    rec["id"] = str(random.randint(10**18, 10**19))
    rec["uuid"] = uuid.uuid4().hex

    if rec.get("totalMemory"):
        rec["totalMemory"] = max(1024, rec["totalMemory"] + int(rec["totalMemory"] * random.uniform(-0.1, 0.1)))

    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rec["lastActiveDate"] = random_ts(now_str, offset_hours=-random.randint(0, 6))
    rec["updatedAt"] = random_ts(now_str, offset_hours=-random.randint(0, 12))
    if rec.get("osStartTime"):
        rec["osStartTime"] = random_ts(now_str, offset_hours=-random.randint(24, 720))

    rec["activeThreats"] = 0
    rec["infected"] = False
    rec["isActive"] = True
    rec["isDecommissioned"] = False
    rec["isPendingUninstall"] = False
    rec["isUninstalled"] = False
    rec["networkStatus"] = "connected"
    rec["threatRebootRequired"] = False
    rec["detectionState"] = "full_mode"
    rec["lastIpToMgmt"] = random_ip()
    rec["externalIp"] = random_external_ip()
    return rec


def make_anomalous_sentinel(template: dict) -> dict:
    """Anomalous SentinelOne endpoint record."""
    rec = copy.deepcopy(template)
    rec["id"] = str(random.randint(10**18, 10**19))
    rec["uuid"] = uuid.uuid4().hex

    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rec["updatedAt"] = random_ts(now_str, offset_hours=-random.randint(0, 12))

    anomaly_types = random.sample([
        "active_threats", "infected", "decommissioned", "disconnected",
        "stale_agent", "unusual_resources", "pending_uninstall",
        "slim_mode", "scan_stale", "inactive",
    ], k=random.randint(2, 4))

    for atype in anomaly_types:
        if atype == "active_threats":
            rec["activeThreats"] = random.randint(1, 15)
            rec["threatRebootRequired"] = True
        elif atype == "infected":
            rec["infected"] = True
            rec["activeThreats"] = max(rec.get("activeThreats", 0), 1)
        elif atype == "decommissioned":
            rec["isDecommissioned"] = True
            rec["isActive"] = False
        elif atype == "disconnected":
            rec["networkStatus"] = "disconnected"
            rec["lastActiveDate"] = random_ts(now_str, offset_hours=-random.randint(720, 4380))
        elif atype == "stale_agent":
            rec["isUpToDate"] = False
            rec["agentVersion"] = "22.1.0.100"
            rec["appsVulnerabilityStatus"] = "patch_required"
        elif atype == "unusual_resources":
            rec["totalMemory"] = random.choice([256, 512, 262144, 524288])
            rec["cpuCount"] = random.choice([1, 64, 128])
            rec["coreCount"] = random.choice([1, 256])
        elif atype == "pending_uninstall":
            rec["isPendingUninstall"] = True
        elif atype == "slim_mode":
            rec["detectionState"] = "slim_mode"
        elif atype == "scan_stale":
            stale = datetime.utcnow() - timedelta(days=random.randint(365, 730))
            rec["lastSuccessfulScanDate"] = stale.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            rec["scanStatus"] = "aborted"
        elif atype == "inactive":
            rec["isActive"] = False
            rec["lastActiveDate"] = random_ts(now_str, offset_hours=-random.randint(2160, 8760))

    rec["lastIpToMgmt"] = random_ip()
    rec["externalIp"] = random_external_ip()
    return rec


# ---------------------------------------------------------------------------
# Solarwinds record generators
# ---------------------------------------------------------------------------

def make_normal_solarwinds(template: dict) -> dict:
    """Normal Solarwinds monitoring record."""
    rec = copy.deepcopy(template)
    rec["NodeID"] = random.randint(1000, 99999)
    rec["Status"] = random.choice(SW_STATUS_NORMAL)
    if rec.get("IPAddress"):
        rec["IPAddress"] = random_ip()
    if rec.get("LastBoot"):
        rec["LastBoot"] = random_ts(offset_hours=-random.randint(24, 2160))
    return rec


def make_anomalous_solarwinds(template: dict) -> dict:
    """Anomalous Solarwinds monitoring record."""
    rec = copy.deepcopy(template)
    rec["NodeID"] = random.randint(1000, 99999)

    anomaly_types = random.sample([
        "status_down", "stale_boot", "unusual_ip",
    ], k=random.randint(1, 2))

    for atype in anomaly_types:
        if atype == "status_down":
            rec["Status"] = random.choice(SW_STATUS_ANOMALOUS)
        elif atype == "stale_boot":
            rec["LastBoot"] = random_ts(offset_hours=-random.randint(8760, 17520))
        elif atype == "unusual_ip":
            # External IP in a monitoring record is suspicious
            rec["IPAddress"] = f"{random.randint(100,200)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

    return rec


# ---------------------------------------------------------------------------
# Main generators
# ---------------------------------------------------------------------------

def generate_test_data(sentinel_recs, solarwinds_recs, count=1000, anomaly_ratio=0.2):
    """Generate test data matching training data distribution."""
    anomaly_count = int(count * anomaly_ratio)
    normal_count = count - anomaly_count

    # Maintain approximate training distribution: ~97% solarwinds, ~3% sentinel
    # But bump sentinel to 10% for richer testing
    sentinel_count = max(50, int(count * 0.10))
    solarwinds_count = count - sentinel_count

    sentinel_anomaly = int(sentinel_count * anomaly_ratio)
    sentinel_normal = sentinel_count - sentinel_anomaly
    sw_anomaly = int(solarwinds_count * anomaly_ratio)
    sw_normal = solarwinds_count - sw_anomaly

    test_records = []

    # SentinelOne records
    for _ in range(sentinel_normal):
        test_records.append(make_normal_sentinel(random.choice(sentinel_recs)))
    for _ in range(sentinel_anomaly):
        test_records.append(make_anomalous_sentinel(random.choice(sentinel_recs)))

    # Solarwinds records
    for _ in range(sw_normal):
        test_records.append(make_normal_solarwinds(random.choice(solarwinds_recs)))
    for _ in range(sw_anomaly):
        test_records.append(make_anomalous_solarwinds(random.choice(solarwinds_recs)))

    random.shuffle(test_records)
    print(f"  SentinelOne: {sentinel_normal} normal + {sentinel_anomaly} anomalous")
    print(f"  Solarwinds:  {sw_normal} normal + {sw_anomaly} anomalous")
    return test_records


def generate_validation_split(sentinel_recs, solarwinds_recs, ratio=0.15):
    """Create a validation split. Device-level holdout for SentinelOne, random sample for Solarwinds."""
    # SentinelOne: hold out by device
    by_device = {}
    for rec in sentinel_recs:
        name = rec.get("computerName", "unknown")
        by_device.setdefault(name, []).append(rec)

    devices = list(by_device.keys())
    random.shuffle(devices)
    val_device_count = max(1, int(len(devices) * ratio))
    val_devices = set(devices[:val_device_count])

    val_records = []
    for device in val_devices:
        val_records.extend(by_device[device])

    # Solarwinds: random sample
    sw_sample_size = max(20, int(len(solarwinds_recs) * ratio * 0.01))  # Small sample
    val_records.extend(random.sample(solarwinds_recs, min(sw_sample_size, len(solarwinds_recs))))

    # Inject some anomalous records
    anomaly_count = max(10, int(len(val_records) * 0.15))
    sentinel_anom = anomaly_count // 2
    sw_anom = anomaly_count - sentinel_anom

    for _ in range(sentinel_anom):
        template = random.choice(sentinel_recs)
        val_records.append(make_anomalous_sentinel(template))
    for _ in range(sw_anom):
        template = random.choice(solarwinds_recs)
        val_records.append(make_anomalous_solarwinds(template))

    random.shuffle(val_records)
    print(f"  {len(val_devices)} SentinelOne devices held out + {sw_sample_size} Solarwinds samples")
    print(f"  {anomaly_count} synthetic anomalies injected")
    print(f"  Total: {len(val_records)} records")
    return val_records


def main():
    random.seed(42)

    print("Loading training data...")
    sentinel_recs, solarwinds_recs = load_training_records()
    print(f"  SentinelOne records: {len(sentinel_recs)}")
    print(f"  Solarwinds records:  {len(solarwinds_recs)}")

    # --- Generate test data ---
    print("\nGenerating test data (1000 records, 20% anomalous)...")
    test_data = generate_test_data(sentinel_recs, solarwinds_recs, count=1000, anomaly_ratio=0.2)
    os.makedirs(os.path.dirname(TEST_DATA_PATH), exist_ok=True)
    with open(TEST_DATA_PATH, "w") as f:
        json.dump(test_data, f, indent=2)
    print(f"Wrote {len(test_data)} test records to {TEST_DATA_PATH}")

    # --- Generate validation data ---
    print("\nGenerating validation split...")
    val_data = generate_validation_split(sentinel_recs, solarwinds_recs, ratio=0.15)
    os.makedirs(os.path.dirname(VALIDATION_DATA_PATH), exist_ok=True)
    with open(VALIDATION_DATA_PATH, "w") as f:
        json.dump(val_data, f, indent=2)
    print(f"Wrote {len(val_data)} validation records to {VALIDATION_DATA_PATH}")

    print("\nDone!")


if __name__ == "__main__":
    main()
