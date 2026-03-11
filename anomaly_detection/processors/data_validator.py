"""
Data Validator for Anomaly Detection System

This module provides comprehensive data validation before feature extraction,
including schema validation, quality checks, and outlier detection.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict
from datetime import datetime
import json


class DataValidationError(Exception):
    """Custom exception for data validation errors."""
    pass


class ValidationReport:
    """Container for validation results."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.stats = {}
        self.valid_count = 0
        self.invalid_count = 0
        self.corrected_count = 0
        
    def add_error(self, message: str, item_id: str = None):
        """Add an error to the report."""
        self.errors.append({"message": message, "item_id": item_id})
        
    def add_warning(self, message: str, item_id: str = None):
        """Add a warning to the report."""
        self.warnings.append({"message": message, "item_id": item_id})
        
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0
    
    def summary(self) -> str:
        """Get a summary of the validation report."""
        return (f"Validation Report: {self.valid_count} valid, "
                f"{self.invalid_count} invalid, {self.corrected_count} corrected, "
                f"{len(self.errors)} errors, {len(self.warnings)} warnings")


class DataValidator:
    """
    Validates data quality before feature extraction.
    
    Performs comprehensive checks including:
    - Schema validation (required fields, data types)
    - Value range validation
    - Duplicate detection
    - Missing value analysis
    - Outlier detection
    - Timestamp validation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize data validator with configuration.
        
        Args:
            config: Validator configuration
        """
        self.config = config
        self.logger = logging.getLogger("DataValidator")
        
        # Validation settings
        self.required_fields = set(config.get("required_fields", []))
        self.optional_fields = set(config.get("optional_fields", []))
        self.timestamp_field = config.get("timestamp_field", "timestamp")
        self.id_field = config.get("id_field", "id")
        
        # Quality thresholds
        self.max_missing_ratio = config.get("max_missing_ratio", 0.3)
        self.max_duplicate_ratio = config.get("max_duplicate_ratio", 0.1)
        self.outlier_std_threshold = config.get("outlier_std_threshold", 5.0)
        
        # Validation modes
        self.strict_mode = config.get("strict_mode", False)
        self.auto_correct = config.get("auto_correct", True)
        self.remove_invalid = config.get("remove_invalid", True)
        
        # Field type specifications
        self.numerical_fields = set(config.get("numerical_fields", []))
        self.categorical_fields = set(config.get("categorical_fields", []))
        self.boolean_fields = set(config.get("boolean_fields", []))
        
        # Value constraints
        self.value_ranges = config.get("value_ranges", {})
        self.allowed_values = config.get("allowed_values", {})
        
        # Statistics tracking
        self.field_stats = defaultdict(lambda: {
            "count": 0,
            "missing": 0,
            "invalid": 0,
            "min": None,
            "max": None,
            "unique_values": set()
        })
        
        self.logger.info(f"Initialized DataValidator with {len(self.required_fields)} required fields")
    
    def validate_batch(self, data: List[Dict[str, Any]], 
                      report: Optional[ValidationReport] = None) -> Tuple[List[Dict[str, Any]], ValidationReport]:
        """
        Validate a batch of data items.
        
        Args:
            data: List of data items to validate
            report: Optional existing validation report to append to
            
        Returns:
            Tuple of (validated_data, validation_report)
        """
        if report is None:
            report = ValidationReport()
        
        validated_data = []
        
        self.logger.info(f"Validating batch of {len(data)} items")
        
        # First pass: Collect statistics
        self._collect_statistics(data)
        
        # Second pass: Validate each item
        for idx, item in enumerate(data):
            try:
                # Validate individual item
                is_valid, corrected_item, item_errors = self._validate_item(item, idx)
                
                # Record errors
                for error in item_errors:
                    report.add_error(error, item.get(self.id_field, str(idx)))
                
                # Handle based on validation result
                if is_valid:
                    validated_data.append(corrected_item)
                    report.valid_count += 1
                    if corrected_item != item:
                        report.corrected_count += 1
                else:
                    report.invalid_count += 1
                    if not self.strict_mode and self.auto_correct:
                        # Try to auto-correct
                        corrected = self._auto_correct_item(item)
                        if corrected:
                            validated_data.append(corrected)
                            report.corrected_count += 1
                            report.add_warning(f"Auto-corrected invalid item {idx}")
                        elif not self.remove_invalid:
                            validated_data.append(item)
                    elif not self.remove_invalid:
                        validated_data.append(item)
                        
            except Exception as e:
                self.logger.error(f"Error validating item {idx}: {str(e)}")
                report.add_error(f"Validation exception: {str(e)}", str(idx))
                if not self.remove_invalid:
                    validated_data.append(item)
        
        # Add statistics to report
        report.stats = self._generate_statistics_summary()
        
        # Check batch-level constraints
        self._validate_batch_constraints(validated_data, report)
        
        self.logger.info(report.summary())
        
        return validated_data, report
    
    def _validate_item(self, item: Dict[str, Any], idx: int) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Validate a single data item.
        
        Returns:
            Tuple of (is_valid, corrected_item, errors)
        """
        errors = []
        corrected_item = item.copy()
        
        # 1. Check required fields
        missing_required = self.required_fields - set(item.keys())
        if missing_required:
            errors.append(f"Missing required fields: {missing_required}")
        
        # 2. Validate field types
        type_errors = self._validate_field_types(item)
        errors.extend(type_errors)
        
        # 3. Validate value ranges
        range_errors = self._validate_value_ranges(item)
        errors.extend(range_errors)
        
        # 4. Validate timestamp
        timestamp_valid, timestamp_error, corrected_timestamp = self._validate_timestamp(item)
        if not timestamp_valid:
            errors.append(timestamp_error)
        elif corrected_timestamp is not None:
            corrected_item[self.timestamp_field] = corrected_timestamp
        
        # 5. Validate categorical values
        categorical_errors = self._validate_categorical_values(item)
        errors.extend(categorical_errors)
        
        is_valid = len(errors) == 0
        return is_valid, corrected_item, errors
    
    def _validate_field_types(self, item: Dict[str, Any]) -> List[str]:
        """Validate that fields have expected types."""
        errors = []
        
        # Check numerical fields
        for field in self.numerical_fields:
            if field in item:
                value = item[field]
                if not isinstance(value, (int, float, np.number)) and value is not None:
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append(f"Field '{field}' expected numeric, got {type(value).__name__}")
        
        # Check boolean fields
        for field in self.boolean_fields:
            if field in item:
                value = item[field]
                if not isinstance(value, bool) and value not in [0, 1, "true", "false", "True", "False"]:
                    errors.append(f"Field '{field}' expected boolean, got {value}")
        
        # Check categorical fields
        for field in self.categorical_fields:
            if field in item:
                value = item[field]
                if not isinstance(value, (str, int, float)) and value is not None:
                    errors.append(f"Field '{field}' expected scalar, got {type(value).__name__}")
        
        return errors
    
    def _validate_value_ranges(self, item: Dict[str, Any]) -> List[str]:
        """Validate that numerical values are within expected ranges."""
        errors = []
        
        for field, (min_val, max_val) in self.value_ranges.items():
            if field in item:
                value = item[field]
                try:
                    num_value = float(value)
                    if min_val is not None and num_value < min_val:
                        errors.append(f"Field '{field}' value {num_value} below minimum {min_val}")
                    if max_val is not None and num_value > max_val:
                        errors.append(f"Field '{field}' value {num_value} above maximum {max_val}")
                except (ValueError, TypeError):
                    pass  # Type validation will catch this
        
        return errors
    
    def _validate_timestamp(self, item: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate timestamp field.
        
        Returns:
            Tuple of (is_valid, error_message, corrected_timestamp)
        """
        if self.timestamp_field not in item:
            return False, f"Missing timestamp field '{self.timestamp_field}'", None
        
        timestamp_value = item[self.timestamp_field]
        
        # Try to parse timestamp
        try:
            if isinstance(timestamp_value, str):
                # Try ISO format first
                parsed = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                return True, None, None
            elif isinstance(timestamp_value, (int, float)):
                # Unix timestamp
                parsed = datetime.fromtimestamp(timestamp_value)
                # Convert to ISO format
                return True, None, parsed.isoformat()
            elif isinstance(timestamp_value, datetime):
                return True, None, timestamp_value.isoformat()
            else:
                return False, f"Invalid timestamp type: {type(timestamp_value).__name__}", None
                
        except Exception as e:
            return False, f"Failed to parse timestamp: {str(e)}", None
    
    def _validate_categorical_values(self, item: Dict[str, Any]) -> List[str]:
        """Validate that categorical fields have allowed values."""
        errors = []
        
        for field, allowed_vals in self.allowed_values.items():
            if field in item:
                value = str(item[field])
                if value not in allowed_vals:
                    errors.append(f"Field '{field}' has invalid value '{value}'. "
                                f"Allowed: {allowed_vals}")
        
        return errors
    
    def _collect_statistics(self, data: List[Dict[str, Any]]):
        """Collect statistics about the data for validation."""
        self.field_stats.clear()
        
        for item in data:
            for field, value in item.items():
                stats = self.field_stats[field]
                stats["count"] += 1
                
                if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
                    stats["missing"] += 1
                else:
                    # Track min/max for numerical fields
                    if isinstance(value, (int, float, np.number)):
                        if stats["min"] is None or value < stats["min"]:
                            stats["min"] = float(value)
                        if stats["max"] is None or value > stats["max"]:
                            stats["max"] = float(value)
                    
                    # Track unique values for categorical fields
                    if field in self.categorical_fields:
                        if len(stats["unique_values"]) < 1000:  # Limit to prevent memory issues
                            stats["unique_values"].add(str(value))
    
    def _generate_statistics_summary(self) -> Dict[str, Any]:
        """Generate summary statistics for the report."""
        summary = {}
        
        for field, stats in self.field_stats.items():
            total = stats["count"]
            missing = stats["missing"]
            
            field_summary = {
                "total": total,
                "missing": missing,
                "missing_ratio": missing / total if total > 0 else 0,
            }
            
            if stats["min"] is not None:
                field_summary["min"] = stats["min"]
                field_summary["max"] = stats["max"]
                field_summary["range"] = stats["max"] - stats["min"]
            
            if stats["unique_values"]:
                field_summary["unique_count"] = len(stats["unique_values"])
                field_summary["cardinality"] = len(stats["unique_values"]) / total if total > 0 else 0
            
            summary[field] = field_summary
        
        return summary
    
    def _validate_batch_constraints(self, data: List[Dict[str, Any]], report: ValidationReport):
        """Validate batch-level constraints."""
        if not data:
            report.add_error("Empty dataset after validation")
            return
        
        # Check for excessive missing values
        for field, stats in report.stats.items():
            missing_ratio = stats.get("missing_ratio", 0)
            if missing_ratio > self.max_missing_ratio:
                report.add_warning(
                    f"Field '{field}' has {missing_ratio:.1%} missing values "
                    f"(threshold: {self.max_missing_ratio:.1%})"
                )
        
        # Check for duplicates
        if self.id_field in report.stats:
            id_stats = report.stats[self.id_field]
            if "unique_count" in id_stats:
                duplicate_ratio = 1 - (id_stats["unique_count"] / id_stats["total"])
                if duplicate_ratio > self.max_duplicate_ratio:
                    report.add_warning(
                        f"Dataset has {duplicate_ratio:.1%} duplicate IDs "
                        f"(threshold: {self.max_duplicate_ratio:.1%})"
                    )
        
        # Detect outliers in numerical fields
        outliers = self._detect_outliers(data)
        if outliers:
            for field, outlier_count in outliers.items():
                report.add_warning(f"Field '{field}' has {outlier_count} outliers")
    
    def _detect_outliers(self, data: List[Dict[str, Any]]) -> Dict[str, int]:
        """Detect outliers using standard deviation method."""
        outliers = {}
        
        for field in self.numerical_fields:
            values = []
            for item in data:
                if field in item:
                    try:
                        value = float(item[field])
                        if not np.isnan(value) and not np.isinf(value):
                            values.append(value)
                    except (ValueError, TypeError):
                        pass
            
            if len(values) > 10:  # Need sufficient data
                mean = np.mean(values)
                std = np.std(values)
                
                if std > 0:
                    outlier_count = sum(
                        1 for v in values 
                        if abs(v - mean) > self.outlier_std_threshold * std
                    )
                    
                    if outlier_count > 0:
                        outliers[field] = outlier_count
        
        return outliers
    
    def _auto_correct_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Attempt to auto-correct an invalid item.
        
        Returns:
            Corrected item or None if correction failed
        """
        corrected = item.copy()
        
        # Add missing required fields with defaults
        for field in self.required_fields:
            if field not in corrected:
                if field in self.numerical_fields:
                    corrected[field] = 0.0
                elif field in self.boolean_fields:
                    corrected[field] = False
                elif field in self.categorical_fields:
                    corrected[field] = "unknown"
                else:
                    corrected[field] = None
        
        # Correct timestamp if missing or invalid
        if self.timestamp_field not in corrected or corrected[self.timestamp_field] is None:
            corrected[self.timestamp_field] = datetime.utcnow().isoformat()
        
        # Add ID if missing
        if self.id_field not in corrected:
            import uuid
            corrected[self.id_field] = str(uuid.uuid4())
        
        return corrected
    
    def get_validation_config(self) -> Dict[str, Any]:
        """Get the current validation configuration."""
        return {
            "required_fields": list(self.required_fields),
            "numerical_fields": list(self.numerical_fields),
            "categorical_fields": list(self.categorical_fields),
            "boolean_fields": list(self.boolean_fields),
            "value_ranges": self.value_ranges,
            "allowed_values": self.allowed_values,
            "thresholds": {
                "max_missing_ratio": self.max_missing_ratio,
                "max_duplicate_ratio": self.max_duplicate_ratio,
                "outlier_std_threshold": self.outlier_std_threshold
            }
        }


class DataValidatorFactory:
    """Factory for creating data validators from configuration."""
    
    @staticmethod
    def create_from_feature_config(feature_config: Dict[str, Any]) -> DataValidator:
        """
        Create a validator from feature extractor configuration.
        
        Args:
            feature_config: Feature extractor configuration
            
        Returns:
            Configured DataValidator
        """
        validator_config = {
            "numerical_fields": feature_config.get("numerical_fields", []),
            "categorical_fields": feature_config.get("categorical_fields", []),
            "boolean_fields": feature_config.get("boolean_fields", []),
            "timestamp_field": "timestamp",
            "id_field": "id",
            "max_missing_ratio": 0.5,
            "max_duplicate_ratio": 0.2,
            "outlier_std_threshold": 5.0,
            "strict_mode": False,
            "auto_correct": True,
            "remove_invalid": False  # Keep data, mark as invalid
        }
        
        return DataValidator(validator_config)