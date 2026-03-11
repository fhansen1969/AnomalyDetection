# generate_sw_training_data.py
import json
import random
from datetime import datetime, timedelta
import uuid

def generate_sw_training_data(num_records=200):
    """Generate SolarWinds alert training data."""
    
    # Alert templates
    alert_types = [
        {
            "Name": "SSI - Application consuming Host Memory",
            "Description": "Triggers when a Node reaches more than 95% Memory and sends an email with the highest Memory process.",
            "ObjectType": "Node",
            "MessageTemplate": "Node: {node}\r\nMemory Usage (Node): {memory} %\r\n\r\nProcess Name: {process}\r\nPeak Memory Usage (Process): {process_memory}%"
        },
        {
            "Name": "Service Fabric Cluster",
            "Description": "Memory usage > 80%\r\nCPU = 100% for > than 5 minutes\r\nDisk space >75% of total available space used.",
            "ObjectType": "Volume",
            "MessageTemplate": "Memory usage > 80%\r\nCPU = 100% for > than 5 minutes\r\nDisk space 75% of total available space used."
        },
        {
            "Name": "SSI - Fluent Bit Service Alert",
            "Description": "Alerts when the Fluent Bit service is not up.",
            "ObjectType": "APM: Application",
            "MessageTemplate": "SSI - Fluent Bit - Windows Monitor on {node} has a status of {status}."
        },
        {
            "Name": "Disk - PRODUCTION DISK < 10%",
            "Description": "This alert is triggered when the disk space is <10%\r\nFile Share Servers\r\nSSIAPP Web Servers\r\nAll App Job and Validation Servers\r\n2024.07.05",
            "ObjectType": "Volume",
            "MessageTemplate": "PRODUCTION DISK < 10GB"
        },
        {
            "Name": "PRODUCTION SQL CPU > 85%",
            "Description": "",
            "ObjectType": "Node",
            "MessageTemplate": "PRODUCTION SQL CPU > 85%"
        },
        {
            "Name": "High Subnet Usage Monitoring",
            "Description": "This alert will write to IPAM event log when a subnets usage surpasses 75%",
            "ObjectType": "IPAM Networks",
            "MessageTemplate": "High Subnet Usage Monitoring"
        },
        {
            "Name": "Service - Qlik Sense Repository Database - UP/DOWN",
            "Description": "This alert will write to the event log when an application goes down and when an application comes back up.",
            "ObjectType": "APM: Application",
            "MessageTemplate": "Service - Qlik Sense Repository Database - UP/DOWN"
        }
    ]
    
    # Node names
    nodes = [
        "DBADEVSQLCVM.SSIAPP.CORP", "SFPRODNODE37VM.SSIAPP.CORP", "HCAITSDKRVM001.SSIAPP.CORP",
        "RMTKWEBVM001.SSIAPP.CORP", "HCAITSDKRVM002.SSIAPP.CORP", "HCASQLAVM.SSIAPP.CORP",
        "CDMSWEBCVMF5.SSIAPP.CORP", "CDMSWEBDVMF5.SSIAPP.CORP", "FZBLGWEBBVM.SSIFZ.COM",
        "HCASFNODE09VM.SSIAPP.CORP", "SFPRODNODE50VM.SSIAPP.CORP", "HCASFNODE06VM.SSIAPP.CORP",
        "HCASFNODE03VM.SSIAPP.CORP", "HCASFNODE13VM.SSIAPP.CORP", "SFPRODNODE23VM.SSIAPP.CORP",
        "SFPRODNODE30VM.SSIAPP.CORP", "EFTSQLAVM.SSIAPP.CORP", "QLIKPRODAVM.SSIAPP.CORP",
        "EDWSHARDCVM.SSIAPP.CORP", "MOB1M5SQLC1B4.SSIAPP.CORP", "HCASFNODE11VM.SSIAPP.CORP"
    ]
    
    # Volume labels
    volumes = ["C:\\ Label: C2CE3AE6", "C:\\ Label: F87772B4", "C:\\ Label: 60EA4F93", 
               "D:\\ Label:APPDATA C4161509", "E:\\ Label: DATA", "F:\\ Label: BACKUP"]
    
    # Statuses
    statuses = ["Critical", "Unreachable", "Warning", "OK", "Unknown"]
    
    # Process names
    processes = ["sqlservr.exe", "w3wp.exe", "chrome.exe", "java.exe", "python.exe", 
                 "node.exe", "vmware-hostd.exe", "System", "svchost.exe"]
    
    records = []
    base_time = datetime.now() - timedelta(days=30)
    
    for i in range(num_records):
        # Select alert type
        alert_template = random.choice(alert_types)
        
        # Base severity distribution (0-3 are normal, 4-9 are higher severity)
        if random.random() < 0.7:  # 70% normal
            severity = random.choice([0, 1, 2])
        else:  # 30% higher severity
            severity = random.randint(3, 9)
        
        # Triggered count based on severity
        if severity >= 7:
            triggered_count = random.randint(100, 1000)
        elif severity >= 4:
            triggered_count = random.randint(20, 100)
        else:
            triggered_count = random.randint(1, 20)
        
        # Generate triggered message based on template
        node = random.choice(nodes)
        triggered_message = alert_template["MessageTemplate"]
        
        if "{node}" in triggered_message:
            triggered_message = triggered_message.replace("{node}", node)
        if "{memory}" in triggered_message:
            triggered_message = triggered_message.replace("{memory}", str(random.randint(85, 100)))
        if "{process}" in triggered_message:
            triggered_message = triggered_message.replace("{process}", random.choice(processes))
        if "{process_memory}" in triggered_message:
            triggered_message = triggered_message.replace("{process_memory}", str(random.randint(1, 99)))
        if "{status}" in triggered_message:
            triggered_message = triggered_message.replace("{status}", random.choice(statuses))
        
        # Acknowledgment (30% chance)
        if random.random() < 0.3:
            ack_by = random.choice(["SSI\\coopedadm", "DirectLink", "SSI\\admin", "SSI\\monitor"])
            ack_date = (base_time + timedelta(days=random.randint(1, 29), 
                                            hours=random.randint(0, 23),
                                            minutes=random.randint(0, 59))).isoformat() + "Z"
        else:
            ack_by = None
            ack_date = None
        
        # Entity caption
        if alert_template["ObjectType"] == "Volume":
            entity_caption = random.choice(volumes)
        elif alert_template["ObjectType"] == "APM: Application":
            entity_caption = alert_template["Name"].replace("SSI - ", "").replace(" Alert", "")
        else:
            entity_caption = node
        
        record = {
            "Name": alert_template["Name"],
            "Description": alert_template["Description"],
            "Severity": severity,
            "ObjectType": alert_template["ObjectType"],
            "EntityCaption": entity_caption,
            "RelatedNodeCaption": node if alert_template["ObjectType"] != "IPAM Networks" else None,
            "TriggeredMessage": triggered_message,
            "TriggeredDateTime": (base_time + timedelta(
                days=random.randint(0, 29),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59)
            )).isoformat() + "Z",
            "TriggeredCount": triggered_count,
            "AcknowledgedBy": ack_by,
            "AcknowledgedDateTime": ack_date,
            "AcknowledgedNote": None,
            "AlertNote": None,
            "timestamp": datetime.now().isoformat(),
            "normalized": True,
            "normalized_timestamp": datetime.now().isoformat(),
            "extracted_features": {
                "feature_Severity": severity,
                "feature_TriggeredCount": triggered_count,
                "feature_normalized": True
            }
        }
        
        records.append(record)
    
    return records

# Generate and save
if __name__ == "__main__":
    sw_data = generate_sw_training_data(200)
    
    with open("sw_training_200.json", "w") as f:
        json.dump(sw_data, f, indent=2)
    
    print(f"Generated {len(sw_data)} SolarWinds alert records")
    
    # Show statistics
    severities = {}
    for record in sw_data:
        sev = record["Severity"]
        severities[sev] = severities.get(sev, 0) + 1
    
    print("\nSeverity distribution:")
    for sev in sorted(severities.keys()):
        print(f"  Severity {sev}: {severities[sev]} records")
