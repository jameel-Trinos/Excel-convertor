"""Geocoding service for converting addresses to latitude/longitude coordinates."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable

logger = logging.getLogger(__name__)


@dataclass
class GeocodeResult:
    """Result of a single geocoding operation."""
    row_index: int
    latitude: Optional[float]
    longitude: Optional[float]
    status: str  # "success", "not_found", "error"
    error: Optional[str] = None
    original_address: str = ""


class GeocodingService:
    """Service for geocoding addresses using OpenStreetMap Nominatim."""

    def __init__(self, user_agent: str = "pdf-excel-converter"):
        """
        Initialize the geocoding service.

        Args:
            user_agent: User agent string for Nominatim API (required by their TOS)
        """
        self.geolocator = Nominatim(user_agent=user_agent, timeout=10)
        self.rate_limit_delay = 1.1  # Nominatim requires max 1 request/second
        self.max_retries = 3
        self.retry_delay = 2.0

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

        # Append region hint for better accuracy
        full_address = f"{address.strip()}, {region_hint}" if region_hint else address.strip()

        for attempt in range(self.max_retries):
            try:
                location = self.geolocator.geocode(full_address)

                if location:
                    return {
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "status": "success",
                        "error": None
                    }
                else:
                    # Try without region hint as fallback
                    if region_hint:
                        location = self.geolocator.geocode(address.strip())
                        if location:
                            return {
                                "latitude": location.latitude,
                                "longitude": location.longitude,
                                "status": "success",
                                "error": None
                            }

                    return {
                        "latitude": None,
                        "longitude": None,
                        "status": "not_found",
                        "error": "Address not found"
                    }

            except GeocoderTimedOut:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                return {
                    "latitude": None,
                    "longitude": None,
                    "status": "error",
                    "error": "Geocoding timed out"
                }

            except (GeocoderServiceError, GeocoderUnavailable) as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                return {
                    "latitude": None,
                    "longitude": None,
                    "status": "error",
                    "error": f"Geocoding service error: {str(e)}"
                }

            except Exception as e:
                logger.error(f"Unexpected geocoding error: {e}")
                return {
                    "latitude": None,
                    "longitude": None,
                    "status": "error",
                    "error": f"Unexpected error: {str(e)}"
                }

        return {
            "latitude": None,
            "longitude": None,
            "status": "error",
            "error": "Max retries exceeded"
        }

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
                truncated_address = address[:50] + "..." if len(address) > 50 else address
                progress_callback(
                    i + 1,
                    total,
                    f"Geocoding: {truncated_address}",
                    success_count,
                    failed_count
                )

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
    # Find column index
    col_index = None
    for i, header in enumerate(headers):
        if header.lower() == address_column.lower():
            col_index = i
            break
        # Also check for partial match
        if address_column.lower() in header.lower():
            col_index = i
            break

    if col_index is None:
        raise ValueError(f"Column '{address_column}' not found. Available columns: {headers}")

    # Extract addresses
    addresses = []
    for row_idx, row in enumerate(rows):
        if col_index < len(row):
            address = row[col_index]
            if address and str(address).strip():
                addresses.append((row_idx, str(address).strip()))
            else:
                addresses.append((row_idx, ""))
        else:
            addresses.append((row_idx, ""))

    return addresses
