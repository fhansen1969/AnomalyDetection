"""
Concrete FeatureExtractor implementation for the API services.
Extracted from api_services.py lines 46-247.
"""
import logging
from datetime import datetime
from typing import Dict, List, Any

import numpy as np


class ConcreteFeatureExtractor:
    """
    Concrete implementation of FeatureExtractor for the API services.
    FIXED VERSION with proper field type handling.
    """
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        self.name = name
        self.config = config
        self.storage_manager = storage_manager
        self.logger = logging.getLogger(f"concrete_extractor_{name}")

        self.fields = config.get('fields', ['*'])
        self.numerical_fields = set(config.get('numerical_fields', []))
        self.categorical_fields = set(config.get('categorical_fields', []))
        self.boolean_fields = set(config.get('boolean_fields', []))
        self.text_fields = set(config.get('text_fields', []))

        self.all_configured_fields = (
            self.numerical_fields |
            self.categorical_fields |
            self.boolean_fields |
            self.text_fields
        )

        self.categorical_encoding = config.get('categorical_encoding', 'one_hot')
        self.categorical_values = {}
        self.categorical_mappings = {}

        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()

        self.logger.info(f"Initialized ConcreteFeatureExtractor with {len(self.all_configured_fields)} configured fields")

    def _get_field_value(self, item: Dict[str, Any], field_name: str) -> Any:
        """Get field value supporting nested fields."""
        if '.' in field_name:
            parts = field_name.split('.')
            current = item
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current
        return item.get(field_name)

    def _collect_categorical_values(self, data: List[Dict[str, Any]]):
        """Collect unique categorical values for encoding."""
        for item in data:
            records = item.get('raw_data', [item])
            if not isinstance(records, list):
                records = [records]

            for record in records:
                for field in self.categorical_fields:
                    value = self._get_field_value(record, field)
                    if value is not None and isinstance(value, str):
                        if field not in self.categorical_values:
                            self.categorical_values[field] = set()
                        self.categorical_values[field].add(value)

        for field, values in self.categorical_values.items():
            sorted_values = sorted(values)
            self.categorical_mappings[field] = {val: idx for idx, val in enumerate(sorted_values)}

    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process data to extract features with proper type handling."""
        processed_data = []

        if not isinstance(data, list):
            data = [data]

        if self.categorical_encoding == 'one_hot' and self.categorical_fields:
            self._collect_categorical_values(data)

        for item in data:
            processed_item = item.copy()

            try:
                records = item.get('raw_data', [item])
                if not isinstance(records, list):
                    records = [records]

                all_features = {}

                for record in records:
                    features = self._extract_features_from_record(record)
                    for key, value in features.items():
                        if key not in all_features:
                            all_features[key] = value

                processed_item['extracted_features'] = all_features
                processed_item['features'] = all_features

            except Exception as e:
                self.logger.error(f"Error processing item: {str(e)}")
                processed_item['extracted_features'] = {}
                processed_item['features'] = {}

            processed_data.append(processed_item)

        return processed_data

    def _extract_features_from_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features from a single record."""
        features = {}

        if self.all_configured_fields:
            fields_to_process = self.all_configured_fields
        elif self.fields == ['*']:
            metadata_keys = {'_source', 'features', 'normalized', 'extracted_features',
                           '_collection_metadata', 'raw_data', 'id', '_id',
                           'collected_at', 'collection_timestamp', 'timestamp'}
            fields_to_process = [f for f in record.keys() if f not in metadata_keys]
        else:
            fields_to_process = self.fields

        for field_name in fields_to_process:
            value = self._get_field_value(record, field_name)

            if value is None:
                continue

            try:
                if field_name in self.boolean_fields:
                    if isinstance(value, bool):
                        features[f"num_{field_name}"] = float(value)
                    elif isinstance(value, str):
                        lower_val = value.lower()
                        if lower_val in ['true', '1', 'yes', 'y']:
                            features[f"num_{field_name}"] = 1.0
                        elif lower_val in ['false', '0', 'no', 'n']:
                            features[f"num_{field_name}"] = 0.0

                elif field_name in self.categorical_fields:
                    if isinstance(value, str):
                        if self.categorical_encoding == 'one_hot':
                            if field_name in self.categorical_mappings:
                                idx = self.categorical_mappings[field_name].get(value, -1)
                                if idx >= 0:
                                    features[f"cat_{field_name}_idx_{idx}"] = 1.0
                        elif self.categorical_encoding == 'label':
                            if field_name in self.categorical_mappings:
                                idx = self.categorical_mappings[field_name].get(value, -1)
                                if idx >= 0:
                                    features[f"cat_{field_name}"] = float(idx)
                        elif self.categorical_encoding == 'hash':
                            import hashlib
                            hash_val = int(hashlib.md5(value.encode()).hexdigest(), 16) % 1000
                            features[f"cat_{field_name}_hash"] = float(hash_val)

                elif field_name in self.numerical_fields:
                    try:
                        float_val = float(value)
                        if not (np.isnan(float_val) or np.isinf(float_val)):
                            features[f"num_{field_name}"] = float_val
                    except (ValueError, TypeError):
                        pass

                elif field_name in self.text_fields:
                    if isinstance(value, str):
                        features[f"text_{field_name}_length"] = float(len(value))
                        features[f"text_{field_name}_word_count"] = float(len(value.split()))

                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    try:
                        float_val = float(value)
                        if not (np.isnan(float_val) or np.isinf(float_val)):
                            features[f"num_{field_name}"] = float_val
                    except (ValueError, TypeError):
                        pass

                elif isinstance(value, list):
                    features[f"list_{field_name}_length"] = float(len(value))

                elif isinstance(value, dict):
                    features[f"dict_{field_name}_size"] = float(len(value))

            except Exception as e:
                self.logger.warning(f"Error extracting field {field_name}: {str(e)}")

        return features
