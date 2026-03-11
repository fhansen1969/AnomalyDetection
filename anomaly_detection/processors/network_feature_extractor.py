"""
Network Feature Extractor for Anomaly Detection System

Specialized feature extractor for network traffic data.
"""

import logging
import numpy as np
import ipaddress
from typing import Dict, List, Any, Optional
from collections import defaultdict

from anomaly_detection.processors.base import Processor


class NetworkFeatureExtractor(Processor):
    """
    Specialized feature extractor for network traffic data.

    Extracts features specific to network analysis:
    - IP address analysis
    - Port analysis
    - Protocol analysis
    - Traffic patterns
    - Geographic features
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        super().__init__(name, config)
        self.storage_manager = storage_manager

        # Network-specific configuration
        self.ip_fields = set(config.get("ip_fields", ["src_ip", "dst_ip", "client_ip", "server_ip"]))
        self.port_fields = set(config.get("port_fields", ["src_port", "dst_port", "port"]))
        self.protocol_fields = set(config.get("protocol_fields", ["protocol", "service"]))

        # Geographic analysis (requires GeoIP database)
        self.enable_geographic = config.get("enable_geographic", False)
        self.geoip_db_path = config.get("geoip_db_path", "/usr/share/GeoIP/GeoLite2-City.mmdb")

        # Traffic pattern analysis
        self.enable_pattern_analysis = config.get("enable_pattern_analysis", True)
        self.session_timeout = config.get("session_timeout_seconds", 300)

        # Load GeoIP if enabled
        self.geo_reader = None
        if self.enable_geographic:
            try:
                import geoip2.database
                self.geo_reader = geoip2.database.Reader(self.geoip_db_path)
                self.logger.info("Loaded GeoIP database")
            except ImportError:
                self.logger.warning("GeoIP2 not available, geographic features disabled")
                self.enable_geographic = False
            except Exception as e:
                self.logger.warning(f"Failed to load GeoIP database: {e}")
                self.enable_geographic = False

        self.logger.info(f"Initialized Network Feature Extractor")

    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract network-specific features from data.

        Args:
            data: List of network data items

        Returns:
            List of data items with extracted network features
        """
        processed_data = []

        for item in data:
            processed_item = item.copy()

            try:
                # Extract network features
                network_features = self._extract_network_features(item)

                # Add to existing features if present
                if "features" in processed_item:
                    processed_item["features"].update(network_features)
                else:
                    processed_item["features"] = network_features

                processed_item["network_features"] = network_features

            except Exception as e:
                self.logger.error(f"Error extracting network features: {e}")
                processed_item["features"] = {}
                processed_item["network_features"] = {}

            processed_data.append(processed_item)

        self.logger.info(f"Extracted network features for {len(processed_data)} items")
        return processed_data

    def _extract_network_features(self, item: Dict[str, Any]) -> Dict[str, float]:
        """Extract network-specific features from a single item."""
        features = {}

        # IP Address Features
        features.update(self._extract_ip_features(item))

        # Port Features
        features.update(self._extract_port_features(item))

        # Protocol Features
        features.update(self._extract_protocol_features(item))

        # Traffic Pattern Features
        if self.enable_pattern_analysis:
            features.update(self._extract_traffic_features(item))

        # Geographic Features
        if self.enable_geographic:
            features.update(self._extract_geographic_features(item))

        return features

    def _extract_ip_features(self, item: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from IP addresses."""
        features = {}

        for field_name in self.ip_fields:
            if field_name in item:
                ip_str = str(item[field_name])
                try:
                    ip_obj = ipaddress.ip_address(ip_str)

                    # Basic IP features
                    features[f"{field_name}_is_private"] = float(ip_obj.is_private)
                    features[f"{field_name}_is_loopback"] = float(ip_obj.is_loopback)
                    features[f"{field_name}_is_multicast"] = float(ip_obj.is_multicast)
                    features[f"{field_name}_is_link_local"] = float(ip_obj.is_link_local)

                    # IPv4 specific features
                    if isinstance(ip_obj, ipaddress.IPv4Address):
                        features[f"{field_name}_is_ipv4"] = 1.0
                        features[f"{field_name}_ipv4_class"] = float(ip_obj.packed[0] // 32)  # Rough class estimation

                        # Extract octets
                        octets = ip_obj.packed
                        for i, octet in enumerate(octets):
                            features[f"{field_name}_octet_{i}"] = float(octet)

                    # IPv6 specific features
                    elif isinstance(ip_obj, ipaddress.IPv6Address):
                        features[f"{field_name}_is_ipv6"] = 1.0
                        features[f"{field_name}_is_ipv6_mapped"] = float(ip_obj.ipv4_mapped is not None)

                except ValueError:
                    # Invalid IP address
                    features[f"{field_name}_is_valid"] = 0.0

        return features

    def _extract_port_features(self, item: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from port numbers."""
        features = {}

        for field_name in self.port_fields:
            if field_name in item:
                try:
                    port = int(item[field_name])

                    # Port classification
                    features[f"{field_name}_is_well_known"] = float(0 <= port <= 1023)
                    features[f"{field_name}_is_registered"] = float(1024 <= port <= 49151)
                    features[f"{field_name}_is_dynamic"] = float(49152 <= port <= 65535)

                    # Common service ports
                    common_ports = {
                        21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
                        53: "dns", 80: "http", 443: "https", 3306: "mysql",
                        5432: "postgresql", 6379: "redis"
                    }

                    if port in common_ports:
                        features[f"{field_name}_is_common_service"] = 1.0
                        # One-hot encode service type
                        for service_port, service_name in common_ports.items():
                            features[f"{field_name}_is_{service_name}"] = float(port == service_port)
                    else:
                        features[f"{field_name}_is_common_service"] = 0.0

                    # Port ranges
                    features[f"{field_name}_port_range"] = float(port // 1000)  # Group by thousands

                except (ValueError, TypeError):
                    features[f"{field_name}_is_valid"] = 0.0

        return features

    def _extract_protocol_features(self, item: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from protocol information."""
        features = {}

        for field_name in self.protocol_fields:
            if field_name in item:
                protocol = str(item[field_name]).lower()

                # Protocol classification
                protocol_map = {
                    'tcp': ['tcp', '6'],
                    'udp': ['udp', '17'],
                    'icmp': ['icmp', '1'],
                    'http': ['http', '80', '443'],
                    'dns': ['dns', 'domain', '53'],
                    'ftp': ['ftp', '21'],
                    'ssh': ['ssh', '22'],
                    'smtp': ['smtp', '25']
                }

                for proto_name, proto_values in protocol_map.items():
                    features[f"{field_name}_is_{proto_name}"] = float(protocol in proto_values)

                # Transport layer features
                transport_protocols = ['tcp', 'udp', 'sctp', 'dccp']
                features[f"{field_name}_is_transport"] = float(any(protocol in proto_values for proto_values in
                                                                 [protocol_map[p] for p in transport_protocols]))

                # Application layer features
                app_protocols = ['http', 'https', 'dns', 'ftp', 'ssh', 'smtp']
                features[f"{field_name}_is_application"] = float(any(protocol in proto_values for proto_values in
                                                                     [protocol_map[p] for p in app_protocols]))

        return features

    def _extract_traffic_features(self, item: Dict[str, Any]) -> Dict[str, float]:
        """Extract traffic pattern features."""
        features = {}

        # Packet/byte counts
        if "bytes" in item:
            try:
                byte_count = float(item["bytes"])
                features["bytes_log"] = float(np.log1p(byte_count))  # Log transform
                features["bytes_category"] = float(np.digitize(byte_count, [100, 1000, 10000, 100000]))
            except (ValueError, TypeError):
                features["bytes_valid"] = 0.0

        if "packets" in item:
            try:
                packet_count = float(item["packets"])
                features["packets_log"] = float(np.log1p(packet_count))
                features["packets_category"] = float(np.digitize(packet_count, [10, 100, 1000, 10000]))
            except (ValueError, TypeError):
                features["packets_valid"] = 0.0

        # Calculate derived metrics
        if "bytes" in item and "packets" in item:
            try:
                bytes_val = float(item["bytes"])
                packets_val = float(item["packets"])

                if packets_val > 0:
                    features["avg_packet_size"] = bytes_val / packets_val
                    features["avg_packet_size_log"] = float(np.log1p(bytes_val / packets_val))
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # Time-based features
        if "duration" in item:
            try:
                duration = float(item["duration"])
                features["duration_log"] = float(np.log1p(duration))
                features["duration_category"] = float(np.digitize(duration, [1, 10, 60, 300, 3600]))
            except (ValueError, TypeError):
                pass

        return features

    def _extract_geographic_features(self, item: Dict[str, Any]) -> Dict[str, float]:
        """Extract geographic features from IP addresses."""
        features = {}

        if not self.geo_reader:
            return features

        for field_name in self.ip_fields:
            if field_name in item:
                ip_str = str(item[field_name])
                try:
                    response = self.geo_reader.city(ip_str)

                    # Country information
                    if response.country.iso_code:
                        # One-hot encode top countries (you might want to make this configurable)
                        top_countries = ['US', 'CN', 'RU', 'DE', 'GB', 'FR', 'JP', 'KR', 'IN', 'BR']
                        for country in top_countries:
                            features[f"{field_name}_country_{country}"] = float(response.country.iso_code == country)

                    # City information (if needed)
                    if response.city.name:
                        city_hash = hash(response.city.name) % 1000  # Simple hash for city
                        features[f"{field_name}_city_hash"] = float(city_hash)

                    # Coordinates
                    if response.location.latitude and response.location.longitude:
                        features[f"{field_name}_latitude"] = response.location.latitude
                        features[f"{field_name}_longitude"] = response.location.longitude

                except Exception as e:
                    self.logger.debug(f"GeoIP lookup failed for {ip_str}: {e}")

        return features
