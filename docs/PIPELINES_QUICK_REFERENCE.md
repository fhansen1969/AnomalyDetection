# Pipelines Quick Reference

## Pipeline Scripts Summary

| Script | Purpose | Key Stages | Output Location |
|--------|---------|------------|-----------------|
| `run_pipelines.sh` | Master orchestrator | Coordinates all pipelines | `reports/master_pipeline/` |
| `training_pipeline.sh` | Model training | 7 stages: Collection → Preprocessing → Features → Splitting → Training → Export → Report | `storage/models/`, `reports/training/` |
| `test_pipeline.sh` | Model evaluation | 5 stages: Data Prep → Evaluation → Correlation → Performance → Report | `reports/test/` |
| `validation_pipeline.sh` | Model validation | 9 stages: Collection → Preprocessing → Loading → Validation → Metrics → Correlation → Baseline → Report → Promotion | `storage/models/validated/`, `reports/validation/` |
| `detect_anomalies_pipeline.sh` | Production detection | 8 stages: Load Models → Collection → Features → Detection → Agents → Correlation → Alerts → Report | `storage/anomalies/`, `storage/correlations/`, `storage/alerts/` |

**Note:** Data generation is handled automatically by each pipeline using `api_client.py generate-data` when data is missing.

## Quick Commands

### Full Workflow
```bash
# Run all pipelines in sequence
bash pipelines/run_pipelines.sh
```

### Individual Pipelines
```bash
# Training
bash pipelines/training_pipeline.sh config/config.yaml

# Testing
bash pipelines/test_pipeline.sh config/config.yaml

# Validation
bash pipelines/validation_pipeline.sh config/validation_config.yaml

# Detection
bash pipelines/detect_anomalies_pipeline.sh config/config.yaml

# Manual Data Generation (if needed)
python api_client.py generate-data --output data/training/training_data.json --count 2000 --anomaly-ratio 0.3
```

### Common Options
```bash
# Skip stages
SKIP_PREPROCESSING=true bash pipelines/training_pipeline.sh

# Custom thresholds
MIN_PRECISION=0.8 MIN_RECALL=0.7 bash pipelines/validation_pipeline.sh

# Continuous monitoring
CONTINUOUS_MODE=true bash pipelines/detect_anomalies_pipeline.sh

# Disable features
ENABLE_AGENTS=false ENABLE_CORRELATION=false bash pipelines/detect_anomalies_pipeline.sh
```

## Data Flow

```
(Data Generation - Automatic)
    ↓
data/training/ → training_pipeline.sh → storage/models/
    ↓
data/test/ → test_pipeline.sh → reports/test/
    ↓
data/validation/ → validation_pipeline.sh → storage/models/validated/
    ↓
data/input/ → detect_anomalies_pipeline.sh → storage/anomalies/
```

## Key Fixes Applied

✅ Metadata files (`*_metadata.json`) are now skipped in all pipelines
✅ Models saved to central `storage/models/` directory
✅ Improved model status detection
✅ Better error handling and logging
