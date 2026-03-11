"""
Unified LangGraph-based agent manager for the anomaly detection system.

This module provides functionality to analyze anomalies using a multi-agent
system with enhanced communication, detailed analysis, and inter-agent dialogue.
Supports both basic and enhanced agent workflows for anomaly detection.
"""

import logging
import os
import json
import time
import datetime
import traceback
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from pydantic import BaseModel, Field
import re
from collections import defaultdict

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("Ollama client not installed. LLM integration will not work.")

try:
    from langgraph.graph import StateGraph, END, START
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logging.warning("LangGraph not installed. Agent framework will not work.")


class EnhancedAgentState(BaseModel):
    """Enhanced state for the agent graph with richer context."""
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    analysis: Optional[Dict[str, Any]] = None
    remediation: Optional[Dict[str, Any]] = None
    reflection: Optional[Dict[str, Any]] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    current_anomaly_index: int = 0
    errors: List[str] = Field(default_factory=list)
    should_continue: bool = True
    additional_data: Dict[str, Any] = Field(default_factory=dict)
    next_step: Optional[str] = None
    active_agent: Optional[str] = None
    
    # Enhanced fields for rich interactions
    agent_dialogue: List[Dict[str, Any]] = Field(default_factory=list)
    context_memory: Dict[str, Any] = Field(default_factory=dict)
    collaboration_requests: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    consensus_needed: List[str] = Field(default_factory=list)
    evidence_chain: List[Dict[str, Any]] = Field(default_factory=list)
    action_items: List[Dict[str, Any]] = Field(default_factory=list)
    threat_indicators: Dict[str, Any] = Field(default_factory=dict)
    
    # Knowledge sharing between agents
    shared_knowledge: Dict[str, Any] = Field(default_factory=dict)
    agent_insights: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)


# Legacy state model for backwards compatibility
class AgentState(EnhancedAgentState):
    """
    Legacy state model that inherits from EnhancedAgentState for backward compatibility.
    This ensures old code using AgentState continues to work.
    """
    pass


class EnhancedAgentPrompts:
    """Enhanced prompts that encourage more detailed, structured responses."""
    
    SECURITY_ANALYST_ENHANCED = """
You are a senior security analyst with 15+ years of experience. Your analysis must be EXTREMELY detailed and comprehensive.

For the provided anomaly, deliver a THOROUGH analysis with the following structure:

## 1. INITIAL ASSESSMENT (Detailed)
- **Anomaly Classification**: Specify exact type (e.g., Authentication Anomaly, Network Traffic Spike, Data Exfiltration Pattern)
- **Attack Vector Analysis**: Identify all possible attack vectors
- **Threat Actor Profile**: Potential threat actor characteristics and motivations
- **Kill Chain Mapping**: Map to Cyber Kill Chain phases

## 2. TECHNICAL DEEP DIVE
- **Indicator Analysis**:
  - List ALL IP addresses, domains, ports, protocols
  - Identify patterns in timing, frequency, volume
  - Extract any payloads, commands, or scripts
  - Note user agents, referrers, or other metadata
- **Behavioral Analysis**:
  - Normal vs anomalous behavior comparison
  - Statistical deviations (specify percentages)
  - Time-series patterns and correlations
- **System Impact**:
  - Affected systems and services
  - Performance degradation metrics
  - Data exposure risk assessment

## 3. THREAT INTELLIGENCE CORRELATION
- **Known Threats**: Match against known attack patterns
- **MITRE ATT&CK Mapping**: List specific techniques (T####)
- **Historical Context**: Similar incidents in past 90 days
- **Industry Trends**: Current threat landscape relevance

## 4. SEVERITY ASSESSMENT
Rate severity as: Critical / High / Medium / Low

Justify with:
- Business impact score (1-10): ___
- Technical severity score (1-10): ___
- Data sensitivity score (1-10): ___
- Spread potential score (1-10): ___
- Overall risk score: ___

## 5. CONFIDENCE ANALYSIS
- **Overall Confidence**: ___% 
- **Evidence Quality**: Strong / Moderate / Weak
- **False Positive Likelihood**: ___% with justification
- **Additional Data Needed**: List specific logs/data that would increase confidence

## 6. IMMEDIATE RECOMMENDATIONS
- **Containment Actions** (Do within 5 minutes):
  1. [Specific action with exact command/procedure]
  2. [Specific action with exact command/procedure]
- **Investigation Priorities**:
  1. [What to check first and why]
  2. [Secondary investigation paths]

## 7. QUESTIONS FOR OTHER TEAMS
- **For Threat Intelligence**: [Specific questions about indicators]
- **For Incident Response**: [Questions about containment options]
- **For Data Collection**: [What additional data is needed]

## 8. EVIDENCE CHAIN
Document the logical flow from detection to conclusion:
Detection → [Evidence 1] → [Inference 1] → [Evidence 2] → [Conclusion]

Remember: Be SPECIFIC, use EXACT values from the data, and JUSTIFY every conclusion with evidence.
"""

    REMEDIATION_EXPERT_ENHANCED = """
You are an incident response team lead. Provide an EXHAUSTIVE remediation plan with precise, actionable steps.

## REMEDIATION PLAN STRUCTURE

### 1. IMMEDIATE CONTAINMENT (0-15 minutes)
For each action provide:
- **Action**: [Specific task]
- **Command/Procedure**: [Exact commands or steps]
- **Expected Result**: [What should happen]
- **Validation**: [How to verify success]
- **Rollback**: [How to undo if needed]

Example format:
```
Action 1: Block malicious IP at perimeter firewall
Command: iptables -A INPUT -s 192.168.1.100 -j DROP
Expected Result: All traffic from IP blocked
Validation: tcpdump -i eth0 src 192.168.1.100 (should show no packets)
Rollback: iptables -D INPUT -s 192.168.1.100 -j DROP
```

### 2. SHORT-TERM INVESTIGATION (15 minutes - 2 hours)
Provide detailed investigation procedures:
- **Log Analysis**:
  ```bash
  # Authentication logs
  grep -E "failed|error|denied" /var/log/auth.log | grep -v false_positive_pattern
  
  # Network connections
  netstat -tulpn | grep ESTABLISHED | awk '{print $5}' | sort | uniq -c | sort -rn
  ```
- **Memory Analysis**:
  ```bash
  # Capture memory
  sudo lime-dump -o /tmp/memory.dump
  
  # Check for suspicious processes
  ps aux | grep -E "unusual_pattern|backdoor_names"
  ```
- **File System Analysis**:
  ```bash
  # Find recently modified files
  find / -type f -mtime -1 -ls 2>/dev/null | grep -v /proc
  ```

### 3. MEDIUM-TERM REMEDIATION (2-24 hours)
- **System Hardening**:
  - Specific configuration changes with files and values
  - Security patch application procedures
  - Access control modifications
- **Monitoring Enhancement**:
  - New detection rules (provide exact syntax)
  - Alert thresholds (specific values)
  - Log retention changes

### 4. LONG-TERM PREVENTION (1-7 days)
- **Architecture Changes**:
  - Network segmentation recommendations
  - Zero-trust implementation steps
  - Identity management improvements
- **Process Improvements**:
  - Security training topics
  - Incident response playbook updates
  - Change management enhancements

### 5. RECOVERY VALIDATION
Provide specific tests:
```bash
# Test 1: Verify service functionality
curl -I https://service.example.com | grep "200 OK"

# Test 2: Check security controls
nmap -sS -p 1-65535 target_host | grep -E "open|filtered"

# Test 3: Validate logging
tail -f /var/log/security.log | grep "expected_pattern"
```

### 6. METRICS AND REPORTING
- **Success Criteria**: List measurable outcomes
- **KPIs to Monitor**: Specific metrics with thresholds
- **Reporting Requirements**: What, when, to whom

### 7. AUTOMATION OPPORTUNITIES
Identify which steps can be automated and provide pseudo-code or actual scripts.

Rate implementation:
- **Urgency** (1-10): ___ because [specific reason]
- **Complexity** (1-10): ___ because [specific challenges]
- **Resource Requirements**: [People, tools, time]
"""

    THREAT_INTEL_ENHANCED = """
You are a threat intelligence specialist. Provide COMPREHENSIVE intelligence enrichment.

## THREAT INTELLIGENCE REPORT

### 1. INDICATOR ENRICHMENT
For each indicator (IP, domain, hash, etc.):
```
Indicator: [value]
Type: [IP/Domain/Hash/Email/etc]
First Seen: [Date from threat feeds]
Last Seen: [Date]
Reputation Score: [0-100]
Associated Campaigns: [List]
Known Malware Families: [List]
Geolocation: [Country, ASN, ISP]
Historical Activity: [Timeline]
```

### 2. THREAT ACTOR ATTRIBUTION
- **Confidence Level**: ___% 
- **Likely Groups**: 
  1. [Group Name] - [Confidence %] - [TTPs match]
  2. [Group Name] - [Confidence %] - [TTPs match]
- **Motivation Assessment**: [Financial/Espionage/Hacktivism/etc]
- **Sophistication Level**: [1-10] with justification
- **Previous Targets**: [Industries/Organizations]

### 3. CAMPAIGN ANALYSIS
- **Campaign Name**: [If known]
- **Timeline**: [Start date - End date]
- **Targets**: [Industries, regions, technologies]
- **Infrastructure**:
  ```
  C2 Servers: [List with IPs/domains]
  Staging Servers: [List]
  Exfiltration Points: [List]
  ```
- **Tools Used**: [Malware, exploits, utilities]

### 4. TACTICAL ANALYSIS
Map to MITRE ATT&CK:
- **Initial Access**: [Technique IDs and descriptions]
- **Execution**: [Technique IDs and descriptions]
- **Persistence**: [Technique IDs and descriptions]
- **Privilege Escalation**: [Technique IDs and descriptions]
- **Defense Evasion**: [Technique IDs and descriptions]
- **Credential Access**: [Technique IDs and descriptions]
- **Discovery**: [Technique IDs and descriptions]
- **Lateral Movement**: [Technique IDs and descriptions]
- **Collection**: [Technique IDs and descriptions]
- **Exfiltration**: [Technique IDs and descriptions]
- **Impact**: [Technique IDs and descriptions]

### 5. RELATED INCIDENTS
- **Similar Incidents**: [List with dates and outcomes]
- **Sector Targeting**: [Patterns across industry]
- **Geographic Patterns**: [Regional focus]

### 6. PREDICTIVE ANALYSIS
- **Next Likely Actions**: [Based on TTPs]
- **Escalation Risk**: [Low/Medium/High with reasoning]
- **Timeline Prediction**: [Expected activity windows]

### 7. DEFENSIVE RECOMMENDATIONS
- **Detection Opportunities**: [Specific IoCs and behaviors]
- **Hunting Queries**: 
  ```
  # Splunk query example
  index=security sourcetype=firewall 
  | where src_ip IN (malicious_ip_list)
  | stats count by src_ip, dest_port
  ```
- **Blocking Recommendations**: [What to block and where]

### 8. INTELLIGENCE GAPS
- **Missing Information**: [What we don't know]
- **Collection Requirements**: [How to fill gaps]
- **Priority Intelligence Requirements (PIRs)**: [Critical questions]

If you disagree with the severity assessment, explain why with evidence.
"""

    REFLECTION_EXPERT_ENHANCED = """
You are a security architect and critical thinker. Provide DEEP, CONSTRUCTIVE analysis.

## CRITICAL REFLECTION REPORT

### 1. ANALYSIS QUALITY ASSESSMENT
Review each component:
- **Completeness** (0-100%): Did analysis cover all aspects?
- **Accuracy** (0-100%): Are conclusions well-supported?
- **Clarity** (0-100%): Is reasoning clear and logical?
- **Actionability** (0-100%): Can recommendations be implemented?

### 2. LOGICAL FLOW EXAMINATION
Trace the reasoning:
```
Observation: [What was observed]
↓ [Is this connection valid? Y/N - Why?]
Inference: [What was concluded]
↓ [Are there alternative explanations?]
Recommendation: [What was suggested]
↓ [Is this proportionate to the threat?]
Outcome: [Expected result]
```

### 3. ASSUMPTION IDENTIFICATION
List all assumptions made:
1. **Assumption**: [Statement]
   - **Validity**: [Strong/Moderate/Weak]
   - **Impact if Wrong**: [High/Medium/Low]
   - **How to Validate**: [Specific test or data]

### 4. ALTERNATIVE HYPOTHESES
For each major conclusion, provide alternatives:
- **Original Conclusion**: [Statement]
- **Alternative 1**: [Different explanation] - Likelihood: ___%
- **Alternative 2**: [Different explanation] - Likelihood: ___%
- **How to Differentiate**: [Specific tests or data points]

### 5. RISK-BENEFIT ANALYSIS
For each recommendation:
```
Recommendation: [Action]
Benefits:
- [Benefit 1]: Impact = High/Medium/Low
- [Benefit 2]: Impact = High/Medium/Low
Risks:
- [Risk 1]: Likelihood = High/Medium/Low
- [Risk 2]: Likelihood = High/Medium/Low
Cost-Benefit Score: [1-10]
```

### 6. MISSING CONTEXT IDENTIFICATION
- **Technical Context**: [What technical details are missing?]
- **Business Context**: [What business impact is unclear?]
- **Threat Context**: [What threat intelligence is lacking?]
- **Environmental Context**: [What system dependencies unknown?]

### 7. IMPROVEMENT RECOMMENDATIONS
Specific, actionable improvements:
1. **For Analysis**: [How to improve with specific steps]
2. **For Response**: [Better approaches with details]
3. **For Detection**: [Enhanced detection logic]
4. **For Prevention**: [Proactive measures]

### 8. CONFIDENCE CALIBRATION
- **Overall Confidence in Analysis**: ___%
- **Confidence in Severity**: ___%
- **Confidence in Attribution**: ___%
- **Confidence in Remediation**: ___%

Explain any low confidence areas and what would increase confidence.

### 9. DECISION QUALITY METRICS
- **Decision Complexity**: [Simple/Moderate/Complex]
- **Time Pressure**: [Low/Medium/High]
- **Information Completeness**: ___%
- **Recommendation Clarity**: [Clear/Somewhat Clear/Unclear]

### 10. LESSONS LEARNED
- **What Worked Well**: [Specific aspects]
- **What Could Improve**: [Specific aspects]
- **Process Enhancements**: [Suggestions for next time]
"""

    CODE_GENERATOR_ENHANCED = """
You are a security automation engineer. Generate PRODUCTION-READY code with comprehensive functionality.

## CODE GENERATION REQUIREMENTS

### 1. DETECTION SCRIPTS
Generate complete, working detection scripts:

```python
#!/usr/bin/env python3

import logging
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/anomaly_detection.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class AnomalyDetector:
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.thresholds = self.config.get('thresholds', {})
        
    def load_config(self, path: str) -> Dict:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def detect_anomaly(self, data: Dict) -> Optional[Dict]:
        # [Implement specific detection logic]
        pass
    
    def alert(self, anomaly: Dict) -> None:
        # [Implement alerting logic]
        pass

# Add test cases
if __name__ == "__main__":
    # Test case 1: Normal behavior
    # Test case 2: Anomalous behavior
    # Test case 3: Edge cases
    pass
```

### 2. REMEDIATION AUTOMATION
Generate scripts for each remediation action:

```bash
#!/bin/bash
# Remediation Script: [Specific Purpose]
# Usage: ./remediate.sh [options]

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
LOG_FILE="/var/log/remediation_$(date +%Y%m%d_%H%M%S).log"
BACKUP_DIR="/var/backups/pre_remediation"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Pre-remediation backup
backup_current_state() {
    log "Creating backup..."
    # [Backup logic here]
}

# Main remediation function
remediate() {
    log "Starting remediation..."
    
    # Step 1: [Specific action]
    if ! command_1; then
        log "ERROR: Step 1 failed"
        rollback
        exit 1
    fi
    
    # Step 2: [Specific action]
    # Continue...
}

# Rollback function
rollback() {
    log "Rolling back changes..."
    # [Rollback logic]
}

# Validation function
validate() {
    log "Validating remediation..."
    # [Validation checks]
}

# Main execution
main() {
    backup_current_state
    remediate
    validate
}

# Run with error handling
trap rollback ERR
main
```

### 3. MONITORING ENHANCEMENTS
Generate monitoring configurations:

```yaml
# Monitoring Rule: [Specific Purpose]
# Platform: [Splunk/ELK/Prometheus/etc]

rule:
  name: "Advanced Anomaly Detection - [Specific Type]"
  description: "Detects [specific behavior] indicating [threat type]"
  
  # Detection logic
  search: |
    index=security sourcetype=firewall
    | eval suspicious_score = case(
        src_port < 1024 AND dest_port > 49152, 10,
        bytes_out / bytes_in > 100, 20,
        connection_count > 1000, 30,
        1=1, 0
    )
    | where suspicious_score > 50
    | stats 
        count, 
        avg(bytes_out) as avg_bytes,
        list(dest_ip) as destinations 
        by src_ip
    
  # Alert configuration
  alert:
    threshold: 3
    window: 5m
    severity: high
    
  # Response automation
  actions:
    - type: "block_ip"
      auto_execute: false
      require_approval: true
    - type: "isolate_host"
      auto_execute: false
      require_approval: true
```

### 4. INTEGRATION CODE
Generate API integrations:

```python
class SecurityOrchestrator:    
    def __init__(self):
        self.siem = SIEMConnector()
        self.firewall = FirewallConnector()
        self.edr = EDRConnector()
        
    async def orchestrate_response(self, incident: Dict):
        # [Implementation with error handling]
        pass
```

### 5. TESTING FRAMEWORK
Include comprehensive tests:

```python
import unittest
from unittest.mock import Mock, patch

class TestRemediation(unittest.TestCase):
    def setUp(self):
        self.remediation = RemediationEngine()
        
    def test_ip_blocking(self):
        # [Test implementation]
        
    def test_rollback_on_failure(self):
        # [Test implementation]
```

### 6. DOCUMENTATION
Generate inline documentation and usage guides:

```markdown
# Script Documentation

## Overview
[What the script does]

## Requirements
- Python 3.8+
- Required libraries: [list]
- System permissions: [list]

## Usage
```bash
./script.py --config config.json --mode aggressive
```

## Configuration
[Explain all configuration options]

## Error Handling
[How errors are handled]

## Logging
[Where logs are stored and format]
```

Remember:
- Use secure coding practices
- Include comprehensive error handling
- Add logging at every critical step
- Make scripts idempotent
- Include rollback mechanisms
- Add input validation
- Use environment variables for sensitive data
"""

    DATA_COLLECTOR_ENHANCED = """
You are a digital forensics expert. Provide COMPREHENSIVE data collection strategies.

## DATA COLLECTION PLAN

### 1. IMMEDIATE COLLECTION (Volatile Data)
Time-sensitive data that changes or disappears:

```bash
# Memory Collection
echo "=== Memory Dump ==="
sudo lime -o /forensics/memory_$(date +%Y%m%d_%H%M%S).lime

# Network Connections
echo "=== Active Connections ==="
netstat -tulpan > /forensics/netstat_$(date +%Y%m%d_%H%M%S).txt
ss -tulpan > /forensics/ss_$(date +%Y%m%d_%H%M%S).txt
lsof -i > /forensics/lsof_network_$(date +%Y%m%d_%H%M%S).txt

# Process Information
echo "=== Running Processes ==="
ps auxww > /forensics/ps_full_$(date +%Y%m%d_%H%M%S).txt
ps -eo pid,ppid,cmd,etime,etime > /forensics/ps_tree_$(date +%Y%m%d_%H%M%S).txt
```

### 2. SYSTEM ARTIFACTS
Critical system data:

```bash
# System Information
echo "=== System Info ==="
uname -a > /forensics/uname.txt
hostname > /forensics/hostname.txt
uptime > /forensics/uptime.txt
w > /forensics/who_logged_in.txt
last -100 > /forensics/last_logins.txt

# File System Timeline
echo "=== File System Timeline ==="
find / -type f -mtime -7 -ls 2>/dev/null > /forensics/modified_files_7days.txt
find / -type f -atime -1 -ls 2>/dev/null > /forensics/accessed_files_1day.txt
```

### 3. LOG COLLECTION MATRIX
Specify exactly which logs and what timeframes:

| Log Type | Location | Timeframe | Priority | Collection Command |
|----------|----------|-----------|----------|-------------------|
| Auth logs | /var/log/auth.log | Last 72h | CRITICAL | `grep -E "$(date -d '3 days ago' +'%b %d')\|$(date -d '2 days ago' +'%b %d')\|$(date -d '1 day ago' +'%b %d')\|$(date +'%b %d')" /var/log/auth.log*` |
| Web server | /var/log/apache2/ | Last 24h | HIGH | `tar czf apache_logs.tar.gz /var/log/apache2/*log` |
| Firewall | /var/log/iptables.log | Last 7d | HIGH | `zgrep -h "" /var/log/iptables.log* > firewall_combined.log` |
| Application | /app/logs/ | Last 48h | MEDIUM | Custom per application |

### 4. CORRELATION REQUIREMENTS
Data needed for correlation:

```yaml
correlation_map:
  network_data:
    - netflow_records
    - dns_queries
    - dhcp_leases
    - arp_cache
    
  identity_data:
    - ldap_logs
    - radius_logs
    - vpn_connections
    - badge_access
    
  endpoint_data:
    - edr_telemetry
    - antivirus_logs
    - software_inventory
    - patch_status
```

### 5. EXTERNAL DATA SOURCES
Third-party data requirements:

- **Threat Intelligence Feeds**:
  ```python
  feeds = [
      {"name": "AlienVault OTX", "api": "https://otx.alienvault.com/api/v1/"},
      {"name": "VirusTotal", "api": "https://www.virustotal.com/api/v3/"},
      {"name": "AbuseIPDB", "api": "https://api.abuseipdb.com/api/v2/"}
  ]
  ```

- **OSINT Collection**:
  ```bash
  # Domain research
  whois suspicious.domain.com
  dig ANY suspicious.domain.com
  host suspicious.domain.com
  
  # IP research
  whois 192.168.1.100
  geoiplookup 192.168.1.100
  ```

### 6. EVIDENCE PRESERVATION
Chain of custody procedures:

```bash
#!/bin/bash
# Evidence preservation script

CASE_ID="INC_$(date +%Y%m%d_%H%M%S)"
EVIDENCE_DIR="/forensics/cases/$CASE_ID"

# Create case directory
mkdir -p "$EVIDENCE_DIR"/{raw,processed,reports}

# Generate hashes for all collected files
find "$EVIDENCE_DIR" -type f -exec sha256sum {} \; > "$EVIDENCE_DIR/evidence_hashes.txt"

# Create evidence manifest
cat > "$EVIDENCE_DIR/manifest.txt" << EOF
Case ID: $CASE_ID
Collection Date: $(date)
Collector: $(whoami)
System: $(hostname)
Reason: [Incident description]
EOF

# Encrypt sensitive evidence
tar czf - "$EVIDENCE_DIR" | gpg --encrypt -r security-team > "$EVIDENCE_DIR.tar.gz.gpg"
```

### 7. ANALYSIS PRIORITIES
Order of analysis with specific focus areas:

1. **Immediate Threats** (0-1 hour):
   - Active C2 communications
   - Ongoing data exfiltration
   - Spreading malware

2. **Attack Reconstruction** (1-4 hours):
   - Initial compromise vector
   - Lateral movement paths
   - Privilege escalation methods

3. **Impact Assessment** (4-8 hours):
   - Data accessed/stolen
   - Systems compromised
   - Credentials exposed

### 8. TOOLING REQUIREMENTS
Specific tools needed:

```yaml
tools:
  collection:
    - name: "Velociraptor"
      purpose: "Endpoint collection"
      deployment: "Agent-based"
    - name: "KAPE"
      purpose: "Triage collection"
      deployment: "Standalone"
      
  analysis:
    - name: "Volatility3"
      purpose: "Memory analysis"
    - name: "Plaso"
      purpose: "Timeline creation"
    - name: "X-Ways"
      purpose: "Disk forensics"
```

### 9. COLLECTION VALIDATION
Verify data integrity:

```python
def validate_collection(evidence_dir):
    validations = {
        "completeness": check_all_sources_collected(),
        "integrity": verify_hashes(),
        "timestamp_consistency": check_time_sync(),
        "format_validity": verify_log_formats(),
        "size_reasonable": check_file_sizes()
    }
    return all(validations.values())
```

### 10. REPORTING REQUIREMENTS
What to include in collection report:

- Collection methodology
- Time synchronization verification
- Gap analysis (what couldn't be collected)
- Initial observations
- Recommended analysis priorities
"""


class AgentManager:
    """
    Unified LangGraph-based agent manager with basic and enhanced capabilities.
    
    This class combines the functionality of both the basic AgentManager and
    the EnhancedAgentManager, providing a unified interface with mode selection.
    """
    
    def __init__(self, config: Dict[str, Any], storage_manager=None, visualizer=None, mode="enhanced"):
        """
        Initialize agent manager with configuration.
        
        Args:
            config: Agent configuration
            storage_manager: Storage manager for persistence
            visualizer: Optional visualizer for Streamlit integration
            mode: Operation mode - "basic" or "enhanced" (default)
        """
        self.config = config
        self.storage_manager = storage_manager
        self.visualizer = visualizer
        self.mode = mode
        self.logger = logging.getLogger("agent_manager")
        
        # Initialize enhanced prompts instance
        self.enhanced_prompt_templates = EnhancedAgentPrompts()
        
        # Initialize basic prompts
        self.basic_prompts = {
            "security_analyst": """
You are a security analyst responsible for analyzing anomalies detected in system logs.
Your task is to examine the provided anomaly data and determine:

1. The severity of the anomaly (Critical, High, Medium, Low)
2. The potential threat it represents
3. A detailed analysis of what the anomaly indicates
4. Whether this is likely a false positive

Use the full context of the anomaly data to provide a comprehensive analysis.
If you're uncertain about any aspect, indicate your confidence level.

Format your response as a structured analysis with clear sections.
""",
            "remediation_expert": """
You are a security remediation expert responsible for providing actionable steps to
address security anomalies. Based on the security analysis provided, recommend:

1. Immediate containment actions to limit damage
2. Investigation steps to gather more information
3. Remediation steps to fix the issue
4. Prevention measures to avoid similar issues in the future

Each recommendation should be specific, actionable, and prioritized.
Include any commands, configuration changes, or procedures that would help.

Format your response as a structured remediation plan with clear sections.
""",
            "reflection_expert": """
You are a security reflection expert responsible for critically evaluating security
analyses and remediation plans. Your task is to:

1. Identify any gaps, assumptions, or weaknesses in the analysis
2. Challenge conclusions that may not be fully supported by the evidence
3. Suggest improvements to the analysis and remediation plan
4. Consider alternative explanations or approaches

Be constructive but thorough in your critique. The goal is to improve the overall
security response, not to simply find fault.

Format your response as a structured reflection with clear sections.
""",
            "security_critic": """
You are a security critic responsible for identifying potential false positives,
missing context, or incomplete analyses. Your task is to:

1. Evaluate whether the anomaly is likely a real security issue or a false positive
2. Identify any missing contextual information that would help analysis
3. Point out logical leaps or assumptions in the analysis
4. Question whether the recommended actions are proportionate to the threat

Be skeptical but fair in your assessment. Consider both the risk of overreaction
and the risk of missing a genuine threat.

Format your response as a structured critique with clear sections.
""",
            "code_generator": """
You are a security code generator responsible for creating secure, efficient code for
remediation actions. Based on the remediation plan, create:

1. Scripts or commands to implement the recommended actions
2. Monitoring code to verify the effectiveness of the remediation
3. Documentation for the code that explains its purpose and usage

Focus on security best practices, defensive coding, and clear error handling.
Make sure your code is properly commented and follows best practices for the language.

Format your response with clearly separated code blocks with language indicators.
""",
            "data_collector": """
You are a security data collector responsible for identifying additional data needed
for a thorough investigation. Based on the anomaly and analysis, determine:

1. What additional logs, files, or artifacts should be collected
2. Specific commands or procedures to gather this data
3. How to preserve evidence for potential forensic analysis
4. What contextual information would help improve the analysis

Be comprehensive but focused on data that would specifically help with this incident.
Consider both technical data and business context.

Format your response as a structured data collection plan with clear sections.
"""
        }
        
        # Initialize enhanced prompts - now using the enhanced prompt templates
        self.enhanced_prompts = {
            "security_analyst": self.enhanced_prompt_templates.SECURITY_ANALYST_ENHANCED,
            "threat_intel": self.enhanced_prompt_templates.THREAT_INTEL_ENHANCED,
            "remediation": self.enhanced_prompt_templates.REMEDIATION_EXPERT_ENHANCED,
            "code_generator": self.enhanced_prompt_templates.CODE_GENERATOR_ENHANCED,
            "security_review": self.enhanced_prompt_templates.REFLECTION_EXPERT_ENHANCED,
            "data_collector": self.enhanced_prompt_templates.DATA_COLLECTOR_ENHANCED
        }
        
        # Basic agent workflow for visualization
        self.basic_workflow = {
            "nodes": [
                "security_analyst", 
                "remediation_expert", 
                "reflection_expert", 
                "security_critic", 
                "code_generator", 
                "data_collector"
            ],
            "edges": [
                {"from": "security_analyst", "to": "remediation_expert"},
                {"from": "remediation_expert", "to": "reflection_expert"},
                {"from": "reflection_expert", "to": "security_critic"},
                {"from": "security_critic", "to": "code_generator"},
                {"from": "code_generator", "to": "data_collector"}
            ]
        }
        
        # Enhanced agent workflow with feedback loops
        self.enhanced_workflow = {
            "nodes": [
                "security_analyst", 
                "threat_intel",
                "consensus_builder",
                "remediation", 
                "code_generator", 
                "security_review",
                "data_collector"
            ],
            "edges": [
                {"from": "security_analyst", "to": "threat_intel"},
                {"from": "threat_intel", "to": "consensus_builder"},
                {"from": "consensus_builder", "to": "remediation"},
                {"from": "remediation", "to": "code_generator"},
                {"from": "code_generator", "to": "security_review"},
                {"from": "security_review", "to": "data_collector"},
                # Feedback loops
                {"from": "security_review", "to": "security_analyst", "type": "feedback"},
                {"from": "consensus_builder", "to": "security_analyst", "type": "clarification"}
            ]
        }
        
        # Agent specializations for better collaboration
        self.agent_specializations = {
            "security_analyst": ["detection", "analysis", "classification"],
            "threat_intel": ["attribution", "correlation", "intelligence"],
            "remediation": ["containment", "eradication", "recovery"],
            "code_generator": ["automation", "scripting", "integration"],
            "security_review": ["validation", "quality", "compliance"],
            "data_collector": ["forensics", "evidence", "preservation"]
        }
        
        # Set the agent workflow based on mode
        self.agent_workflow = self.enhanced_workflow if mode == "enhanced" else self.basic_workflow
        
        # Reflection configuration
        self.reflection_rounds = config.get("reflection_rounds", 2)
        
        # Initialize LLM client
        self.llm_client = self._create_llm_client()
        
        # Initialize agent graph
        if LANGGRAPH_AVAILABLE and self.llm_client:
            if mode == "enhanced":
                self.agent_graph = self._create_enhanced_agent_graph()
            else:
                self.agent_graph = self._create_basic_agent_graph()
        else:
            self.agent_graph = None
            
        self.logger.info(f"Initialized Unified Agent Manager in {mode} mode")
        
        # Visualize the initial agent workflow if visualizer is provided
        if self.visualizer:
            self.visualizer.visualize_agent_graph(self.agent_workflow)
    
    def _create_enhanced_agent_graph(self):
        """
        Create the enhanced agent graph for comprehensive anomaly analysis.
        
        Returns:
            Compiled graph for agent execution
        """
        from langgraph.graph import StateGraph, END
        
        # Create the graph
        graph = StateGraph(dict)
        
        # Define agent nodes
        agents = [
            "security_analyst",
            "threat_intel",
            "remediation",
            "code_generator",
            "security_review",
            "data_collector"
        ]
        
        # Add nodes for each agent
        for agent in agents:
            graph.add_node(agent, lambda state, agent_name=agent: self._run_agent(state, agent_name))
        
        # Add edges based on workflow
        graph.add_edge("security_analyst", "threat_intel")
        graph.add_edge("threat_intel", "remediation")
        graph.add_edge("remediation", "code_generator")
        graph.add_edge("code_generator", "security_review")
        graph.add_edge("security_review", "data_collector")
        graph.add_edge("data_collector", END)
        
        # Set entry point
        graph.set_entry_point("security_analyst")
        
        # Compile the graph
        return graph.compile()
    
    def _run_agent(self, state, agent_name):
        """
        Run a specific agent in the enhanced workflow.
        
        Args:
            state: Current state dictionary
            agent_name: Name of the agent to run
            
        Returns:
            Updated state
        """
        # Get the anomaly from state
        anomaly = state.get("anomaly", {})
        
        # Log activity if visualizer is available
        if self.visualizer:
            self.visualizer.log_agent_activity(
                agent_name,
                "processing",
                "started",
                {"anomaly_id": anomaly.get("id")}
            )
        
        try:
            # Get agent prompt
            prompt = self.get_agent_prompt(agent_name, anomaly)
            
            # Run the agent using llm_client
            if self.llm_client:
                response = self.llm_client(prompt)
            else:
                response = "LLM client not available"
            
            # Update state with agent response
            if agent_name not in state:
                state[agent_name] = {}
            
            state[agent_name]["response"] = response
            state[agent_name]["timestamp"] = datetime.datetime.utcnow().isoformat()
            
            # Log completion
            if self.visualizer:
                self.visualizer.log_agent_activity(
                    agent_name,
                    "processing",
                    "completed",
                    {
                        "anomaly_id": anomaly.get("id"),
                        "response_length": len(response)
                    }
                )
                
        except Exception as e:
            # Log error
            if self.visualizer:
                self.visualizer.log_agent_activity(
                    agent_name,
                    "processing",
                    "failed",
                    {
                        "anomaly_id": anomaly.get("id"),
                        "error": str(e)
                    }
                )
            
            state[agent_name] = {
                "error": str(e),
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        
        return state
    
    def get_agent_prompt(self, agent_name, anomaly):
        """
        Get the prompt for a specific agent.
        
        Args:
            agent_name: Name of the agent
            anomaly: Anomaly data
            
        Returns:
            Formatted prompt string
        """
        # Default prompts for each agent
        prompts = {
            "security_analyst": f"""
You are a security analyst. Analyze this anomaly and determine:
1. Severity level (Critical/High/Medium/Low)
2. Type of potential threat
3. Whether it's likely a false positive
4. Initial risk assessment

Anomaly data:
{json.dumps(anomaly, indent=2)}

Provide a structured analysis.
""",
            "threat_intel": f"""
You are a threat intelligence expert. Based on the security analysis, provide:
1. Known threat patterns that match this anomaly
2. Indicators of compromise (IoCs)
3. Related threat actors or campaigns
4. Historical context

Anomaly data:
{json.dumps(anomaly, indent=2)}

Provide detailed threat intelligence.
""",
            "remediation": f"""
You are a remediation expert. Provide:
1. Immediate containment steps
2. Investigation procedures
3. Long-term remediation actions
4. Prevention measures

Anomaly data:
{json.dumps(anomaly, indent=2)}

Provide actionable remediation steps.
""",
            "code_generator": f"""
You are a security code generator. Create:
1. Scripts for automated response
2. Detection rules
3. Monitoring queries
4. Remediation automation

Anomaly data:
{json.dumps(anomaly, indent=2)}

Generate practical, secure code.
""",
            "security_review": f"""
You are a security reviewer. Review the analysis and:
1. Validate findings
2. Check for missed threats
3. Verify remediation completeness
4. Suggest improvements

Anomaly data:
{json.dumps(anomaly, indent=2)}

Provide a comprehensive review.
""",
            "data_collector": f"""
You are a data collector. Identify:
1. Additional data needed
2. Log sources to check
3. Correlation opportunities
4. Evidence preservation needs

Anomaly data:
{json.dumps(anomaly, indent=2)}

Specify data collection requirements.
"""
        }
        
        return prompts.get(agent_name, f"Analyze this anomaly: {json.dumps(anomaly, indent=2)}")
    
    def _create_llm_client(self):
        """Create LLM client based on configuration."""
        if not self.config.get("llm", {}).get("provider"):
            self.logger.error("No LLM provider configured")
            return None
        
        provider = self.config["llm"]["provider"]
        
        if provider == "ollama":
            if not OLLAMA_AVAILABLE:
                self.logger.error("Ollama client not installed")
                return None
            
            # Configure Ollama client
            base_url = self.config["llm"].get("base_url", "http://localhost:11434")
            model = self.config["llm"].get("model", "mistral")
            
            # Set Ollama base URL
            os.environ["OLLAMA_HOST"] = base_url
            
            self.logger.info(f"Using Ollama with model {model}")
            
            # Get enhanced settings from config
            max_tokens = self.config.get("llm", {}).get("max_tokens", 8192)
            default_temp = self.config.get("llm", {}).get("temperature", 0.3)
            
            # Create a wrapper function that calls Ollama
            def ollama_generate(prompt, system_prompt=None, temperature=None, max_tokens=None):
                try:
                    # Use provided values or defaults from config
                    temp = temperature if temperature is not None else default_temp
                    tokens = max_tokens if max_tokens is not None else self.config.get("llm", {}).get("max_tokens", 8192)
                    
                    # Log to visualizer if available
                    if self.visualizer:
                        self.visualizer.log_agent_activity(
                            "ollama_llm",
                            "generate",
                            "started",
                            {"model": model, "prompt_length": len(prompt)}
                        )
                    
                    response = ollama.chat(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        options={
                            "temperature": temp,
                            "num_predict": tokens
                        }
                    )
                    
                    response_content = response["message"]["content"]
                    
                    # Check for minimum response length if configured
                    min_length = self.config.get("response_enhancement", {}).get("min_response_length", 1000)
                    if len(response_content) < min_length and self.config.get("performance", {}).get("retry_on_brief_response", True):
                        # Retry with more explicit instructions
                        retry_prompt = prompt + f"\n\nIMPORTANT: Please provide a DETAILED response with at least {min_length} characters. Include specific examples, commands, and comprehensive analysis."
                        
                        response = ollama.chat(
                            model=model,
                            messages=[
                                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                                {"role": "user", "content": retry_prompt}
                            ],
                            options={
                                "temperature": temp,
                                "num_predict": tokens
                            }
                        )
                        response_content = response["message"]["content"]
                    
                    # Log completion to visualizer
                    if self.visualizer:
                        self.visualizer.log_agent_activity(
                            "ollama_llm",
                            "generate",
                            "completed",
                            {"model": model, "response_length": len(response_content)}
                        )
                    
                    return response_content
                except Exception as e:
                    self.logger.error(f"Error calling Ollama: {str(e)}")
                    
                    # Log error to visualizer
                    if self.visualizer:
                        self.visualizer.log_agent_activity(
                            "ollama_llm",
                            "generate",
                            "error",
                            {"error": str(e)}
                        )
                    
                    return f"Error: {str(e)}"
            
            return ollama_generate
        else:
            self.logger.error(f"Unsupported LLM provider: {provider}")
            return None
    
    def _create_basic_agent_graph(self):
        """Create basic agent graph (placeholder for now)."""
        # This is a placeholder - implement if needed
        return None
    
    def parse_structured_response(self, response_text: str, agent_type: str) -> Dict[str, Any]:
        """Parse structured responses from agents into organized data."""
        
        structured_data = {
            "raw_response": response_text,
            "sections": {},
            "metrics": {},
            "action_items": [],
            "code_blocks": [],
            "commands": []
        }
        
        # Extract sections based on headers
        section_pattern = r"##\s+(\d+\.\s+)?(.+?)(?=\n##|\Z)"
        sections = re.findall(section_pattern, response_text, re.DOTALL)
        
        for _, section_title in sections:
            section_content = re.search(
                rf"##\s+\d+\.\s+{re.escape(section_title)}(.+?)(?=\n##|\Z)",
                response_text,
                re.DOTALL
            )
            if section_content:
                structured_data["sections"][section_title.strip()] = section_content.group(1).strip()
        
        # Extract metrics (scores, percentages, ratings)
        metrics_patterns = {
            "confidence": r"(?:confidence|certainty)[:\s]+(\d+)%",
            "severity": r"severity[:\s]+(Critical|High|Medium|Low)",
            "urgency": r"urgency[:\s]+(\d+)",
            "complexity": r"complexity[:\s]+(\d+)",
            "risk_score": r"risk\s+score[:\s]+(\d+)"
        }
        
        for metric_name, pattern in metrics_patterns.items():
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                structured_data["metrics"][metric_name] = match.group(1)
        
        # Extract code blocks
        code_blocks = re.findall(r"```(\w*)\n(.*?)```", response_text, re.DOTALL)
        for lang, code in code_blocks:
            structured_data["code_blocks"].append({
                "language": lang or "bash",
                "code": code.strip()
            })
        
        # Extract commands (lines starting with $ or #)
        command_lines = re.findall(r"^\s*[$#]\s*(.+)$", response_text, re.MULTILINE)
        structured_data["commands"].extend(command_lines)
        
        # Extract action items (numbered lists)
        action_pattern = r"^\s*\d+\.\s+(.+?)(?=^\s*\d+\.|\Z)"
        actions = re.findall(action_pattern, response_text, re.MULTILINE | re.DOTALL)
        structured_data["action_items"].extend([action.strip() for action in actions])
        
        return structured_data
    
    def process_agent_response(self, state: EnhancedAgentState, agent_name: str, response: str) -> Dict[str, Any]:
        """Process agent response and extract structured data."""
        
        # Parse the structured response
        parsed = self.parse_structured_response(response, agent_name)
        
        # Update state with parsed data
        if agent_name not in state.agent_insights:
            state.agent_insights[agent_name] = []
        
        state.agent_insights[agent_name].append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "parsed_response": parsed,
            "key_findings": parsed.get("sections", {}).get("INITIAL ASSESSMENT", "")[:200],
            "metrics": parsed.get("metrics", {}),
            "action_count": len(parsed.get("action_items", []))
        })
        
        # Extract evidence for evidence chain
        if "evidence" in response.lower():
            evidence_items = re.findall(r"evidence:?\s*(.+?)(?=\n|$)", response, re.IGNORECASE)
            for evidence in evidence_items:
                state.evidence_chain.append({
                    "agent": agent_name,
                    "evidence": evidence.strip(),
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })
        
        # Update confidence scores
        if "confidence" in parsed["metrics"]:
            state.confidence_scores[agent_name] = float(parsed["metrics"]["confidence"]) / 100.0
        
        # Extract collaboration requests
        if "questions" in response.lower() or "need" in response.lower():
            questions = re.findall(r"(?:question|need)[:\s]+(.+?)(?=\n|$)", response, re.IGNORECASE)
            for question in questions:
                state.collaboration_requests.append({
                    "from": agent_name,
                    "request": question.strip(),
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })
        
        return parsed
    
    def generate_executive_summary(self, state: EnhancedAgentState) -> str:
        """Generate an executive summary from all agent analyses."""
        
        summary_parts = [
            "## EXECUTIVE SUMMARY\n",
            f"**Incident ID**: {state.anomalies[0].get('id', 'Unknown') if state.anomalies else 'Unknown'}",
            f"**Analysis Date**: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ""
        ]
        
        # Get consensus severity
        if state.analysis:
            severity = state.analysis.get("consensus_severity", state.analysis.get("severity", "Unknown"))
            summary_parts.append(f"**Severity**: {severity}")
        
        # Average confidence
        if state.confidence_scores:
            avg_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
            summary_parts.append(f"**Overall Confidence**: {avg_confidence*100:.0f}%")
        
        # Key findings from each agent
        summary_parts.append("\n### Key Findings by Agent\n")
        for agent, insights in state.agent_insights.items():
            if insights:
                latest = insights[-1]
                summary_parts.append(f"**{agent.replace('_', ' ').title()}**:")
                summary_parts.append(f"- {latest.get('key_findings', 'No findings available')}")
                if latest.get('metrics'):
                    metrics_str = ", ".join([f"{k}: {v}" for k, v in latest['metrics'].items()])
                    summary_parts.append(f"- Metrics: {metrics_str}")
                summary_parts.append("")
        
        # Action items summary
        if state.action_items:
            summary_parts.append("### Priority Actions\n")
            for i, action in enumerate(state.action_items[:5], 1):
                summary_parts.append(f"{i}. {action.get('actions', 'Action details not available')}")
        
        # Evidence chain summary
        if state.evidence_chain:
            summary_parts.append("\n### Evidence Chain\n")
            for evidence in state.evidence_chain[:5]:
                summary_parts.append(f"- {evidence['agent']}: {evidence['evidence']}")
        
        return "\n".join(summary_parts)
    
    def generate_comprehensive_report(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Generate a comprehensive report from all agent analyses."""
        
        report = {
            "executive_summary": self.generate_executive_summary(state),
            "detailed_analysis": {},
            "action_plan": {},
            "evidence_summary": [],
            "metrics_dashboard": {},
            "recommendations": []
        }
        
        # Compile detailed analysis from each agent
        if state.analysis:
            report["detailed_analysis"]["security_analyst"] = {
                "findings": state.analysis.get("analysis", ""),
                "severity": state.analysis.get("severity", "Unknown"),
                "confidence": state.confidence_scores.get("security_analyst", 0),
                "parsed_data": state.additional_data.get("parsed_responses", {}).get("security_analyst", {})
            }
        
        if state.remediation:
            report["detailed_analysis"]["remediation"] = {
                "plan": state.remediation.get("remediation_plan", ""),
                "urgency": state.remediation.get("urgency", 0),
                "complexity": state.remediation.get("complexity", 0)
            }
        
        # Compile action plan
        immediate_actions = []
        short_term_actions = []
        long_term_actions = []
        
        for item in state.action_items:
            if "immediate" in str(item).lower() or item.get("timeframe") == "0-15 minutes":
                immediate_actions.append(item)
            elif "short" in str(item).lower() or "hour" in str(item).lower():
                short_term_actions.append(item)
            else:
                long_term_actions.append(item)
        
        report["action_plan"] = {
            "immediate": immediate_actions,
            "short_term": short_term_actions,
            "long_term": long_term_actions
        }
        
        # Compile evidence chain
        report["evidence_summary"] = state.evidence_chain
        
        # Compile metrics
        for agent, score in state.confidence_scores.items():
            report["metrics_dashboard"][f"{agent}_confidence"] = score
        
        # Generate recommendations based on consensus
        if state.consensus_needed:
            report["recommendations"].append({
                "type": "consensus_required",
                "items": state.consensus_needed,
                "recommendation": "Review conflicting assessments and establish consensus"
            })
        
        if any(score < 0.5 for score in state.confidence_scores.values()):
            report["recommendations"].append({
                "type": "low_confidence",
                "recommendation": "Collect additional data to increase analysis confidence"
            })
        
        return report
    
    def format_analysis_results(self, anomalies: List[Dict[str, Any]]) -> str:
        """Format analysis results for display or export."""
        
        formatted_output = []
        formatted_output.append("=" * 80)
        formatted_output.append("ANOMALY DETECTION ANALYSIS REPORT")
        formatted_output.append("=" * 80)
        formatted_output.append("")
        
        for anomaly in anomalies:
            formatted_output.append(f"## Anomaly ID: {anomaly.get('id', 'Unknown')}")
            formatted_output.append(f"Detection Time: {anomaly.get('timestamp', 'Unknown')}")
            formatted_output.append(f"Score: {anomaly.get('score', 0):.3f}")
            formatted_output.append(f"Model: {anomaly.get('model', 'Unknown')}")
            formatted_output.append("")
            
            # Analysis section
            if "analysis" in anomaly:
                analysis = anomaly["analysis"]
                formatted_output.append("### Security Analysis")
                formatted_output.append(f"Severity: {analysis.get('severity', 'Unknown')}")
                formatted_output.append(f"Confidence: {analysis.get('confidence', 0)*100:.0f}%")
                formatted_output.append("")
                
                # Include key findings
                if "parsed_data" in analysis:
                    parsed = analysis["parsed_data"]
                    if "sections" in parsed:
                        for section, content in parsed["sections"].items():
                            formatted_output.append(f"#### {section}")
                            formatted_output.append(content[:500] + "..." if len(content) > 500 else content)
                            formatted_output.append("")
            
            # Remediation section
            if "remediation" in anomaly:
                remediation = anomaly["remediation"]
                formatted_output.append("### Remediation Plan")
                formatted_output.append(f"Urgency: {remediation.get('urgency', 'N/A')}/10")
                formatted_output.append(f"Complexity: {remediation.get('complexity', 'N/A')}/10")
                formatted_output.append("")
            
            # Agent dialogue section
            if "agent_dialogue" in anomaly:
                formatted_output.append("### Agent Collaboration")
                for dialogue in anomaly["agent_dialogue"][-5:]:  # Last 5 exchanges
                    formatted_output.append(
                        f"- {dialogue['from']} → {dialogue['to']}: {dialogue['message'][:100]}..."
                    )
                formatted_output.append("")
            
            formatted_output.append("-" * 80)
            formatted_output.append("")
        
        return "\n".join(formatted_output)
    
    def analyze_anomalies(self, anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze a list of anomalies using the agent system.
        
        Args:
            anomalies: List of anomalies to analyze
            
        Returns:
            List of analyzed anomalies with agent insights
        """
        analyzed_results = []
        
        for anomaly in anomalies:
            try:
                # Run the agent graph
                if self.agent_graph and LANGGRAPH_AVAILABLE:
                    initial_state = {"anomaly": anomaly}
                    final_state = self.agent_graph.invoke(initial_state)
                    
                    # Extract results from final state
                    anomaly["agent_analysis"] = {
                        agent: final_state.get(agent, {})
                        for agent in ["security_analyst", "threat_intel", "remediation", 
                                    "code_generator", "security_review", "data_collector"]
                    }
                    
                    # Add summary analysis
                    anomaly["analysis"] = {
                        "severity": self._extract_severity(final_state),
                        "threat_type": self._extract_threat_type(final_state),
                        "confidence": self._calculate_confidence(final_state)
                    }
                else:
                    # Fallback if no graph available
                    anomaly["analysis"] = {
                        "error": "Agent graph not available",
                        "severity": "Unknown"
                    }
                
                analyzed_results.append(anomaly)
                
            except Exception as e:
                self.logger.error(f"Error analyzing anomaly: {str(e)}")
                anomaly["analysis"] = {
                    "error": str(e),
                    "severity": "Unknown"
                }
                analyzed_results.append(anomaly)
        
        return analyzed_results
    
    def _extract_severity(self, state: Dict[str, Any]) -> str:
        """Extract severity from agent responses."""
        # Check security analyst response
        if "security_analyst" in state and "response" in state["security_analyst"]:
            response = state["security_analyst"]["response"]
            for severity in ["Critical", "High", "Medium", "Low"]:
                if severity.lower() in response.lower():
                    return severity
        return "Unknown"
    
    def _extract_threat_type(self, state: Dict[str, Any]) -> str:
        """Extract threat type from agent responses."""
        # Check threat intel response
        if "threat_intel" in state and "response" in state["threat_intel"]:
            response = state["threat_intel"]["response"]
            # Simple pattern matching for common threat types
            threat_types = ["malware", "phishing", "ddos", "intrusion", "data_leak"]
            for threat in threat_types:
                if threat in response.lower():
                    return threat.title()
        return "Unknown"
    
    def _calculate_confidence(self, state: Dict[str, Any]) -> float:
        """Calculate overall confidence from agent responses."""
        confidences = []
        for agent in ["security_analyst", "threat_intel", "remediation"]:
            if agent in state and "response" in state[agent]:
                # Simple heuristic: longer responses indicate more confidence
                response_length = len(state[agent]["response"])
                confidence = min(1.0, response_length / 1000)  # Normalize to 0-1
                confidences.append(confidence)
        
        return sum(confidences) / len(confidences) if confidences else 0.5