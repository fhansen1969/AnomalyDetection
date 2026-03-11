# train_all_models.py
import json
import os
import sys
from api_client import AnomalyDetectionClient

def load_and_prepare_data(filepath):
    """Load data in any format and prepare for training."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    records = []
    
    # Handle different formats
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # Check for nested data
        for key in ['data', 'records', 'items', 'anomalies']:
            if key in data and isinstance(data[key], list):
                records = data[key]
                break
        
        # If no nested list found, convert dict entries
        if not records:
            for k, v in data.items():
                if isinstance(v, dict):
                    record = {"id": k, **v}
                else:
                    record = {"id": k, "value": v}
                records.append(record)
    
    # Extract features from each record
    processed_records = []
    for record in records:
        features = []
        
        # Extract all numeric values as features
        def extract_numbers(obj, features_list):
            if isinstance(obj, dict):
                for v in obj.values():
                    extract_numbers(v, features_list)
            elif isinstance(obj, list):
                for item in obj:
                    extract_numbers(item, features_list)
            elif isinstance(obj, (int, float)):
                features_list.append(float(obj))
        
        extract_numbers(record, features)
        
        if features:
            processed_records.append({
                "features": features,
                "original_data": record
            })
    
    return processed_records

def main():
    # Initialize client
    client = AnomalyDetectionClient("http://localhost:8000")
    
    # Load all training data
    all_training_data = []
    data_files = [
        "data/validation/network_traffic_analyze.json",
        "data/validation/sw_analyze.json",
        "data/validation/av_analyze.json",
        "data/validation/s1_analyze.json",
        "data/validation/tn_analyze.json"
    ]
    
    print("Loading training data...")
    for filepath in data_files:
        if os.path.exists(filepath):
            print(f"\nProcessing {filepath}...")
            try:
                data = load_and_prepare_data(filepath)
                all_training_data.extend(data)
                print(f"  ✓ Added {len(data)} records")
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
    
    print(f"\n{'='*50}")
    print(f"Total training records: {len(all_training_data)}")
    
    if not all_training_data:
        print("No training data available!")
        return
    
    # Get list of models
    models = client.list_models()
    
    # Train each model
    print(f"\n{'='*50}")
    print("Training models...")
    
    successful_models = []
    failed_models = []
    
    for model in models:
        model_name = model['name']
        model_status = model['status']
        
        if model_status == 'trained':
            print(f"\n✓ {model_name} is already trained, skipping...")
            successful_models.append(model_name)
            continue
        
        print(f"\nTraining {model_name}...")
        
        try:
            # Start training job
            job = client.train_model(model_name, all_training_data)
            job_id = job['job_id']
            print(f"  Job ID: {job_id}")
            
            # Wait for completion with progress updates
            final_status = client.wait_for_job(job_id, timeout=600)
            
            if final_status['status'] == 'completed':
                result = final_status.get('result', {})
                training_time = result.get('training_time', 'N/A')
                print(f"  ✓ Training completed in {training_time}")
                successful_models.append(model_name)
            else:
                error = final_status.get('result', {}).get('error', 'Unknown error')
                print(f"  ✗ Training failed: {error}")
                failed_models.append((model_name, error))
                
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            failed_models.append((model_name, str(e)))
    
    # Summary
    print(f"\n{'='*50}")
    print("TRAINING SUMMARY")
    print(f"{'='*50}")
    print(f"Successfully trained: {len(successful_models)} models")
    if successful_models:
        for model in successful_models:
            print(f"  ✓ {model}")
    
    if failed_models:
        print(f"\nFailed to train: {len(failed_models)} models")
        for model, error in failed_models:
            print(f"  ✗ {model}: {error}")
    
    # Check final model status
    print(f"\n{'='*50}")
    print("FINAL MODEL STATUS")
    print(f"{'='*50}")
    
    models = client.list_models()
    for model in models:
        print(f"{model['name']}: {model['status']}")
    
    return successful_models

if __name__ == "__main__":
    successful = main()
    if successful:
        print(f"\n{'='*50}")
        print("✓ Models are now ready for validation!")
        print("Run: ./validation_pipeline.sh config/config.yaml")
    else:
        print("\n⚠ No models were successfully trained.")
        sys.exit(1)
