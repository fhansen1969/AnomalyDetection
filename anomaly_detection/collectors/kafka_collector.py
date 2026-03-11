"""
Kafka data collector for the anomaly detection system.

This module provides functionality to collect data from Kafka topics
and write them to JSON files for processing.
"""

import json
import logging
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

try:
    from kafka import KafkaConsumer, TopicPartition
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logging.warning("Kafka Python client not installed. KafkaCollector will not work.")

from anomaly_detection.collectors.base import Collector


class KafkaCollector(Collector):
    """
    Collector implementation for Apache Kafka data sources.
    
    This collector consumes messages from one or more Kafka topics
    and writes them to JSON files in the configured output directory.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """
        Initialize Kafka collector with configuration.
        
        Args:
            name: Collector name
            config: Kafka collector configuration
            storage_manager: Optional storage manager for persistence
        """
        super().__init__(name, config)
        self.storage_manager = storage_manager
        
        if not KAFKA_AVAILABLE:
            self.logger.error("Kafka Python client not installed. KafkaCollector will not work.")
            return
        
        # Kafka configuration
        self.bootstrap_servers = config.get("bootstrap_servers", "localhost:9092")
        self.topics_config = config.get("topics", [])
        self.consumer_timeout_ms = config.get("consumer_timeout_ms", 5000)
        self.batch_size = config.get("batch_size", 100)
        self.auto_offset_reset = config.get("auto_offset_reset", "earliest")
        self.enable_auto_commit = config.get("enable_auto_commit", True)
        self.max_poll_records = config.get("max_poll_records", 500)
        self.session_timeout_ms = config.get("session_timeout_ms", 10000)
        self.request_timeout_ms = config.get("request_timeout_ms", 30000)
        
        # Output configuration
        self.output_dir = Path(config.get("output_dir", "data/input"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.write_mode = config.get("write_mode", "both")  # "file", "memory", or "both"
        
        # File writing options
        self.write_individual_files = config.get("write_individual_files", True)
        self.write_batch_file = config.get("write_batch_file", True)
        self.max_file_size_mb = config.get("max_file_size_mb", 100)
        
        self.logger.info(f"Output directory: {self.output_dir.absolute()}")
        self.logger.info(f"Write mode: {self.write_mode}")
        
        # Group topics by group_id for efficient consumption
        self.group_topics = {}
        for topic_config in self.topics_config:
            topic_name = topic_config["name"]
            group_id = topic_config.get("group_id", "anomaly_detection_group")
            
            if group_id not in self.group_topics:
                self.group_topics[group_id] = []
            self.group_topics[group_id].append(topic_name)
        
        self.logger.info(f"Initialized Kafka collector with {len(self.group_topics)} consumer groups")
        for group_id, topics in self.group_topics.items():
            self.logger.info(f"  Group '{group_id}': topics {topics}")
    
    def collect(self) -> List[Dict[str, Any]]:
        """
        Collect data from Kafka topics and optionally write to JSON files.
        
        Returns:
            List of collected data items as dictionaries
        """
        if not KAFKA_AVAILABLE:
            self.logger.error("Kafka Python client not installed. Cannot collect data.")
            return []
        
        all_results = []
        files_written = []
        
        # Process each consumer group
        for group_id, topics in self.group_topics.items():
            try:
                self.logger.info(f"Creating consumer for group '{group_id}' with topics: {topics}")
                
                # Consumer configuration
                consumer_config = {
                    'bootstrap_servers': self.bootstrap_servers,
                    'group_id': group_id,
                    'auto_offset_reset': self.auto_offset_reset,
                    'enable_auto_commit': self.enable_auto_commit,
                    'max_poll_records': self.max_poll_records,
                    'session_timeout_ms': self.session_timeout_ms,
                    'request_timeout_ms': self.request_timeout_ms,
                    'consumer_timeout_ms': self.consumer_timeout_ms,
                    'value_deserializer': lambda x: json.loads(x.decode('utf-8')) if x else None
                }
                
                # Create a single consumer for all topics in this group
                consumer = KafkaConsumer(*topics, **consumer_config)
                
                # Log consumer details
                self.logger.info(f"Consumer created successfully for group '{group_id}'")
                self.logger.info(f"Consumer subscriptions: {consumer.subscription()}")
                
                # Collect messages from all topics in this group
                group_results = self._collect_from_consumer(consumer, group_id)
                
                if group_results:
                    self.logger.info(f"Collected {len(group_results)} messages from group '{group_id}'")
                    
                    # Write to files based on configuration
                    if self.write_mode in ["file", "both"]:
                        written_files = self._write_to_files(group_results, group_id)
                        files_written.extend(written_files)
                    
                    # Add to results if memory mode is enabled
                    if self.write_mode in ["memory", "both"]:
                        all_results.extend(group_results)
                else:
                    self.logger.info(f"No messages collected from group '{group_id}' within timeout")
                
                # Close the consumer
                consumer.close()
                self.logger.info(f"Consumer for group '{group_id}' closed successfully")
                
            except Exception as e:
                self.logger.error(f"Error collecting data from group '{group_id}': {str(e)}", exc_info=True)
        
        # Log summary
        self.logger.info(f"Collection complete. Total messages: {len(all_results)}, Files written: {len(files_written)}")
        if files_written:
            self.logger.info(f"Written files: {files_written}")
        
        return all_results
    
    def _collect_from_consumer(self, consumer, group_id: str) -> List[Dict[str, Any]]:
        """
        Collect messages from a consumer instance.
        
        Args:
            consumer: KafkaConsumer instance
            group_id: Consumer group ID
            
        Returns:
            List of collected messages
        """
        results = []
        batch_count = 0
        start_time = time.time()
        poll_count = 0
        max_polls = 10  # Maximum number of poll attempts
        
        try:
            # Wait for partition assignment
            while not consumer.assignment() and poll_count < 5:
                consumer.poll(timeout_ms=1000)
                poll_count += 1
                time.sleep(0.1)
            
            if consumer.assignment():
                self.logger.info(f"Consumer assigned partitions: {consumer.assignment()}")
            else:
                self.logger.warning(f"No partitions assigned to consumer after {poll_count} polls")
            
            # Main collection loop
            while batch_count < self.batch_size and poll_count < max_polls:
                # Poll for messages
                message_batch = consumer.poll(timeout_ms=self.consumer_timeout_ms, max_records=self.batch_size - batch_count)
                poll_count += 1
                
                if not message_batch:
                    self.logger.debug(f"No messages in poll {poll_count}/{max_polls}")
                    continue
                
                # Process messages from all partitions
                for topic_partition, messages in message_batch.items():
                    self.logger.info(f"Processing {len(messages)} messages from {topic_partition}")
                    
                    for message in messages:
                        try:
                            # Get the message value
                            data = message.value
                            
                            if data is None:
                                self.logger.warning(f"Null message at offset {message.offset}")
                                continue
                            
                            if not isinstance(data, dict):
                                self.logger.warning(f"Non-dict message at offset {message.offset}: {type(data)}")
                                data = {"raw_data": data}
                            
                            # Add metadata
                            data["_kafka_metadata"] = {
                                "topic": message.topic,
                                "partition": message.partition,
                                "offset": message.offset,
                                "timestamp": message.timestamp,
                                "timestamp_type": message.timestamp_type,
                                "key": message.key.decode('utf-8') if message.key else None,
                                "headers": [(k, v.decode('utf-8') if v else None) for k, v in message.headers] if message.headers else []
                            }
                            
                            data["_collection_metadata"] = {
                                "collector": self.name,
                                "group_id": group_id,
                                "collected_at": datetime.now().isoformat(),
                                "collection_timestamp": int(time.time() * 1000)
                            }
                            
                            results.append(data)
                            batch_count += 1
                            
                            if batch_count >= self.batch_size:
                                self.logger.info(f"Reached batch size limit ({self.batch_size})")
                                break
                                
                        except Exception as e:
                            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    
                    if batch_count >= self.batch_size:
                        break
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Collected {batch_count} messages from group '{group_id}' "
                            f"in {elapsed_time:.2f} seconds ({poll_count} polls)")
            
        except Exception as e:
            self.logger.error(f"Error during message collection for group '{group_id}': {str(e)}", exc_info=True)
        
        return results
    
    def _write_to_files(self, data: List[Dict[str, Any]], group_id: str) -> List[str]:
        """
        Write collected data to JSON files.
        
        Args:
            data: List of data items to write
            group_id: Consumer group ID for organizing files
            
        Returns:
            List of written file paths
        """
        written_files = []
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            
            # Write individual topic files
            if self.write_individual_files:
                # Group data by topic
                data_by_topic = {}
                for item in data:
                    topic = item.get("_kafka_metadata", {}).get("topic", "unknown")
                    if topic not in data_by_topic:
                        data_by_topic[topic] = []
                    data_by_topic[topic].append(item)
                
                # Write each topic's data to a separate file
                for topic, topic_data in data_by_topic.items():
                    filename = f"{topic}_{group_id}_{timestamp}.json"
                    filepath = self.output_dir / filename
                    
                    # Check file size limit
                    estimated_size = len(json.dumps(topic_data, default=str)) / (1024 * 1024)  # MB
                    if estimated_size > self.max_file_size_mb:
                        self.logger.warning(f"File size ({estimated_size:.2f}MB) exceeds limit ({self.max_file_size_mb}MB). Splitting...")
                        # Split into multiple files
                        chunk_size = int(len(topic_data) * self.max_file_size_mb / estimated_size)
                        for i in range(0, len(topic_data), chunk_size):
                            chunk = topic_data[i:i + chunk_size]
                            chunk_filename = f"{topic}_{group_id}_{timestamp}_part{i//chunk_size}.json"
                            chunk_filepath = self.output_dir / chunk_filename
                            self._write_json_file(chunk_filepath, chunk)
                            written_files.append(str(chunk_filepath))
                    else:
                        self._write_json_file(filepath, topic_data)
                        written_files.append(str(filepath))
                    
                    self.logger.info(f"Wrote {len(topic_data)} records to {filepath}")
            
            # Write batch file with all data
            if self.write_batch_file:
                batch_filename = f"kafka_batch_{group_id}_{timestamp}.json"
                batch_filepath = self.output_dir / batch_filename
                self._write_json_file(batch_filepath, data)
                written_files.append(str(batch_filepath))
                self.logger.info(f"Wrote batch file with {len(data)} records to {batch_filepath}")
                
        except Exception as e:
            self.logger.error(f"Error writing data to files: {str(e)}", exc_info=True)
        
        return written_files
    
    def _write_json_file(self, filepath: Path, data: List[Dict[str, Any]]):
        """
        Write data to a JSON file with proper formatting and error handling.
        
        Args:
            filepath: Path to write the file
            data: Data to write
        """
        try:
            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Write with atomic operation (write to temp then rename)
            temp_filepath = filepath.with_suffix('.tmp')
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            
            # Rename to final name
            temp_filepath.replace(filepath)
            
            # Set permissions
            os.chmod(filepath, 0o644)
            
        except Exception as e:
            self.logger.error(f"Error writing file {filepath}: {str(e)}", exc_info=True)
            # Clean up temp file if it exists
            temp_filepath = filepath.with_suffix('.tmp')
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise
    
    def collect_continuous(self, interval_seconds: int = 60):
        """
        Continuously collect data at specified intervals.
        
        Args:
            interval_seconds: Time between collection runs
        """
        self.logger.info(f"Starting continuous collection with {interval_seconds}s interval")
        
        while True:
            try:
                self.collect()
                self.logger.info(f"Waiting {interval_seconds} seconds before next collection...")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                self.logger.info("Stopping continuous collection...")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous collection: {str(e)}", exc_info=True)
                time.sleep(interval_seconds)