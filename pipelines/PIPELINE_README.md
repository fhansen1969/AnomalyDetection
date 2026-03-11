Anomaly Detection Pipeline System Documentation

Table of Contents

Overview
Pipeline Usage Guide
Architecture
Pipeline Components
Data Flow
Pipeline Types and Workflows
Feature Engineering
Model Management
Correlation Analysis
Deployment Strategy
Monitoring and Maintenance
Best Practices
Troubleshooting

Overview
The Anomaly Detection Pipeline System is a comprehensive ML pipeline infrastructure designed to detect anomalies in various data sources with advanced correlation analysis capabilities. The system consists of three specialized bash pipeline scripts that work together in a structured workflow:

test_pipeline.sh: For experimental model development and testing with correlation validation
validation_pipeline.sh: For model validation, performance assessment, and correlation capability verification
detect_anomalies_pipeline.sh: For production anomaly detection with real-time correlation analysis

Key Features

Multi-source data ingestion (files, databases, APIs, Kafka)
Automated data preprocessing and feature engineering
Multiple ML model support (Isolation Forest, Statistical, Autoencoder, GAN, One-Class SVM, Ensemble)
Advanced correlation analysis for pattern detection
Correlation matrix generation and visualization
Multi-agent AI system for anomaly analysis
Real-time alerting with correlation insights
Comprehensive logging and visualization

Pipeline Usage Guide

When to Use Each Pipeline

1. Test Pipeline (test_pipeline.sh)
When to use:

Starting a new anomaly detection project
Experimenting with new feature engineering approaches
Testing different model architectures
Developing custom anomaly detection algorithms
Testing correlation detection capabilities
Initial data exploration and preprocessing

Prerequisites:

Place test data in data/test/ directory
Configure config/test_config.yaml (or use default config/config.yaml)
Ensure API server is running

Basic Usage:
# Run full test pipeline with correlation testing
./test_pipeline.sh config/test_config.yaml

# Skip certain stages if needed
./test_pipeline.sh --skip-collection  # If data already collected
./test_pipeline.sh --skip-preprocessing  # If data already preprocessed
./test_pipeline.sh --skip-training  # To only evaluate existing models
./test_pipeline.sh --skip-correlation-test  # Skip correlation testing

2. Validation Pipeline (validation_pipeline.sh)
When to use:

After training models in test pipeline
Before promoting models to production
Validating model performance on holdout datasets
Verifying correlation analysis capabilities
Compliance testing and audit requirements
A/B testing between model versions

Prerequisites:

Trained models available (from test pipeline)
Validation data in data/validation/ directory
Different from training data to ensure unbiased evaluation

Basic Usage:

# Run validation with default thresholds
./validation_pipeline.sh config/validation_config.yaml

# Run with custom validation thresholds
./validation_pipeline.sh --min-precision 0.8 --min-recall 0.7 --max-fpr 0.2

3. Detection Pipeline (detect_anomalies_pipeline.sh)
When to use:

Production anomaly detection
Real-time monitoring of systems
Batch processing of historical data
Correlation analysis of detected anomalies
Incident investigation with pattern analysis
Continuous monitoring scenarios

Prerequisites:

Validated models available (from validation pipeline)
Production data sources configured
Alert mechanisms set up (email, Slack, etc.)

Basic Usage:

# Batch detection mode with correlation analysis (default)
./detect_anomalies_pipeline.sh config/config.yaml

# Real-time detection mode
./detect_anomalies_pipeline.sh --mode realtime

# Continuous monitoring mode
./detect_anomalies_pipeline.sh --continuous --mode realtime

# With custom thresholds and correlation settings
./detect_anomalies_pipeline.sh --critical-threshold 0.95 --correlation-window 48 --min-correlation 0.4

# Without certain features
./detect_anomalies_pipeline.sh --no-agents --no-alerts --no-correlation

Typical Workflow Sequence
LR
    A[New Project] --> B[test_pipeline.sh]
    B --> C[Models Trained & Tested]
    C --> D[validation_pipeline.sh]
    D --> E[Models Validated with Correlation Support]
    E --> F[detect_anomalies_pipeline.sh]
    F --> G[Production Monitoring with Correlation]
    G --> H[Feedback Loop]
    H --> B

Development Phase: Run test_pipeline.sh to develop, train models, and test correlation capabilities
Validation Phase: Run validation_pipeline.sh to validate model performance and correlation support
Production Phase: Run detect_anomalies_pipeline.sh for actual anomaly detection with correlation analysis
Maintenance Phase: Monitor performance, analyze correlations, and retrain as needed

Architecture
System Architecture
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Data Sources      │     │   Data Sources      │     │   Data Sources      │
│  - Files            │     │  - Files            │     │  - Files            │
│  - Databases        │     │  - Databases        │     │  - Databases        │
│  - APIs             │     │  - APIs             │     │  - APIs             │
│  - Kafka Streams    │     │  - Kafka Streams    │     │  - Kafka Streams    │
└──────────┬──────────┘     └──────────┬──────────┘     └──────────┬──────────┘
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   TEST PIPELINE     │     │ VALIDATION PIPELINE │     │ DETECTION PIPELINE  │
├─────────────────────┤     ├─────────────────────┤     ├─────────────────────┤
│ 1. Data Collection  │     │ 1. Data Collection  │     │ 1. Data Collection  │
│ 2. Preprocessing    │     │ 2. Preprocessing    │     │ 2. Preprocessing    │
│ 3. Feature Eng.     │     │ 3. Model Loading    │     │ 3. Feature Eng.     │
│ 4. Data Splitting   │     │ 4. Model Validation │     │ 4. Model Loading    │
│ 5. Model Training   │     │ 5. Metrics Calc.    │     │ 5. Anomaly Detection│
│ 6. Evaluation       │     │ 6. Correlation Val. │     │ 6. Agent Analysis   │
│ 7. Correlation Test │     │ 7. Baseline Comp.   │     │ 7. Correlation Anal.│
│ 8. Model Export     │     │ 8. Report Gen.      │     │ 8. Alerting         │
│                     │     │ 9. Model Promotion  │     │ 9. Results Storage  │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
    storage/models/test/        storage/models/            storage/anomalies/
    reports/test/              validated/                  storage/correlations/
                               reports/validation/         storage/alerts/
                                                          reports/detection/
Directory Structure
anomaly-detection-system/
├── api_client.py                 # API client for interacting with ML server
├── api_services.py              # Enhanced API with correlation endpoints
├── config/
│   ├── config.yaml              # Default configuration
│   ├── test_config.yaml         # Test pipeline config
│   └── validation_config.yaml   # Validation pipeline config
├── data/
│   ├── input/                   # Production input data
│   ├── test/                    # Test datasets
│   ├── validation/              # Validation datasets
│   └── processed/               # Processed data
│       ├── test/
│       ├── validation/
│       └── detection/
├── storage/
│   ├── models/
│   │   ├── test/               # Models from test pipeline
│   │   ├── validated/          # Validated models with certificates
│   │   └── production/         # Production-ready models
│   ├── anomalies/              # Detected anomalies
│   ├── correlations/           # Correlation analysis results
│   └── alerts/                 # Alert records
├── reports/
│   ├── test/                   # Test pipeline reports
│   ├── validation/             # Validation reports
│   └── detection/              # Detection reports
├── logs/                       # Pipeline execution logs
├── test_pipeline.sh            # Test/training pipeline
├── validation_pipeline.sh      # Validation pipeline
└── detect_anomalies_pipeline.sh # Production detection pipeline

Pipeline Components
Component Details by Pipeline

Test Pipeline Components (test_pipeline.sh)
Stage 1-6: [Same as original]
Stage 7: Correlation Testing (NEW)

Creates synthetic correlated anomalies
Tests correlation detection capabilities
Validates correlation matrix generation
Reports correlation testing results

Stage 8: Model Export and Versioning

Exports trained models with correlation support metadata
Creates model inventory with feature capabilities
Timestamps all outputs

Validation Pipeline Components (validation_pipeline.sh)
Stage 1-5: [Same as original]
Stage 6: Correlation Validation (NEW)

Tests each model's correlation detection capability
Calculates correlation density metrics
Validates cross-correlation functionality
Adds correlation support to validation criteria

Stage 7-9: [Same as original, with correlation support considered]
Detection Pipeline Components (detect_anomalies_pipeline.sh)
Stage 1-6: [Same as original]
Stage 7: Correlation Analysis (NEW)

Analyzes correlations between detected anomalies
Generates correlation matrices for visualization
Identifies correlation clusters and patterns
Produces correlation statistics and reports
Configurable time windows and correlation thresholds

Stage 8: Alerting and Notification (Enhanced)

Includes correlation insights in alerts
Detects anomaly clusters
Warns about coordinated attacks or systemic issues
Prioritizes alerts based on correlation patterns

Stage 9: Results Storage and Reporting (Enhanced)

Saves correlation analysis results
Includes correlation statistics in reports
Archives correlation matrices for analysis

Continuous Monitoring Mode
When run with --continuous flag, the detection pipeline:

Monitors data/input/ for new files every 60 seconds
Processes only new files since last check
Performs incremental correlation analysis
Maintains correlation history
Runs indefinitely until stopped

Data Flow
Training Data Flow (Test Pipeline)
data/test/*.json
    │
    ▼
normalize-data API
    │
    ▼
extract-features API
    │
    ▼
train-model API
    │
    ▼
Correlation Testing
    │
    ▼
storage/models/test/

Validation Data Flow
data/validation/*.json
    │
    ▼
process-data API
    │
    ▼
detect-anomalies API
    │
    ▼
Correlation Validation
    │
    ▼
storage/models/validated/*_validation_cert.json

Detection Data Flow
data/input/* OR Real-time collectors
    │
    ▼
process-data API
    │
    ▼
detect-anomalies API
    │
    ├─> storage/anomalies/
    │
    ├─> Correlation Analysis
    │     └─> storage/correlations/
    │
    ├─> Agent Analysis
    │
    └─> Alert Generation
          └─> storage/alerts/

Correlation Analysis
Correlation Features

The enhanced pipeline system includes comprehensive correlation analysis:

Correlation Detection

Time-based correlations
Location-based correlations
IP address correlations
Score similarity correlations
Feature-based correlations


Correlation Metrics

Correlation scores (0-1)
Correlation density
Cluster identification
Pattern recognition


Correlation Visualization

Correlation matrices
Color-coded correlation strength
Top correlation pairs
Cluster visualization



Using Correlation Analysis

In Test Pipeline
# Test with correlation validation
./test_pipeline.sh

# Skip correlation testing if needed
./test_pipeline.sh --skip-correlation-test

In Validation Pipeline

# Validation includes correlation capability testing
./validation_pipeline.sh

# Models are evaluated for correlation support
# Check reports/validation/correlation_validation_*.json
In Detection Pipeline

# Enable correlation analysis (default)
./detect_anomalies_pipeline.sh

# Configure correlation parameters
./detect_anomalies_pipeline.sh \
  --correlation-window 48 \      # 48-hour window
  --min-correlation 0.4 \        # Min correlation score
  --max-correlation-results 100  # Max results per anomaly

# Disable correlation if needed
./detect_anomalies_pipeline.sh --no-correlation
Correlation API Commands

# Get correlations for specific anomaly
python api_client.py get-correlations <anomaly_id> \
  --time-window 24 --min-score 0.3

# Bulk correlation analysis
python api_client.py bulk-correlate <id1> <id2> <id3> \
  --cross-correlate

# Generate correlation matrix
python api_client.py correlation-matrix <id1> <id2> ... <id10>

# Get correlation statistics
python api_client.py correlation-stats \
  --time-window 24 --min-score 0.3

Correlation Reports
Correlation analysis generates several reports:

Correlation Report (storage/correlations/correlation_*.json)

Detailed correlations for each anomaly
Correlation scores and reasons
Top correlated anomalies


Correlation Matrix (storage/correlations/correlation_matrix_*.json)

Pairwise correlation scores
Visual matrix representation
Anomaly metadata


Correlation Statistics (storage/correlations/correlation_stats_*.json)

Overall correlation metrics
Correlation type distribution
High correlation pairs



Feature Engineering
Feature Types by Pipeline
Test Pipeline Features

Base features: Direct from raw data
Statistical features: Mean, std, min, max
Time-based features: If timestamps present
Domain features: Based on data type
Correlation-friendly features: IP addresses, locations, timestamps

Detection Pipeline Features

All test pipeline features PLUS:
Hour of day: For temporal correlation patterns
Day of week: For weekly correlation patterns
Is weekend: For weekend vs weekday patterns
Feature statistics: For feature-based correlations
Real-time features: Computed on streaming data

Feature Processing Commands

# In test pipeline
python api_client.py extract-features normalized_data.json > features_data.json

# In detection pipeline (includes normalization)
python api_client.py process-data raw_data.json > processed_data.json
Model Management
Model Lifecycle with Correlation Support

Development (test_pipeline.sh)

Models created and trained
Correlation capabilities tested
Saved to storage/models/test/
Status: "experimental"


Validation (validation_pipeline.sh)

Models tested on holdout data
Correlation support validated
Validation certificates include correlation metrics
Saved to storage/models/validated/
Status: "validated"


Production (detect_anomalies_pipeline.sh)

Models loaded from validated storage
Active anomaly detection with correlation
Performance and correlation patterns monitored
Status: "production"



Model Selection Criteria
Test Pipeline: Trains ALL configured models

Models tested for correlation support
Correlation testing results included in reports

Validation Pipeline: Validates correlation capabilities

Models with poor correlation support flagged
Correlation density used as validation metric

Detection Pipeline: Prefers models with correlation support

Ensemble includes correlation-capable models
Single model selection considers correlation support

Deployment Strategy
Development to Production Flow
Development Setup
bash# Start API server with correlation features
python api_services.py --config config/config.yaml --auto-init

# Run test pipeline with correlation testing
./test_pipeline.sh

# Check correlation test results
cat reports/test/correlation_test_*.txt
Validation Setup

# Prepare validation data
cp production_sample.json data/validation/

# Run validation with correlation validation
./validation_pipeline.sh --min-precision 0.8

# Check correlation validation results
cat reports/validation/correlation_validation_*.json
Production Deployment

# Configure production settings
export ENABLE_ALERTS=true
export ENABLE_AGENTS=true
export ENABLE_CORRELATION=true
export CORRELATION_TIME_WINDOW=24
export MIN_CORRELATION_SCORE=0.3

# Start detection with correlation
./detect_anomalies_pipeline.sh --continuous
Scaling Configurations
Batch Processing with Correlation:

# Process large datasets with correlation analysis
./detect_anomalies_pipeline.sh --mode batch --correlation-window 48
Real-time Processing with Correlation:

# Enable all collectors with correlation
./detect_anomalies_pipeline.sh --mode realtime --min-correlation 0.4
High-Performance Setup:

# Optimize for performance
./detect_anomalies_pipeline.sh \
  --no-agents \
  --correlation-window 12 \  # Smaller window
  --max-correlation-results 20  # Fewer results

Monitoring and Maintenance
Pipeline Monitoring
Test Pipeline Monitoring:

# Monitor correlation testing
grep "Correlation Testing" logs/test_pipeline_*.log

# Check correlation test results
tail -f logs/test_pipeline_*.log | grep "correlation"
Validation Pipeline Monitoring:

# Check correlation validation progress
grep "correlation" logs/validation_pipeline_*.log

# View correlation metrics
cat reports/validation/correlation_validation_*.json | jq
Detection Pipeline Monitoring:

# Monitor correlation analysis
tail -f logs/detect_pipeline_*.log | grep "Correlation"

# Check correlation alerts
grep "CORRELATION ALERT" logs/detect_pipeline_*.log

# Monitor correlation patterns
watch -n 10 'ls storage/correlations/ | wc -l'
Maintenance Schedule

Daily Tasks:
# Review correlation patterns
python analyze_correlations.py --last 24h

# Check for anomaly clusters
grep "correlation clusters" storage/alerts/alert_*.txt

# Monitor correlation performance
python api_client.py correlation-stats --time-window 24
Weekly Tasks:

# Analyze correlation trends
python correlation_trends.py --days 7

# Archive correlation data
tar -czf correlations_week_$(date +%Y%W).tar.gz storage/correlations/

# Review correlation effectiveness
./generate_correlation_report.sh --weekly
Monthly Tasks:

# Retrain with correlation feedback
./test_pipeline.sh --include-correlation-feedback

# Update correlation thresholds based on analysis
vim config/config.yaml  # Update correlation settings

# Full correlation analysis report
python generate_monthly_correlation_report.py
Best Practices
Correlation Analysis Best Practices

Configuration:

Start with 24-hour correlation windows
Use 0.3 as minimum correlation score
Limit results to top 50 correlations per anomaly


Performance:

Enable correlation for high/critical anomalies only
Use smaller time windows for real-time systems
Archive old correlation data regularly


Analysis:

Review correlation clusters daily
Investigate high correlation patterns
Use correlation insights for root cause analysis



Pipeline Best Practices

Data Preparation:

Include correlation-friendly fields (IPs, locations, timestamps)
Maintain consistent data formats
Preserve metadata for correlation analysis


Pipeline Execution:

Always test correlation capabilities in test pipeline
Validate correlation support before production
Monitor correlation performance in production


Alert Management:

Prioritize alerts with high correlations
Investigate correlation clusters immediately
Use correlation patterns for incident response



Configuration Examples
Test Configuration with Correlation:

# config/test_config.yaml
pipeline:
  type: test
  correlation_testing:
    enabled: true
    synthetic_clusters: 3
    anomalies_per_cluster: 5
  models:
    - isolation_forest
    - statistical
    - autoencoder

Production Configuration with Correlation:

# config/config.yaml
pipeline:
  type: detection
  correlation:
    enabled: true
    time_window_hours: 24
    min_correlation_score: 0.3
    max_results: 50
  thresholds:
    critical: 0.9
    high: 0.8

Troubleshooting
Common Correlation Issues
Issue: "No correlations found"

# Solution: Check time window and threshold
python api_client.py correlation-stats --time-window 48 --min-score 0.2

# Verify anomalies have required fields
python api_client.py list-anomalies --limit 10 | jq '.[] | {id, src_ip, location, timestamp}'
Issue: "Correlation analysis slow"

# Solution: Reduce correlation window
./detect_anomalies_pipeline.sh --correlation-window 12

# Limit correlation results
./detect_anomalies_pipeline.sh --max-correlation-results 20
Issue: "Too many false correlation alerts"

# Solution: Increase correlation threshold
./detect_anomalies_pipeline.sh --min-correlation 0.5

# Require multiple correlation reasons
# Edit correlation logic in api_services.py
Debug Commands

# Test correlation API
python api_client.py store-anomalies test_anomalies.json
python api_client.py correlation-stats

# Check correlation between specific anomalies
python api_client.py get-correlations <anomaly_id>

# Generate test correlation matrix
ids=$(python api_client.py list-anomalies --limit 5 | jq -r '.[].id' | tr '\n' ' ')
python api_client.py correlation-matrix $ids

# Monitor correlation performance
time python api_client.py bulk-correlate $ids --cross-correlate
Log Analysis

# Find correlation errors
grep -E "correlation.*error|failed.*correlation" logs/*.log

# Check correlation performance
grep "Correlation analysis completed" logs/detect_pipeline*.log | tail -10

# Analyze correlation patterns
grep -A5 "Correlation Types:" logs/detect_pipeline*.log

# Monitor correlation alerts
grep -B2 -A2 "CORRELATION ALERT" logs/*.log

Conclusion
The enhanced pipeline system with correlation analysis provides:

Test Pipeline with correlation capability testing
Validation Pipeline with correlation support validation
Detection Pipeline with real-time correlation analysis

The correlation features enable:

Pattern detection across anomalies
Root cause analysis through correlation clusters
Improved alert prioritization
Better incident response

By leveraging correlation analysis, teams can:

Detect coordinated attacks
Identify systemic issues
Reduce false positives through pattern validation
Improve anomaly investigation efficiency

For additional support:

Check correlation reports in storage/correlations/
Use correlation API endpoints for custom analysis
Monitor correlation metrics in pipeline logs
Refer to api_services.py for correlation implementation details