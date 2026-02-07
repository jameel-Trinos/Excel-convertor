"""Geocoding service for converting addresses to latitude/longitude coordinates."""

import asyncio
import logging
import os
import re
import ssl
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
import urllib3

logger = logging.getLogger(__name__)

# Disable SSL warnings if we're disabling verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Monkey-patch requests to disable SSL verification by default for geocoding
# This is needed because some systems have SSL certificate issues
try:
    import requests
    
    # Patch requests Session to disable SSL verification
    _original_request = requests.Session.request
    
    def _patched_request(self, method, url, **kwargs):
        """Patched request method that disables SSL verification."""
        kwargs.setdefault('verify', False)
        return _original_request(self, method, url, **kwargs)
    
    requests.Session.request = _patched_request
    logger.info("Patched requests library to disable SSL verification for geocoding")
except Exception as e:
    logger.warning(f"Failed to patch requests library: {e}")

# Simple in-memory cache to avoid re-geocoding same addresses
_geocode_cache: Dict[str, dict] = {}


@dataclass
class GeocodeResult:
    """Result of a single geocoding operation."""
    row_index: int
    latitude: Optional[float]
    longitude: Optional[float]
    status: str  # "success", "not_found", "error"
    error: Optional[str] = None
    original_address: str = ""


def clean_address(address: str) -> str:
    """
    Clean and normalize an address for better geocoding results.

    Args:
        address: Raw address string

    Returns:
        Cleaned address string
    """
    if not address:
        return ""

    # Remove extra whitespace
    cleaned = " ".join(address.split())

    # Remove common noise patterns
    noise_patterns = [
        r'\bPS\s*No\.?\s*\d+\b',  # PS No. 123
        r'\bBooth\s*No\.?\s*\d+\b',  # Booth No. 123
        r'\bSlNo\.?\s*\d+\b',  # SlNo. 123
        r'\bS\.?No\.?\s*\d+\b',  # S.No. 123
        r'^\d+\s*[-\.]\s*',  # Leading numbers like "1. " or "1 - "
        r'\(\s*\d+\s*\)',  # (123)
    ]

    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Clean up result
    cleaned = " ".join(cleaned.split())
    cleaned = cleaned.strip(' ,-.')

    return cleaned


class GeocodingService:
    """Service for geocoding addresses using OpenStreetMap Nominatim."""

    def __init__(self, user_agent: str = "pdf-excel-converter", verify_ssl: Optional[bool] = None):
        """
        Initialize the geocoding service.

        Args:
            user_agent: User agent string for Nominatim API (required by their TOS)
            verify_ssl: Whether to verify SSL certificates. If None, checks GEOCODE_VERIFY_SSL env var,
                       defaults to False if SSL verification fails
        """
        # Check environment variable for SSL verification setting
        # Default to False (disable verification) to handle SSL certificate issues
        if verify_ssl is None:
            verify_ssl_env = os.getenv("GEOCODE_VERIFY_SSL", "false").lower()
            verify_ssl = verify_ssl_env in ("true", "1", "yes", "on")
        
        self.verify_ssl = verify_ssl
        
        # Initialize Nominatim (but we'll use direct HTTP as primary method due to SSL issues)
        # SSL verification is handled at the module level via monkey-patch
        try:
            self.geolocator = Nominatim(user_agent=user_agent, timeout=15)
        except Exception as e:
            logger.warning(f"Failed to initialize Nominatim geolocator: {e}")
            self.geolocator = None
        
        if not self.verify_ssl:
            logger.info("SSL certificate verification is disabled for geocoding requests (using direct HTTP method)")
        
        self.rate_limit_delay = 1.1  # Nominatim requires max 1 request/second
        self.max_retries = 3
        self.retry_delay = 2.0
        self.user_agent = user_agent

    def _geocode_direct_http(self, query: str) -> dict:
        """
        Direct HTTP request to Nominatim API, bypassing geopy.
        This is a fallback when geopy has SSL issues.
        
        Args:
            query: Address query string
            
        Returns:
            dict with keys: latitude, longitude, status, error
        """
        try:
            import requests
            
            # Nominatim API endpoint
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": 1,
                "addressdetails": 0
            }
            headers = {
                "User-Agent": self.user_agent
            }
            
            logger.debug(f"Making direct HTTP request to Nominatim for: {query[:50]}...")
            
            # Make request without SSL verification
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                verify=False,  # Explicitly disable SSL verification
                timeout=15
            )
            
            logger.debug(f"HTTP response status: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Received {len(data) if data else 0} results from Nominatim")
            
            if data and len(data) > 0:
                result_data = data[0]
                lat = float(result_data.get("lat", 0))
                lon = float(result_data.get("lon", 0))
                logger.info(f"Successfully geocoded '{query[:50]}...' -> ({lat}, {lon})")
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "status": "success",
                    "error": None
                }
            else:
                logger.debug(f"No results found for: {query[:50]}...")
                return {
                    "latitude": None,
                    "longitude": None,
                    "status": "not_found",
                    "error": "Address not found"
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"Direct HTTP geocoding request failed: {e}")
            return {
                "latitude": None,
                "longitude": None,
                "status": "error",
                "error": f"HTTP request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Direct HTTP geocoding failed with unexpected error: {e}", exc_info=True)
            return {
                "latitude": None,
                "longitude": None,
                "status": "error",
                "error": str(e)
            }

    def geocode_single(
        self,
        address: str,
        region_hint: str = "India"
    ) -> dict:
        """
        Geocode a single address.

        Args:
            address: The address to geocode
            region_hint: Region hint to improve accuracy (e.g., "Tamil Nadu, India")

        Returns:
            dict with keys: latitude, longitude, status, error
        """
        if not address or not address.strip():
            return {
                "latitude": None,
                "longitude": None,
                "status": "error",
                "error": "Empty address"
            }

        # Clean the address for better results
        cleaned_address = clean_address(address)
        if not cleaned_address:
            return {
                "latitude": None,
                "longitude": None,
                "status": "error",
                "error": "Empty address after cleaning"
            }

        # Check cache first
        cache_key = f"{cleaned_address.lower()}|{region_hint.lower() if region_hint else ''}"
        if cache_key in _geocode_cache:
            logger.debug(f"Cache hit for: {cleaned_address[:30]}...")
            return _geocode_cache[cache_key]

        # Build query variations to try
        queries_to_try = []

        # Primary: cleaned address with region hint
        if region_hint:
            queries_to_try.append(f"{cleaned_address}, {region_hint}")

        # Fallback 1: cleaned address only
        queries_to_try.append(cleaned_address)

        # Fallback 2: original address with region hint (sometimes noise helps)
        if region_hint and cleaned_address != address.strip():
            queries_to_try.append(f"{address.strip()}, {region_hint}")

        # Try direct HTTP first (more reliable with SSL issues)
        for query in queries_to_try:
            try:
                logger.debug(f"Trying direct HTTP geocoding for: {query[:50]}...")
                result = self._geocode_direct_http(query)
                if result and result.get("status") == "success":
                    _geocode_cache[cache_key] = result
                    logger.debug(f"Direct HTTP geocoding succeeded for: {query[:50]}...")
                    return result
                elif result and result.get("status") == "not_found":
                    # Address not found, try next query variation
                    continue
            except Exception as http_error:
                logger.debug(f"Direct HTTP geocoding failed: {http_error}")
            
            # Fallback to geopy if available
            if self.geolocator:
                for attempt in range(self.max_retries):
                    try:
                        location = self.geolocator.geocode(query)

                        if location:
                            result = {
                                "latitude": location.latitude,
                                "longitude": location.longitude,
                                "status": "success",
                                "error": None
                            }
                            # Cache successful result
                            _geocode_cache[cache_key] = result
                            return result

                        # No result, try next query
                        break

                    except GeocoderTimedOut:
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay * (attempt + 1))
                            continue
                        # On final attempt timeout, try next query
                        break

                    except (GeocoderServiceError, GeocoderUnavailable) as e:
                        error_str = str(e).lower()
                        # Check if it's an SSL error
                        if "ssl" in error_str or "certificate" in error_str or "cert" in error_str:
                            # Try direct HTTP request as fallback
                            logger.warning(f"SSL error with geopy, trying direct HTTP request: {e}")
                            try:
                                result = self._geocode_direct_http(query)
                                if result and result.get("status") == "success":
                                    _geocode_cache[cache_key] = result
                                    return result
                            except Exception as http_error:
                                logger.debug(f"Direct HTTP geocoding also failed: {http_error}")
                        
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay * (attempt + 1))
                            continue
                        logger.warning(f"Geocoding service error for '{query[:30]}...': {e}")
                        break

                    except Exception as e:
                        error_str = str(e).lower()
                        # Check if it's an SSL error in the exception message
                        if "ssl" in error_str or "certificate" in error_str or "cert" in error_str:
                            # Try direct HTTP request as fallback
                            logger.warning(f"SSL error detected, trying direct HTTP request: {e}")
                            try:
                                result = self._geocode_direct_http(query)
                                if result and result.get("status") == "success":
                                    _geocode_cache[cache_key] = result
                                    return result
                            except Exception as http_error:
                                logger.debug(f"Direct HTTP geocoding also failed: {http_error}")
                        
                        logger.error(f"Unexpected geocoding error: {e}")
                        # Continue to next query if this one fails
                        break

        # All queries failed
        result = {
            "latitude": None,
            "longitude": None,
            "status": "not_found",
            "error": "Address not found"
        }
        # Cache negative result too to avoid repeated lookups
        _geocode_cache[cache_key] = result
        return result

    async def geocode_batch(
        self,
        addresses: List[tuple],  # List of (row_index, address)
        region_hint: str = "India",
        progress_callback: Optional[Callable[[int, int, str, int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[GeocodeResult]:
        """
        Geocode a batch of addresses with rate limiting.

        Args:
            addresses: List of tuples (row_index, address_string)
            region_hint: Region hint to improve accuracy
            progress_callback: Callback function(current, total, message, success_count, failed_count)
            cancel_check: Function that returns True if operation should be cancelled

        Returns:
            List of GeocodeResult objects
        """
        results: List[GeocodeResult] = []
        total = len(addresses)
        success_count = 0
        failed_count = 0

        for i, (row_index, address) in enumerate(addresses):
            # Check for cancellation
            if cancel_check and cancel_check():
                logger.info("Geocoding cancelled by user")
                break

            # Rate limiting - wait before each request
            if i > 0:
                await asyncio.sleep(self.rate_limit_delay)

            # Geocode the address (run in thread to not block async)
            result_dict = await asyncio.to_thread(
                self.geocode_single,
                address,
                region_hint
            )

            # Create result object
            result = GeocodeResult(
                row_index=row_index,
                latitude=result_dict["latitude"],
                longitude=result_dict["longitude"],
                status=result_dict["status"],
                error=result_dict["error"],
                original_address=address
            )
            results.append(result)

            # Update counts
            if result.status == "success":
                success_count += 1
            else:
                failed_count += 1

            # Call progress callback
            if progress_callback:
                try:
                    truncated_address = address[:50] + "..." if len(address) > 50 else address
                    progress_callback(
                        i + 1,
                        total,
                        f"Geocoding: {truncated_address}",
                        success_count,
                        failed_count
                    )
                except Exception as callback_error:
                    logger.warning(f"Progress callback error: {callback_error}")

            logger.debug(
                f"Geocoded {i + 1}/{total}: {address[:30]}... -> "
                f"({result.latitude}, {result.longitude}) [{result.status}]"
            )

        return results


def extract_addresses_from_column(
    headers: List[str],
    rows: List[List],
    address_column: str
) -> List[tuple]:
    """
    Extract addresses from a specific column.

    Args:
        headers: List of column headers
        rows: List of row data
        address_column: Name of the column containing addresses

    Returns:
        List of tuples (row_index, address_string)

    Raises:
        ValueError: If address column not found
    """
    if not headers:
        raise ValueError("No headers found in the data")
    
    if not rows:
        raise ValueError("No rows found in the data")
    
    # Normalize the address column name for matching
    address_column_lower = address_column.lower().strip()
    
    # Find column index - try exact match first, then partial match
    col_index = None
    exact_match_index = None
    partial_match_index = None
    
    for i, header in enumerate(headers):
        header_lower = str(header).lower().strip()
        
        # Exact match (case-insensitive)
        if header_lower == address_column_lower:
            exact_match_index = i
            break
        
        # Partial match - check if address_column is in header or vice versa
        if address_column_lower in header_lower or header_lower in address_column_lower:
            # Prefer columns with common address keywords
            address_keywords = ["address", "location", "building", "place", "area", "street", "road"]
            if any(keyword in header_lower for keyword in address_keywords):
                if partial_match_index is None:
                    partial_match_index = i
    
    # Use exact match if found, otherwise use partial match
    col_index = exact_match_index if exact_match_index is not None else partial_match_index
    
    if col_index is None:
        available_columns = ", ".join([f"'{h}'" for h in headers[:10]])  # Show first 10 columns
        if len(headers) > 10:
            available_columns += f", ... ({len(headers)} total columns)"
        raise ValueError(
            f"Column '{address_column}' not found. "
            f"Available columns: {available_columns}. "
            f"Please check the column name and try again."
        )
    
    logger.info(f"Found address column '{address_column}' at index {col_index} (header: '{headers[col_index]}')")
    
    # Extract addresses
    addresses = []
    non_empty_count = 0
    for row_idx, row in enumerate(rows):
        if col_index < len(row):
            address = row[col_index]
            # Convert to string and clean
            if address is not None:
                address_str = str(address).strip()
                if address_str:
                    addresses.append((row_idx, address_str))
                    non_empty_count += 1
                else:
                    addresses.append((row_idx, ""))
            else:
                addresses.append((row_idx, ""))
        else:
            addresses.append((row_idx, ""))
    
    logger.info(f"Extracted {non_empty_count} non-empty addresses from {len(rows)} rows")
    
    if non_empty_count == 0:
        raise ValueError(
            f"No addresses found in column '{address_column}'. "
            f"The column exists but all values are empty."
        )
    
    return addresses
