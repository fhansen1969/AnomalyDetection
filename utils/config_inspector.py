"""
Quick config structure inspector to understand your config.yaml layout.
"""

import yaml
import json
from pathlib import Path

def inspect_structure(obj, indent=0, max_depth=4):
    """Recursively inspect and display structure."""
    prefix = "  " * indent
    
    if indent > max_depth:
        print(f"{prefix}... (max depth reached)")
        return
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, dict):
                print(f"{prefix}{key}: {{dict with {len(value)} keys}}")
                # Show first few keys
                if len(value) <= 3:
                    inspect_structure(value, indent + 1, max_depth)
                else:
                    # Just show keys
                    sample_keys = list(value.keys())[:5]
                    print(f"{prefix}  Keys: {', '.join(sample_keys)}...")
            elif isinstance(value, list):
                print(f"{prefix}{key}: [list with {len(value)} items]")
                if value and len(value) <= 3:
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            print(f"{prefix}  [{i}]: {{dict with {len(item)} keys}}")
                            if 'name' in item:
                                print(f"{prefix}      name: {item['name']}")
                            if 'config' in item:
                                print(f"{prefix}      config: {{...}}")
                        else:
                            print(f"{prefix}  [{i}]: {type(item).__name__}")
            else:
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:50] + "..."
                print(f"{prefix}{key}: {type(value).__name__} = {value_str}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:3]):  # Show first 3 items
            print(f"{prefix}[{i}]: {type(item).__name__}")
            if isinstance(item, (dict, list)):
                inspect_structure(item, indent + 1, max_depth)
    else:
        print(f"{prefix}{type(obj).__name__}: {str(obj)[:50]}")

def main():
    config_paths = [
        "config.yaml",
        "config/config.yaml",
        "configs/config.yaml",
        Path.cwd() / "config.yaml"
    ]
    
    config = None
    config_path = None
    
    for path in config_paths:
        if Path(path).exists():
            config_path = path
            print(f"Found config at: {path}\n")
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            break
    
    if not config:
        print("❌ Could not find config.yaml")
        print("Searched:")
        for path in config_paths:
            print(f"  - {path}")
        return
    
    print("="*70)
    print("CONFIG STRUCTURE INSPECTION")
    print("="*70)
    print()
    
    # Top level overview
    print("Top-level keys:")
    for key in config.keys():
        print(f"  - {key}")
    print()
    
    # Inspect processors section
    if 'processors' in config:
        print("="*70)
        print("PROCESSORS SECTION")
        print("="*70)
        print()
        inspect_structure(config['processors'], indent=0, max_depth=3)
        print()
    
    # Look for feature extractors
    print("="*70)
    print("FEATURE EXTRACTOR SEARCH")
    print("="*70)
    print()
    
    found_extractors = []
    
    # Search pattern 1: processors.feature_extractors
    if 'processors' in config and 'feature_extractors' in config['processors']:
        path = "config['processors']['feature_extractors']"
        extractors = config['processors']['feature_extractors']
        print(f"✓ Found at: {path}")
        print(f"  Count: {len(extractors)}")
        for i, ext in enumerate(extractors):
            if isinstance(ext, dict):
                name = ext.get('name', f'extractor_{i}')
                print(f"  [{i}] name: {name}")
                if 'config' in ext:
                    conf = ext['config']
                    num_fields = len(conf.get('numerical_fields', []))
                    cat_fields = len(conf.get('categorical_fields', []))
                    bool_fields = len(conf.get('boolean_fields', []))
                    print(f"      Fields: {num_fields} numerical, {cat_fields} categorical, {bool_fields} boolean")
        found_extractors.append(path)
        print()
    
    # Search pattern 2: feature_extractors (top level)
    if 'feature_extractors' in config:
        path = "config['feature_extractors']"
        print(f"✓ Found at: {path}")
        found_extractors.append(path)
        print()
    
    # Search pattern 3: processors.feature_extractor (singular)
    if 'processors' in config and 'feature_extractor' in config['processors']:
        path = "config['processors']['feature_extractor']"
        print(f"✓ Found at: {path}")
        found_extractors.append(path)
        print()
    
    if not found_extractors:
        print("❌ No feature extractors found in config!")
        print()
        print("Expected locations:")
        print("  - config['processors']['feature_extractors']")
        print("  - config['feature_extractors']")
        print()
    
    # Models section
    if 'models' in config:
        print("="*70)
        print("MODELS SECTION")
        print("="*70)
        print()
        models = config['models']
        if 'enabled' in models:
            print(f"Enabled models: {', '.join(models['enabled'])}")
        print()
    
    # Agents section
    if 'agents' in config:
        print("="*70)
        print("AGENTS SECTION")
        print("="*70)
        print()
        agents = config['agents']
        print(f"Agents enabled: {agents.get('enabled', False)}")
        if 'llm' in agents:
            llm = agents['llm']
            print(f"LLM provider: {llm.get('provider', 'not set')}")
            print(f"LLM model: {llm.get('model', 'not set')}")
        print()
    
    # Save full structure to JSON for inspection
    output_file = "config_structure.json"
    def make_serializable(obj):
        """Convert config to serializable format."""
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)
    
    try:
        with open(output_file, 'w') as f:
            json.dump(make_serializable(config), f, indent=2)
        print(f"✓ Full config structure saved to: {output_file}")
    except Exception as e:
        print(f"✗ Could not save config structure: {e}")
    
    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print()
    print(f"Config file: {config_path}")
    print(f"Top-level sections: {len(config)}")
    print(f"Feature extractors found: {len(found_extractors)}")
    
    if found_extractors:
        print(f"\nTo access feature extractor config in your code:")
        for path in found_extractors:
            print(f"  {path}[0]['config']")
    
    print()

if __name__ == "__main__":
    main()
