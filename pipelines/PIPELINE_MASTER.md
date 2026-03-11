# Master Pipeline Runner - Documentation

## Overview

The `run_master_pipeline.sh` script is a robust orchestrator for the complete anomaly detection pipeline workflow. It provides comprehensive control over pipeline execution, cleanup behavior, error handling, and reporting.

## Features

### ✨ Key Improvements Over Original Script

1. **Comprehensive Error Handling**
   - Validates prerequisites before starting
   - Checks for required files and running services
   - Can continue or stop on errors

2. **Flexible Cleanup Control**
   - Individual cleanup flags for each pipeline
   - Global cleanup override options
   - Clear logging of cleanup behavior

3. **Stage Timing & Reporting**
   - Tracks duration of each stage
   - Generates detailed summary reports
   - Color-coded console output

4. **Selective Stage Execution**
   - Skip any stage with `--skip-*` flags
   - Run only specific stages with `--only-*` flags
   - Perfect for debugging and iterative development

5. **Better Logging**
   - Timestamped log entries
   - Separate master log file
   - Preserves individual pipeline logs

6. **Configuration Management**
   - Centralized configuration file support
   - Command-line parameter overrides
   - Validation of configuration

## Installation

```bash
# Make the script executable
chmod +x run_master_pipeline.sh

# Place in your project root or pipelines directory
cp run_master_pipeline.sh /path/to/your/project/
```

## Basic Usage

### Run Full Pipeline (Default)
```bash
./run_master_pipeline.sh
```

This runs all stages with default cleanup enabled:
1. ⏭️  Data Generation (skipped by default)
2. ✅ Model Training (with cleanup)
3. ✅ Model Testing (with cleanup)
4. ✅ Model Validation (with cleanup)
5. ✅ Anomaly Detection (no cleanup by design)
6. ✅ Results Verification

### Run Without Cleanup (Debugging)
```bash
./run_master_pipeline.sh --no-cleanup-all
```

Perfect for debugging when you want to inspect all generated anomalies.

### Skip Stages
```bash
# Skip data generation and validation
./run_master_pipeline.sh --skip-data-generation --skip-validation

# Skip everything except training
./run_master_pipeline.sh --only-training
```

## Command-Line Options

### Stage Control

#### Skip Stages
```bash
--skip-data-generation      # Skip data generation
--skip-training            # Skip training
--skip-testing             # Skip testing
--skip-validation          # Skip validation
--skip-detection           # Skip detection
--skip-results-check       # Skip results check
```

#### Run Only Specific Stage
```bash
--only-training            # Run only training
--only-testing             # Run only testing
--only-validation          # Run only validation
--only-detection           # Run only detection
```

### Cleanup Control

#### Global Cleanup Override
```bash
--cleanup-all              # Enable cleanup for ALL stages
--no-cleanup-all           # Disable cleanup for ALL stages
```

#### Individual Cleanup Control
```bash
# Training cleanup
--cleanup-training         # Enable (default)
--no-cleanup-training      # Disable

# Testing cleanup
--cleanup-testing          # Enable (default)
--no-cleanup-testing       # Disable

# Validation cleanup
--cleanup-validation       # Enable (default)
--no-cleanup-validation    # Disable
```

**Note:** Detection pipeline never cleans up (production anomalies should be preserved).

### Data Generation Options
```bash
--generate-data            # Enable data generation
--training-records 5000    # Number of training records
--anomaly-ratio 0.3        # Anomaly ratio (0-1)
```

### Validation Parameters
```bash
--correlation-window 12    # Correlation time window (hours)
--min-correlation 0.7      # Minimum correlation score
```

### Error Handling
```bash
--continue-on-error        # Continue even if stages fail
--stop-on-first-error      # Stop on first failure (default)
```

### Configuration
```bash
--config path/to/config.yaml    # Custom config file
```

## Common Use Cases

### 1. Development & Debugging

#### Debug Training Issues
```bash
# Run only training, keep anomalies for inspection
./run_master_pipeline.sh --only-training --no-cleanup-training
```

#### Debug Full Pipeline, Keep All Data
```bash
# Run full pipeline without cleanup
./run_master_pipeline.sh --no-cleanup-all
```

#### Re-run Failed Stage
```bash
# If testing failed, skip successful stages
./run_master_pipeline.sh --skip-training --skip-validation
```

### 2. Production Workflows

#### Standard Development Cycle
```bash
# Generate data, train, test, validate (with cleanup)
./run_master_pipeline.sh --generate-data --training-records 10000
```

#### Quick Validation Check
```bash
# Only validate existing models
./run_master_pipeline.sh --only-validation
```

#### Production Detection Run
```bash
# Skip training/testing, only run detection
./run_master_pipeline.sh --skip-training --skip-testing --skip-validation
```

### 3. Continuous Integration

#### CI Pipeline
```bash
# Continue on error to collect all results
./run_master_pipeline.sh --continue-on-error --cleanup-all
```

#### Automated Testing
```bash
# Generate consistent test data
./run_master_pipeline.sh \
  --generate-data \
  --training-records 1000 \
  --anomaly-ratio 0.2 \
  --cleanup-all
```

### 4. Experimentation

#### Test Different Correlation Parameters
```bash
# Run validation with different parameters
./run_master_pipeline.sh \
  --only-validation \
  --correlation-window 24 \
  --min-correlation 0.8 \
  --no-cleanup-validation
```

#### Compare Cleanup vs No Cleanup
```bash
# Run 1: With cleanup
./run_master_pipeline.sh

# Run 2: Without cleanup
./run_master_pipeline.sh --no-cleanup-all

# Compare database sizes
```

## Understanding Cleanup Behavior

### Default Behavior

| Pipeline | Cleanup Enabled | Reason |
|----------|----------------|--------|
| Training | ✅ Yes | Training anomalies are for model development |
| Testing | ✅ Yes | Test anomalies are for evaluation |
| Validation | ✅ Yes | Validation anomalies are temporary |
| Detection | ❌ No | Production anomalies need investigation |

### How Cleanup Works

1. **Before Pipeline:** Records baseline anomaly count
2. **During Pipeline:** New anomalies are created
3. **After Pipeline:** Removes only newly created anomalies
4. **Result:** Database returns to baseline state

**Example:**
```
Database has 100 anomalies
│
├─ Run training pipeline (creates 50 anomalies)
│  Database: 100 → 150
│
├─ Training cleanup runs
│  Database: 150 → 100 (removes 50)
│
└─ Back to baseline: 100 anomalies
```

### When to Disable Cleanup

✅ **Use `--no-cleanup-*` when:**
- Debugging anomaly detection
- Analyzing false positives/negatives
- Comparing anomalies across runs
- Performance benchmarking
- Development and experimentation

❌ **Keep cleanup enabled for:**
- Regular development workflow
- Continuous integration
- Automated testing
- Production-like testing

## Output and Reports

### Console Output

The script provides color-coded, real-time feedback:

```
========================================
STAGE: Model Training
========================================
[INFO] Starting model training pipeline...
[INFO]   Config: config/config.yaml
[INFO]   Cleanup: --cleanup-anomalies
[SUCCESS] Training pipeline completed
[✓] Training completed in 45s

========================================
STAGE: Model Testing
========================================
...
```

### Summary Report

After execution, a detailed Markdown report is generated:

**Location:** `reports/master_pipeline/master_run_YYYYMMDD_HHMMSS.md`

**Contents:**
- Execution summary (success/fail counts)
- Configuration used
- Stage-by-stage results table
- Duration for each stage
- Log file locations
- Next steps and recommendations

**Example:**
```markdown
# Master Pipeline Execution Report

**Generated:** 2025-11-03 12:00:00
**Total Duration:** 240s (4m 0s)

## Summary
- Total Stages: 6
- Successful: 5 ✅
- Failed: 1 ❌
- Skipped: 0 ⏭️

## Stage Results
| Stage | Status | Duration |
|-------|--------|----------|
| Training | ✅ SUCCESS | 45s |
| Testing | ✅ SUCCESS | 38s |
| Validation | ❌ FAILED | 12s |
...
```

### Log Files

**Master Log:** `logs/master_pipeline/master_pipeline_YYYYMMDD_HHMMSS.log`
- Contains all output from master script
- Includes pipeline stdout/stderr

**Individual Pipeline Logs:**
- `logs/training_pipeline_*.log`
- `logs/test_pipeline_*.log`
- `logs/validation_pipeline_*.log`
- `logs/detect_pipeline_*.log`

## Troubleshooting

### Issue: Prerequisites Check Fails

**Problem:** API server not responding

**Solution:**
```bash
# Start the API server
python api_services.py &

# Wait a moment for it to start
sleep 5

# Run pipeline
./run_master_pipeline.sh
```

### Issue: Pipeline Files Not Found

**Problem:** "Pipeline directory not found"

**Solution:**
```bash
# Run from project root
cd /path/to/project/root
./run_master_pipeline.sh

# Or use absolute path
/path/to/project/run_master_pipeline.sh
```

### Issue: Stage Fails, Want to Continue

**Problem:** One stage fails, need to see all results

**Solution:**
```bash
# Continue on error
./run_master_pipeline.sh --continue-on-error
```

### Issue: Cleanup Not Working

**Problem:** Anomalies not being cleaned up

**Diagnosis:**
1. Check if cleanup is enabled:
   ```bash
   grep "Cleanup:" logs/master_pipeline/*.log
   ```

2. Check individual pipeline logs:
   ```bash
   grep -i "cleanup" logs/*_pipeline_*.log
   ```

3. Verify database connection:
   ```bash
   python api_client.py health
   ```

**Solution:**
- Ensure cleanup flags are set correctly
- Check database connectivity
- Review individual pipeline logs for errors

### Issue: Want to See More Detail

**Problem:** Need more information about what happened

**Solution:**
```bash
# View master log
tail -f logs/master_pipeline/master_pipeline_*.log

# View specific pipeline log
tail -f logs/training_pipeline_*.log

# View summary report
cat reports/master_pipeline/master_run_*.md
```

## Integration with CI/CD

### Jenkins Example
```groovy
pipeline {
    stages {
        stage('Run Pipeline') {
            steps {
                sh '''
                    ./run_master_pipeline.sh \
                        --continue-on-error \
                        --cleanup-all \
                        --config config/ci_config.yaml
                '''
            }
        }
        stage('Archive Results') {
            steps {
                archiveArtifacts artifacts: 'reports/**/*.md'
                archiveArtifacts artifacts: 'logs/**/*.log'
            }
        }
    }
}
```

### GitHub Actions Example
```yaml
name: Anomaly Detection Pipeline

on: [push]

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Start API Server
        run: python api_services.py &
        
      - name: Run Master Pipeline
        run: |
          chmod +x run_master_pipeline.sh
          ./run_master_pipeline.sh \
            --continue-on-error \
            --cleanup-all
            
      - name: Upload Reports
        uses: actions/upload-artifact@v2
        with:
          name: pipeline-reports
          path: reports/
```

## Best Practices

### 1. Development
```bash
# Quick iteration during development
./run_master_pipeline.sh \
  --only-training \
  --no-cleanup-training

# Full test with cleanup
./run_master_pipeline.sh --cleanup-all
```

### 2. Testing
```bash
# Automated testing with consistent data
./run_master_pipeline.sh \
  --generate-data \
  --training-records 1000 \
  --cleanup-all \
  --continue-on-error
```

### 3. Production Validation
```bash
# Validate before production deployment
./run_master_pipeline.sh \
  --skip-detection \
  --correlation-window 24 \
  --min-correlation 0.8
```

### 4. Emergency Debugging
```bash
# Investigate production issues
./run_master_pipeline.sh \
  --only-detection \
  --continue-on-error
```

## Performance Tips

1. **Skip Unnecessary Stages**
   - Use `--skip-*` flags to avoid re-running successful stages
   - Saves time during iterative development

2. **Use Cleanup**
   - Keep cleanup enabled to maintain database performance
   - Only disable when actively debugging

3. **Parallel Execution**
   - Run independent stages in parallel (advanced)
   - Requires custom orchestration

4. **Resource Management**
   - Monitor system resources during execution
   - Adjust training records and batch sizes accordingly

## Migration from Original Script

### Old Script
```bash
#!/bin/sh
pipelines/training_pipeline.sh config/config.yaml                                
pipelines/test_pipeline.sh config/config.yaml                                  
pipelines/validate_pipeline.sh --correlation-window 6 --min-correlation 0.5                              
pipelines/detect_anomalies_pipeline.sh config/config.yaml
# Results checking functionality integrated into run_pipelines.sh
```

### New Script (Equivalent)
```bash
./run_master_pipeline.sh \
  --config config/config.yaml \
  --correlation-window 6 \
  --min-correlation 0.5
```

### Migration Checklist

- ✅ Replace `#!/bin/sh` with robust bash script
- ✅ Add error handling
- ✅ Add cleanup control
- ✅ Add logging and reporting
- ✅ Add stage skipping capability
- ✅ Add prerequisites validation
- ✅ Add timing information
- ✅ Add color-coded output
- ✅ Add comprehensive help

## Advanced Usage

### Custom Pipeline Order
If you need a custom execution order, modify the `main()` function or use selective execution:

```bash
# Custom order: validation → testing → detection
./run_master_pipeline.sh --only-validation
./run_master_pipeline.sh --only-testing
./run_master_pipeline.sh --only-detection
```

### Environment Variables
You can set defaults using environment variables:

```bash
export CONFIG_FILE="config/production.yaml"
export CLEANUP_ALL="false"
./run_master_pipeline.sh
```

### Scheduled Execution
```bash
# Add to crontab for daily execution
0 2 * * * cd /path/to/project && ./run_master_pipeline.sh --cleanup-all >> logs/cron.log 2>&1
```

## Summary

The improved master pipeline script provides:

✅ **Robustness:** Error handling, validation, and recovery  
✅ **Flexibility:** Skip stages, control cleanup, customize parameters  
✅ **Visibility:** Detailed logging, reporting, and color output  
✅ **Control:** Fine-grained cleanup and execution options  
✅ **Integration:** CI/CD ready with proper exit codes  
✅ **Documentation:** Comprehensive help and examples  

