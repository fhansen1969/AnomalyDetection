"""
UPDATED File data collector for the anomaly detection system.

This version handles batch-structured JSON files with raw_data arrays.
"""

import json
import logging
import os
import time
import glob
import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from anomaly_detection.collectors.base import Collector


class FileCollector(Collector):
    """
    Collector implementation for file-based data sources.
    
    This collector reads data from files with specified patterns and
    converts them to the internal data format.
    
    UPDATED: Now handles batch structures like [{"raw_data": [...]}]
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """
        Initialize file collector with configuration.
        
        Args:
            name: Collector name
            config: File collector configuration
            storage_manager: Optional storage manager for persistence
        """
        super().__init__(name, config)
        self.storage_manager = storage_manager
        
        self.file_paths = config.get("paths", [])
        self.watch_interval = config.get("watch_interval_seconds", 60)
        self.batch_size = config.get("batch_size", 1000)
        self.processed_files = set()
        
        # NEW: Configuration for handling batch structures
        self.unwrap_batches = config.get("unwrap_batches", True)
        self.batch_field = config.get("batch_field", "raw_data")
        
        # Create a tracking file for processed files if storage manager is available
        if self.storage_manager:
            self.tracking_file = os.path.join(
                self.storage_manager.get_storage_path(), 
                f"file_collector_{name}_processed.json"
            )
            self._load_processed_files()
        else:
            self.tracking_file = None
            
        self.logger.info(f"Initialized file collector with patterns: {', '.join(self.file_paths)}")
        self.logger.info(f"Batch unwrapping: {'enabled' if self.unwrap_batches else 'disabled'}")
    
    def _load_processed_files(self):
        """Load the set of already processed files."""
        if self.tracking_file and os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    self.processed_files = set(json.load(f))
                self.logger.debug(f"Loaded {len(self.processed_files)} previously processed files")
            except Exception as e:
                self.logger.error(f"Error loading processed files tracking: {str(e)}")
    
    def _save_processed_files(self):
        """Save the set of processed files."""
        if self.tracking_file:
            try:
                with open(self.tracking_file, 'w') as f:
                    json.dump(list(self.processed_files), f)
            except Exception as e:
                self.logger.error(f"Error saving processed files tracking: {str(e)}")
    
    def _get_file_last_modified(self, file_path):
        """Get the last modified time for a file."""
        try:
            return os.path.getmtime(file_path)
        except Exception:
            return 0
    
    def collect(self) -> List[Dict[str, Any]]:
        """
        Collect data from files matching the configured patterns.
        
        Returns:
            List of collected data items as dictionaries
        """
        results = []
        processed_count = 0
        file_list = []
        
        # Find all files matching the patterns
        for pattern in self.file_paths:
            self.logger.debug(f"Looking for files matching pattern: {pattern}")
            matching_files = glob.glob(pattern, recursive=True)
            self.logger.debug(f"Found {len(matching_files)} files matching pattern: {pattern}")
            for file_path in matching_files:
                abs_path = os.path.abspath(file_path)
                file_list.append((abs_path, self._get_file_last_modified(abs_path)))
        
        # Sort by modification time (newest first)
        file_list.sort(key=lambda x: x[1], reverse=True)
        
        self.logger.debug(f"Total files to process: {len(file_list)}")
        
        # Process files until batch size is reached
        for file_path, mod_time in file_list:
            # Skip already processed files
            if file_path in self.processed_files:
                self.logger.debug(f"Skipping already processed file: {file_path}")
                continue
                
            try:
                self.logger.debug(f"Processing file: {file_path}")
                file_data = self._process_file(file_path)
                
                if file_data:
                    self.logger.debug(f"Extracted {len(file_data)} items from file: {file_path}")
                    results.extend(file_data)
                    processed_count += 1
                    self.processed_files.add(file_path)
                    
                    if processed_count >= self.batch_size:
                        break
                        
            except Exception as e:
                self.logger.error(f"Error processing file {file_path}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
        
        # Save processed files list
        self._save_processed_files()
        
        self.logger.info(f"Collected {len(results)} data items from {processed_count} files")
        return results
    
    def _process_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Process a single file and convert it to data items.
        
        Args:
            file_path: Path to file to process
            
        Returns:
            List of data items extracted from the file
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Handle different file types
        if file_ext == '.json':
            return self._process_json_file(file_path)
        elif file_ext in ['.log', '.txt']:
            return self._process_text_file(file_path)
        else:
            self.logger.warning(f"Unsupported file type: {file_ext} for file {file_path}")
            return []
    
    def _process_json_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Process a JSON file with support for batch structures.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of data items extracted from the file
        """
        with open(file_path, 'r') as f:
            content = json.load(f)
            
        results = []
        
        # Handle both array and object formats
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    # NEW: Check if this is a batch structure that needs unwrapping
                    if self.unwrap_batches and self.batch_field in item:
                        batch_data = item[self.batch_field]
                        if isinstance(batch_data, list):
                            # Unwrap the batch and process each record
                            self.logger.debug(f"Unwrapping batch with {len(batch_data)} records")
                            for record in batch_data:
                                if isinstance(record, dict):
                                    record["_source"] = {
                                        "collector": self.name,
                                        "file": file_path,
                                        "timestamp": datetime.datetime.fromtimestamp(
                                            os.path.getmtime(file_path)
                                        ).isoformat()
                                    }
                                    results.append(record)
                        else:
                            # batch_field exists but isn't a list, treat as single record
                            item["_source"] = {
                                "collector": self.name,
                                "file": file_path,
                                "timestamp": datetime.datetime.fromtimestamp(
                                    os.path.getmtime(file_path)
                                ).isoformat()
                            }
                            results.append(item)
                    else:
                        # No batch structure or unwrapping disabled, use as-is
                        item["_source"] = {
                            "collector": self.name,
                            "file": file_path,
                            "timestamp": datetime.datetime.fromtimestamp(
                                os.path.getmtime(file_path)
                            ).isoformat()
                        }
                        results.append(item)
                        
        elif isinstance(content, dict):
            # Single object - check if it's a batch structure
            if self.unwrap_batches and self.batch_field in content:
                batch_data = content[self.batch_field]
                if isinstance(batch_data, list):
                    self.logger.debug(f"Unwrapping batch with {len(batch_data)} records")
                    for record in batch_data:
                        if isinstance(record, dict):
                            record["_source"] = {
                                "collector": self.name,
                                "file": file_path,
                                "timestamp": datetime.datetime.fromtimestamp(
                                    os.path.getmtime(file_path)
                                ).isoformat()
                            }
                            results.append(record)
                else:
                    content["_source"] = {
                        "collector": self.name,
                        "file": file_path,
                        "timestamp": datetime.datetime.fromtimestamp(
                            os.path.getmtime(file_path)
                        ).isoformat()
                    }
                    results.append(content)
            else:
                content["_source"] = {
                    "collector": self.name,
                    "file": file_path,
                    "timestamp": datetime.datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    ).isoformat()
                }
                results.append(content)
        
        self.logger.info(f"Extracted {len(results)} records from {file_path}")
        return results
    
    def _process_text_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Process a text/log file.
        
        Args:
            file_path: Path to text file
            
        Returns:
            List of data items extracted from the file
        """
        results = []
        
        with open(file_path, 'r') as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                # Try to parse as JSON first
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        item["_source"] = {
                            "collector": self.name,
                            "file": file_path,
                            "line": line_number,
                            "timestamp": datetime.datetime.fromtimestamp(
                                os.path.getmtime(file_path)
                            ).isoformat()
                        }
                        results.append(item)
                except json.JSONDecodeError:
                    # Not JSON, treat as plain text
                    results.append({
                        "message": line,
                        "_source": {
                            "collector": self.name,
                            "file": file_path,
                            "line": line_number,
                            "timestamp": datetime.datetime.fromtimestamp(
                                os.path.getmtime(file_path)
                            ).isoformat()
                        }
                    })
        
        return results
