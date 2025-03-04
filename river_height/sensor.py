import logging
from urllib.request import urlopen
from urllib.error import URLError
from datetime import timedelta
from bs4 import BeautifulSoup, Comment
from dataclasses import dataclass
from typing import Optional, List, Union, Dict, Any

import voluptuous as vol

# Import statements modified to make the code runnable outside Home Assistant when __name__ == "__main__"
try:
    from homeassistant.components.sensor import (
        PLATFORM_SCHEMA,
        SensorEntity,
        SensorDeviceClass,
        SensorStateClass,
    )
    from homeassistant.const import (
        CONF_NAME,
        CONF_UNIT_OF_MEASUREMENT,
        CONF_SCAN_INTERVAL,
        STATE_UNKNOWN,
    )
    import homeassistant.helpers.config_validation as cv
    from homeassistant.util import Throttle
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
    from homeassistant.helpers.update_coordinator import (
        CoordinatorEntity,
        DataUpdateCoordinator,
    )
    IN_HA = True
except ImportError:
    # Mock classes for standalone execution
    PLATFORM_SCHEMA = object()

    class SensorEntity:
        pass
    CONF_NAME = "name"
    CONF_UNIT_OF_MEASUREMENT = "unit_of_measurement"
    CONF_SCAN_INTERVAL = "scan_interval"
    STATE_UNKNOWN = "unknown"
    SensorDeviceClass = object()
    SensorStateClass = object()
    cv = object()

    class Throttle:
        def __init__(self, interval):
            self.interval = interval

        def __call__(self, func):
            return func
    Entity = object()
    CoordinatorEntity = object()
    DataUpdateCoordinator = object()

    class HomeAssistant:
        pass

    class AddEntitiesCallback:
        pass
    ConfigType = Dict
    DiscoveryInfoType = Dict
    IN_HA = False

_LOGGER = logging.getLogger(__name__)

CONF_URL = "url"
CONF_STATION_FILTER = "station_filter"

# Default scan interval is 30 minutes
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

# Define the YAML schema for this platform
if IN_HA:
    PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_NAME, default="River Height"): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="m"): cv.string,
        vol.Optional(CONF_STATION_FILTER): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    })


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the River Height sensor platform."""
    url = config[CONF_URL]
    name = config[CONF_NAME]
    unit_of_measurement = config[CONF_UNIT_OF_MEASUREMENT]
    station_filter = config.get(CONF_STATION_FILTER)
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Verify the URL starts with ftp://
    if not url.startswith('ftp://'):
        _LOGGER.error("Only FTP URLs are supported (starting with ftp://)")
        return

    if IN_HA:
        # Create a coordinator that will be used by the entity
        coordinator = RiverHeightDataCoordinator(
            hass, url, station_filter, scan_interval
        )

        # Create consolidated entity
        entity = RiverHeightEntity(coordinator, name, unit_of_measurement)

        # Add entity to Home Assistant
        add_entities([entity], True)
    else:
        # Create the legacy single sensor for standalone mode
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

    # Add additional properties that may be needed for sensor entity functionality
    unit_of_measurement: Optional[str] = None
    device_class: Optional[str] = None
    state_class: Optional[str] = None
    entity_id: Optional[str] = None
    unique_id: Optional[str] = None

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


class RiverHeightDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching BOM river data."""

    def __init__(self, hass, url, station_filter, update_interval):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="BOM River Height",
            update_interval=update_interval,
        )
        self.url = url
        self.station_filter = station_filter
        self.rivers = []
        self.selected_river = None

    async def _async_update_data(self):
        """Fetch data from BOM."""
        try:
            # Use a separate method for the actual data fetching
            return await self.hass.async_add_executor_job(self._fetch_river_data)
        except Exception as err:
            _LOGGER.error("Error updating river height data: %s", err)
            raise

    def _fetch_river_data(self):
        """Fetch river height data from BOM."""
        try:
            html_content = self._fetch_url_content(self.url, timeout=10)

            if not html_content:
                _LOGGER.error(
                    "Error fetching river height data from %s", self.url)
                return None

            # Parse all rivers from the table
            self.rivers = _parse_table(html_content, return_river_data=True)

            if not self.rivers:
                _LOGGER.warning("No river data found at %s", self.url)
                return None

            # If we have a station filter, try to find that specific river
            if self.station_filter:
                for river in self.rivers:
                    if river.title_matches(self.station_filter):
                        self.selected_river = river
                        return river
                _LOGGER.warning(
                    "Could not find river matching filter: %s", self.station_filter)
                return None
            else:
                # Default to first river if no filter specified
                self.selected_river = self.rivers[0]
                return self.rivers[0]
        except Exception as err:
            _LOGGER.error(
                "Unexpected error processing river height data from %s: %s", self.url, err)
            return None

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


class RiverHeightBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for river height sensors."""

    def __init__(self, coordinator, name, unit_of_measurement):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = name
        self._unit_of_measurement = unit_of_measurement
        self._attr_unique_id = f"{name.lower().replace(' ', '_')}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


class RiverHeightCoordinatorSensor(RiverHeightBaseSensor):
    """Implementation of the river height sensor."""

    @property
    def native_value(self):
        """Return the river height."""
        if self.coordinator.data:
            return self.coordinator.data.height
        return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return extra attributes from the river height data."""
        if not self.coordinator.data:
            return {}

        attrs = {
            "station_name": self.coordinator.data.station_name,
            "timestamp": self.coordinator.data.timestamp,
            "trend": self.coordinator.data.trend,
            "status": self.coordinator.data.status,
        }

        if self.coordinator.data.metadata:
            attrs["metadata"] = self.coordinator.data.metadata

        return attrs


class RiverStationSensor(RiverHeightBaseSensor):
    """Implementation of the river station name sensor."""

    @property
    def native_value(self):
        """Return the river station name."""
        if self.coordinator.data:
            return self.coordinator.data.station_name
        return None


class RiverTimestampSensor(RiverHeightBaseSensor):
    """Implementation of the river timestamp sensor."""

    @property
    def native_value(self):
        """Return the timestamp of the river data."""
        if self.coordinator.data:
            return self.coordinator.data.timestamp
        return None


class RiverTrendSensor(RiverHeightBaseSensor):
    """Implementation of the river trend sensor."""

    @property
    def native_value(self):
        """Return the river trend."""
        if self.coordinator.data:
            return self.coordinator.data.trend
        return None


class RiverStatusSensor(RiverHeightBaseSensor):
    """Implementation of the river status sensor."""

    @property
    def native_value(self):
        """Return the river status."""
        if self.coordinator.data:
            return self.coordinator.data.status
        return None


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

    @Throttle(DEFAULT_SCAN_INTERVAL)
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


class RiverHeightEntity(CoordinatorEntity, SensorEntity):
    """Implementation of a consolidated River Height entity with multiple attributes."""

    def __init__(self, coordinator, name, unit_of_measurement):
        """Initialize the entity."""
        super().__init__(coordinator)
        self._name = name
        self._unit_of_measurement = unit_of_measurement
        self._attr_unique_id = f"{name.lower().replace(' ', '_')}"

        # Set device class and state class for proper formatting in UI
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the river height as the primary value."""
        if self.coordinator.data:
            return self.coordinator.data.height
        return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return all river data as attributes."""
        if not self.coordinator.data:
            return {}

        attrs = {
            "station_name": self.coordinator.data.station_name,
            "timestamp": self.coordinator.data.timestamp,
            "trend": self.coordinator.data.trend,
            "status": self.coordinator.data.status,
            "all_stations": [
                {
                    "station_name": river.station_name,
                    "height": river.height,
                    "timestamp": river.timestamp,
                    "trend": river.trend,
                    "status": river.status
                } for river in self.coordinator.rivers if river is not None
            ]
        }

        if self.coordinator.data.metadata:
            attrs["metadata"] = self.coordinator.data.metadata

        return attrs

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


if __name__ == "__main__":
    import sys
    import time

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

    # Create mock hass object for testing
    class MockHass:
        def async_add_executor_job(self, func):
            return func()

    # Create coordinator with test data
    coordinator = RiverHeightDataCoordinator(
        MockHass(),
        url,
        station_filter,
        DEFAULT_SCAN_INTERVAL
    )

    # Manually trigger data fetch
    river_data = coordinator._fetch_river_data()
    coordinator.data = river_data
    coordinator.last_update_success = river_data is not None

    # Create the Home Assistant entity
    entity = RiverHeightEntity(coordinator, "River Height", "m")

    # Display results
    if coordinator.data:
        print("\nFound station:")
        print(f"Station: {coordinator.data.station_name}")
        print(
            f"Height: {coordinator.data.height} {entity.native_unit_of_measurement}")
        print(f"Timestamp: {coordinator.data.timestamp}")
        print(f"Trend: {coordinator.data.trend}")
        print(f"Status: {coordinator.data.status}")
        if coordinator.data.metadata:
            print(f"Metadata: {coordinator.data.metadata}")
    else:
        print(f"\nNo data found for {station_filter}")
