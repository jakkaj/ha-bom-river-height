import logging
from urllib.request import urlopen
from urllib.error import URLError
from datetime import timedelta
from bs4 import BeautifulSoup, Comment
from dataclasses import dataclass
from typing import Optional, List, Union

import voluptuous as vol

# Import statements modified to make the code runnable outside Home Assistant when __name__ == "__main__"
try:
    from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
    from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
    import homeassistant.helpers.config_validation as cv
    from homeassistant.util import Throttle
    IN_HA = True
except ImportError:
    # Mock classes for standalone execution
    PLATFORM_SCHEMA = object()

    class SensorEntity:
        pass
    CONF_NAME = "name"
    CONF_UNIT_OF_MEASUREMENT = "unit_of_measurement"
    cv = object()

    class Throttle:
        def __init__(self, interval):
            self.interval = interval

        def __call__(self, func):
            return func
    IN_HA = False

_LOGGER = logging.getLogger(__name__)

CONF_URL = "url"
CONF_STATION_FILTER = "station_filter"

# We poll every 30 minutes, as specified
SCAN_INTERVAL = timedelta(minutes=30)

# Define the YAML schema for this platform
if IN_HA:
    PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_NAME, default="River Height"): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="m"): cv.string,
        vol.Optional(CONF_STATION_FILTER): cv.string,
    })


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the River Height sensor platform."""
    url = config[CONF_URL]
    name = config[CONF_NAME]
    unit_of_measurement = config[CONF_UNIT_OF_MEASUREMENT]
    station_filter = config.get(CONF_STATION_FILTER)

    # Verify the URL starts with ftp://
    if not url.startswith('ftp://'):
        _LOGGER.error("Only FTP URLs are supported (starting with ftp://)")
        return

    sensor = RiverHeightSensor(
        name, url, unit_of_measurement, station_filter)
    add_entities([sensor], True)


@dataclass
class RiverData:
    """Data structure to hold river information."""
    station_name: str
    timestamp: str
    height: float
    trend: str
    status: str
    metadata: Optional[str] = None

    def title_matches(self, search: str) -> bool:
        """Check if the station name contains the search string (case insensitive)."""
        return search.lower() in self.station_name.lower()


def _parse_river_data(row_data: List[str], metadata: Optional[str] = None) -> Optional[RiverData]:
    """Parse a row of data into a RiverData object."""
    if len(row_data) < 6:
        return None

    try:
        height_text = row_data[2].strip()
        height = float(height_text.replace(',', '').replace('m', ''))
        return RiverData(
            station_name=row_data[0].strip(),
            timestamp=row_data[1].strip(),
            height=height,
            trend=row_data[3].strip(),
            status=row_data[5].strip(),
            metadata=metadata
        )
    except (ValueError, IndexError):
        return None


def _parse_table(html_content: str, return_river_data: bool = False) -> Union[List[List[str]], List[RiverData]]:
    """
    Parse HTML content using BeautifulSoup to extract table data.
    Args:
        html_content: HTML content to parse
        return_river_data: If True, returns List[RiverData], otherwise List[List[str]]
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    rows = []

    # Find all tables in the document
    tables = soup.find_all('table', recursive=True)  # Only top-level tables
    for table in tables:
        # For each table, process each row
        for tr in table.find_all('tr', recursive=True):  # Only direct child rows
            # Look for metadata in comments before the row
            metadata = None
            comments = tr.find_all(
                string=lambda text: isinstance(text, Comment))
            for comment in comments:
                if "METADATA" in comment:
                    metadata = comment.strip()
                    break

            # Extract cell data
            row_data = []
            for td in tr.find_all(['td']):
                # Get text content, excluding nested table content
                cell_text = ''.join(text for text in td.stripped_strings)
                row_data.append(cell_text)

            if row_data:
                if return_river_data:
                    river = _parse_river_data(row_data, metadata)
                    if river is not None:
                        rows.append(river)
                else:
                    rows.append(row_data)

    return rows


class RiverHeightSensor(SensorEntity):
    """Representation of the River Height sensor."""

    def __init__(self, name, url, unit_of_measurement, station_filter=None):
        """Initialize the sensor."""
        self._name = name
        self._url = url
        self._unit_of_measurement = unit_of_measurement
        self._state = None
        self._available = False  # Start as unavailable until first update
        self._station_filter = station_filter
        self._rivers = []
        self._selected_river = None

        # Attributes for the data format
        self._station_name = None
        self._timestamp = None
        self._trend = None
        self._status = None
        self._metadata = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the native unit of measurement (e.g., meters)."""
        return self._unit_of_measurement

    @property
    def native_value(self):
        """Return the current river height as a float."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return extra attributes from the river height data."""
        attrs = {}

        if self._station_name:
            attrs["station_name"] = self._station_name
        if self._timestamp:
            attrs["timestamp"] = self._timestamp
        if self._trend:
            attrs["trend"] = self._trend
        if self._status:
            attrs["status"] = self._status
        if self._metadata:
            attrs["metadata"] = self._metadata

        return attrs if attrs else None

    @property
    def available(self):
        """Return True if sensor is available (i.e., latest fetch was successful)."""
        return self._available

    @property
    def all_rivers(self) -> List[RiverData]:
        """Return all rivers in the dataset."""
        return self._rivers

    def select_river(self, search_title: str) -> bool:
        """
        Select a specific river by searching for a title.
        Returns True if a matching river was found.
        """
        for river in self._rivers:
            if search_title.lower() in river.station_name.lower():
                self._selected_river = river
                self._update_state_from_river(river)
                return True
        return False

    def _update_state_from_river(self, river: RiverData) -> None:
        """Update sensor state from a RiverData object."""
        self._state = river.height
        self._station_name = river.station_name
        self._timestamp = river.timestamp
        self._trend = river.trend
        self._status = river.status
        self._metadata = river.metadata
        self._available = True

    def _fetch_url_content(self, url, timeout=10):
        """Fetch content from FTP URL."""
        try:
            if not url.startswith('ftp://'):
                _LOGGER.error("Only FTP URLs are supported: %s", url)
                return None

            with urlopen(url, timeout=timeout) as response:
                return response.read().decode('utf-8')
        except URLError as e:
            _LOGGER.error("Error fetching FTP URL %s: %s", url, str(e))
            return None

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """
        Fetch and parse the latest data.
        Throttle ensures this is called no more often than SCAN_INTERVAL.
        """
        # Reset state before update
        self._state = None
        self._available = False
        self._rivers = []
        self._selected_river = None

        try:
            html_content = self._fetch_url_content(self._url, timeout=10)

            if not html_content:
                _LOGGER.error(
                    "Error fetching river height data from %s", self._url)
                return

            # Parse all rivers from the table
            self._rivers = _parse_table(html_content, return_river_data=True)

            if not self._rivers:
                _LOGGER.warning("No river data found at %s", self._url)
                return

            # If we have a station filter, try to find that specific river
            if self._station_filter:
                if not self.select_river(self._station_filter):
                    _LOGGER.warning(
                        "Could not find river matching filter: %s", self._station_filter)
                    return
            else:
                # Default to first river if no filter specified
                self._selected_river = self._rivers[0]
                self._update_state_from_river(self._rivers[0])

        except Exception as err:
            _LOGGER.error(
                "Unexpected error processing river height data from %s: %s", self._url, err)


if __name__ == "__main__":
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Use the FTP URL provided
    url = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDQ60005.html"
    station_filter = "Coomera R at Oxenford Weir"

    print(f"Fetching river height data from {url}")
    print(f"Looking for station: {station_filter}")

    # Create and initialize the sensor
    sensor = RiverHeightSensor(
        name="River Height Test",
        url=url,
        unit_of_measurement="m",
        station_filter=station_filter
    )

    # Update the sensor data
    sensor.update()

    # Display results
    if sensor.available:
        print("\nFound matching river station:")
        print(f"Station: {sensor._station_name}")
        print(f"Height: {sensor._state} {sensor._unit_of_measurement}")
        print(f"Timestamp: {sensor._timestamp}")
        print(f"Trend: {sensor._trend}")
        print(f"Status: {sensor._status}")
        if sensor._metadata:
            print(f"Metadata: {sensor._metadata}")
    else:
        print(f"\nNo data found for {station_filter}")

        # Show all available stations as a fallback
        print("\nAll available stations:")
        for i, river in enumerate(sensor.all_rivers, 1):
            print(f"{i}. {river.station_name} - Height: {river.height}m")
