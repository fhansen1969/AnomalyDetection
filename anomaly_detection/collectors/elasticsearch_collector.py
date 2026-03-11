"""
Elasticsearch Data Collector for Anomaly Detection System

Collects data from Elasticsearch indices for anomaly detection.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

try:
    from elasticsearch import Elasticsearch
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    logging.warning("elasticsearch package not installed. ElasticsearchCollector will not work.")

from anomaly_detection.collectors.base import Collector


class ElasticsearchCollector(Collector):
    """
    Collector for Elasticsearch data sources.

    Queries Elasticsearch indices and formats results for anomaly detection.
    Supports both scroll API for large datasets and time-based queries.
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        super().__init__(name, config)
        self.storage_manager = storage_manager

        if not ELASTICSEARCH_AVAILABLE:
            self.logger.error("Elasticsearch package not installed")
            return

        # Elasticsearch connection config
        self.hosts = config.get("hosts", ["localhost:9200"])
        self.username = config.get("username")
        self.password = config.get("password")
        self.api_key = config.get("api_key")
        self.use_ssl = config.get("use_ssl", False)
        self.verify_certs = config.get("verify_certs", True)

        # Query configuration
        self.indices = config.get("indices", ["logs-*"])
        self.query = config.get("query", {"match_all": {}})
        self.time_field = config.get("time_field", "@timestamp")
        self.batch_size = config.get("batch_size", 1000)
        self.scroll_timeout = config.get("scroll_timeout", "5m")
        self.max_results = config.get("max_results", 10000)

        # Time range configuration
        self.lookback_hours = config.get("lookback_hours", 1)
        self.time_range_enabled = config.get("time_range_enabled", True)

        # Field mapping
        self.field_mapping = config.get("field_mapping", {})
        self.fields_to_extract = config.get("fields_to_extract", ["_source"])

        # Initialize Elasticsearch client
        self.client = self._create_client()

        # Track processed documents to avoid duplicates
        self.processed_ids = set()

        self.logger.info(f"Initialized Elasticsearch collector for indices: {self.indices}")

    def _create_client(self) -> Optional[Elasticsearch]:
        """Create and return Elasticsearch client."""
        try:
            client_config = {
                "hosts": self.hosts,
                "ssl_show_warn": False,
                "verify_certs": self.verify_certs,
            }

            if self.use_ssl:
                client_config["use_ssl"] = True

            if self.api_key:
                client_config["api_key"] = self.api_key
            elif self.username and self.password:
                client_config["basic_auth"] = (self.username, self.password)

            return Elasticsearch(**client_config)

        except Exception as e:
            self.logger.error(f"Failed to create Elasticsearch client: {e}")
            return None

    def collect(self) -> List[Dict[str, Any]]:
        """
        Collect data from Elasticsearch.

        Returns:
            List of collected data items formatted for anomaly detection
        """
        if not self.client:
            self.logger.error("Elasticsearch client not available")
            return []

        try:
            # Build search query
            search_query = self._build_search_query()

            # Execute search
            if self.max_results <= self.batch_size:
                # Single query for small result sets
                results = self._execute_single_query(search_query)
            else:
                # Use scroll API for large result sets
                results = self._execute_scroll_query(search_query)

            # Format results for anomaly detection
            formatted_results = []
            for hit in results:
                if hit["_id"] not in self.processed_ids:
                    formatted_item = self._format_hit(hit)
                    if formatted_item:
                        formatted_results.append(formatted_item)
                        self.processed_ids.add(hit["_id"])

            self.logger.info(f"Collected {len(formatted_results)} new documents from Elasticsearch")
            return formatted_results

        except Exception as e:
            self.logger.error(f"Error collecting from Elasticsearch: {e}")
            return []

    def _build_search_query(self) -> Dict[str, Any]:
        """Build the Elasticsearch search query."""
        query = {
            "query": self.query,
            "size": min(self.batch_size, self.max_results),
            "_source": self.fields_to_extract,
            "sort": [{self.time_field: {"order": "desc"}}]
        }

        # Add time range filter if enabled
        if self.time_range_enabled:
            time_filter = self._build_time_filter()
            if time_filter:
                if "bool" not in query["query"]:
                    original_query = query["query"]
                    query["query"] = {"bool": {"must": [original_query]}}
                else:
                    query["query"]["bool"].setdefault("must", [])

                query["query"]["bool"]["must"].append(time_filter)

        return query

    def _build_time_filter(self) -> Optional[Dict[str, Any]]:
        """Build time range filter for recent data."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=self.lookback_hours)

            return {
                "range": {
                    self.time_field: {
                        "gte": start_time.isoformat(),
                        "lte": end_time.isoformat()
                    }
                }
            }
        except Exception as e:
            self.logger.warning(f"Failed to build time filter: {e}")
            return None

    def _execute_single_query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a single Elasticsearch query."""
        try:
            response = self.client.search(
                index=self.indices,
                body=query
            )

            hits = response.get("hits", {}).get("hits", [])
            self.logger.debug(f"Single query returned {len(hits)} hits")

            return hits

        except Exception as e:
            self.logger.error(f"Single query failed: {e}")
            return []

    def _execute_scroll_query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute scroll query for large result sets."""
        try:
            # Initial search
            response = self.client.search(
                index=self.indices,
                body=query,
                scroll=self.scroll_timeout
            )

            scroll_id = response.get("_scroll_id")
            hits = response.get("hits", {}).get("hits", [])

            total_collected = len(hits)

            # Continue scrolling until we have enough results or no more data
            while total_collected < self.max_results and hits:
                response = self.client.scroll(
                    scroll_id=scroll_id,
                    scroll=self.scroll_timeout
                )

                new_hits = response.get("hits", {}).get("hits", [])
                if not new_hits:
                    break

                hits.extend(new_hits)
                total_collected += len(new_hits)

                # Update scroll ID
                scroll_id = response.get("_scroll_id")

            # Clear scroll context
            try:
                self.client.clear_scroll(scroll_id=scroll_id)
            except:
                pass

            self.logger.debug(f"Scroll query collected {total_collected} total hits")
            return hits[:self.max_results]

        except Exception as e:
            self.logger.error(f"Scroll query failed: {e}")
            return []

    def _format_hit(self, hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Format Elasticsearch hit for anomaly detection."""
        try:
            source = hit.get("_source", {})

            # Apply field mapping if specified
            if self.field_mapping:
                mapped_data = {}
                for target_field, source_field in self.field_mapping.items():
                    if source_field in source:
                        mapped_data[target_field] = source[source_field]
                    else:
                        # Try nested field access (e.g., "user.name")
                        value = self._get_nested_field(source, source_field)
                        if value is not None:
                            mapped_data[target_field] = value
                source = mapped_data

            # Add metadata
            formatted_item = {
                "_source": {
                    "collector": self.name,
                    "type": "elasticsearch",
                    "index": hit.get("_index"),
                    "id": hit.get("_id"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

            # Add the actual data
            formatted_item.update(source)

            # Ensure we have a timestamp field
            if self.time_field in source:
                formatted_item["timestamp"] = source[self.time_field]
            elif "@timestamp" in source:
                formatted_item["timestamp"] = source["@timestamp"]
            else:
                formatted_item["timestamp"] = datetime.utcnow().isoformat()

            return formatted_item

        except Exception as e:
            self.logger.warning(f"Failed to format hit {hit.get('_id')}: {e}")
            return None

    def _get_nested_field(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get nested field value using dot notation."""
        try:
            parts = field_path.split(".")
            current = data

            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None

            return current

        except Exception:
            return None

    def test_connection(self) -> bool:
        """Test Elasticsearch connection."""
        if not self.client:
            return False

        try:
            info = self.client.info()
            self.logger.info(f"Elasticsearch connection successful. Version: {info.get('version', {}).get('number')}")
            return True
        except Exception as e:
            self.logger.error(f"Elasticsearch connection test failed: {e}")
            return False
