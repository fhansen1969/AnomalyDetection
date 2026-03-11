"""
REST API data collector for the anomaly detection system.

This module provides functionality to collect data from REST APIs
for further processing and analysis.
"""

import logging
import json
import datetime
import time
from typing import Dict, List, Any, Optional

try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.packages.urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("Requests library not installed. RestApiCollector will not work.")

from anomaly_detection.collectors.base import Collector


class RestApiCollector(Collector):
    """
    Collector implementation for REST API data sources.
    
    This collector makes HTTP requests to configured API endpoints and
    converts the responses to the internal data format.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """
        Initialize REST API collector with configuration.
        
        Args:
            name: Collector name
            config: REST API collector configuration
            storage_manager: Optional storage manager for persistence
        """
        super().__init__(name, config)
        self.storage_manager = storage_manager
        
        if not REQUESTS_AVAILABLE:
            self.logger.error("Requests library not installed. RestApiCollector will not work.")
            return
        
        # API endpoints configuration
        self.endpoints = config.get("endpoints") or []
        self.batch_size = config.get("batch_size", 1000)
        self.timeout = config.get("timeout_seconds", 30)
        self.max_retries = config.get("max_retries", 3)
        self.retry_backoff = config.get("retry_backoff", 0.5)
        
        # Optional global authentication
        self.global_auth = config.get("authentication", {})
        
        # Optional rate limiting
        self.rate_limit = config.get("rate_limit", {})
        self.min_request_interval = self.rate_limit.get("min_interval_seconds", 0)
        self._last_request_time = 0
        
        # Create a session with retries
        self.session = self._create_session()
        
        self.logger.info(f"Initialized REST API collector with {len(self.endpoints)} endpoints")
    
    def _create_session(self):
        """Create and configure a requests session with retries."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_auth(self, endpoint_config):
        """Get authentication configuration, merging global and endpoint-specific settings."""
        endpoint_auth = endpoint_config.get("authentication", {})
        
        # If endpoint has specific auth config, use it
        if endpoint_auth:
            return endpoint_auth
        
        # Otherwise, use global auth config
        return self.global_auth
    
    def _make_request(self, endpoint_config):
        """Make an HTTP request to the API endpoint with appropriate configuration."""
        endpoint_name = endpoint_config.get("name", "unnamed")
        url = endpoint_config.get("url")
        method = endpoint_config.get("method", "GET").upper()
        headers = endpoint_config.get("headers", {})
        params = endpoint_config.get("params", {})
        data = endpoint_config.get("data")
        json_data = endpoint_config.get("json")
        
        if not url:
            self.logger.warning(f"Missing URL for endpoint {endpoint_name}")
            return None
        
        # Apply rate limiting if configured
        if self.min_request_interval > 0:
            time_since_last = time.time() - self._last_request_time
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                self.logger.debug(f"Rate limiting: Sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        # Apply authentication if configured
        auth_config = self._get_auth(endpoint_config)
        auth = None
        
        auth_type = auth_config.get("type", "").lower()
        if auth_type == "basic":
            auth = (auth_config.get("username", ""), auth_config.get("password", ""))
        elif auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        elif auth_type == "api_key":
            key_name = auth_config.get("key_name", "api_key")
            key_value = auth_config.get("key_value", "")
            key_in = auth_config.get("in", "header").lower()
            
            if key_in == "header":
                headers[key_name] = key_value
            elif key_in == "query":
                params[key_name] = key_value
        
        # Make the request
        self.logger.debug(f"Making {method} request to {url}")
        
        try:
            self._last_request_time = time.time()
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                auth=auth,
                timeout=self.timeout
            )
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Try to parse response as JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                # If not JSON, return text content with metadata
                return {
                    "content": response.text,
                    "content_type": response.headers.get("Content-Type", "text/plain"),
                    "status_code": response.status_code
                }
        
        except Exception as e:
            self.logger.error(f"Error making request to {url}: {str(e)}")
            return None
    
    def _process_response(self, response, endpoint_config):
        """
        Process API response according to the configuration.
        
        Args:
            response: The API response data
            endpoint_config: Configuration for the endpoint
            
        Returns:
            List of data items extracted from the response
        """
        if response is None:
            return []
        
        results = []
        endpoint_name = endpoint_config.get("name", "unnamed")
        
        # Extract data from response using configured JSON path
        data_path = endpoint_config.get("data_path", "")
        
        if data_path:
            # Simple dot notation path extraction
            current_data = response
            for key in data_path.split('.'):
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                elif isinstance(current_data, list) and key.isdigit():
                    index = int(key)
                    if 0 <= index < len(current_data):
                        current_data = current_data[index]
                    else:
                        self.logger.warning(f"Index {index} out of bounds in data_path for {endpoint_name}")
                        current_data = None
                        break
                else:
                    self.logger.warning(f"Could not find '{key}' in response for {endpoint_name}")
                    current_data = None
                    break
            
            # Extract the data at the specified path
            if current_data is not None:
                if isinstance(current_data, list):
                    data_items = current_data
                else:
                    data_items = [current_data]
            else:
                data_items = []
        else:
            # No data path specified, use entire response
            if isinstance(response, list):
                data_items = response
            else:
                data_items = [response]
        
        # Apply transformation to each item if configured
        transform = endpoint_config.get("transform", {})
        
        # Process each data item up to batch size
        for item in data_items[:self.batch_size]:
            if isinstance(item, dict):
                # Add metadata
                item["_source"] = {
                    "collector": self.name,
                    "endpoint": endpoint_name,
                    "timestamp": datetime.datetime.utcnow().isoformat()
                }
                
                # Apply field mapping if configured
                if "field_mapping" in transform:
                    mapped_item = {}
                    for source_field, target_field in transform["field_mapping"].items():
                        if source_field in item:
                            mapped_item[target_field] = item[source_field]
                    
                    # Add unmapped fields if configured to do so
                    if transform.get("include_unmapped", False):
                        for key, value in item.items():
                            if key not in transform["field_mapping"] and key != "_source":
                                mapped_item[key] = value
                    
                    # Add source metadata
                    mapped_item["_source"] = item["_source"]
                    item = mapped_item
                
                results.append(item)
            else:
                # Handle non-dict items
                results.append({
                    "value": item,
                    "_source": {
                        "collector": self.name,
                        "endpoint": endpoint_name,
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    }
                })
        
        return results
    
    def collect(self) -> List[Dict[str, Any]]:
        """
        Collect data from configured REST API endpoints.
        
        Returns:
            List of collected data items as dictionaries
        """
        if not REQUESTS_AVAILABLE:
            self.logger.error("Requests library not installed. Cannot collect data.")
            return []
        
        results = []
        
        for endpoint_config in self.endpoints:
            endpoint_name = endpoint_config.get("name", "unnamed")
            
            try:
                self.logger.info(f"Collecting data from endpoint: {endpoint_name}")
                
                # Make the request
                response = self._make_request(endpoint_config)
                
                # Process the response
                endpoint_results = self._process_response(response, endpoint_config)
                
                # Add to overall results
                results.extend(endpoint_results)
                
                self.logger.info(f"Collected {len(endpoint_results)} items from endpoint {endpoint_name}")
            
            except Exception as e:
                self.logger.error(f"Error collecting data from endpoint {endpoint_name}: {str(e)}")
        
        self.logger.info(f"Total data items collected from REST API sources: {len(results)}")
        return results