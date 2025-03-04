import unittest
from bs4 import BeautifulSoup
from datetime import timedelta
from unittest.mock import MagicMock
from river_height.sensor import (
    RiverHeightSensor,
    RiverHeightEntity,
    _parse_table,
    RiverData
)


class TestRiverHeightSensor(unittest.TestCase):
    def test_ftp_get_and_load(self):
        # Use the FTP URL provided
        url = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDQ60005.html"
        station_filter = "Coomera R at Oxenford Weir #"

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

        # Test results with assertions
        if sensor.available:
            print("\nFound matching river station:")
            # Add assertions to verify river station data
            self.assertEqual(sensor._station_name, station_filter)
            self.assertIsNotNone(sensor._state)
            self.assertIsInstance(sensor._state, float)
            self.assertEqual(sensor._unit_of_measurement, "m")
            self.assertIsNotNone(sensor._timestamp)
            self.assertIsNotNone(sensor._trend)
            self.assertIsNotNone(sensor._status)
            if sensor._metadata:
                print(f"Metadata: {sensor._metadata}")
        else:
            print(f"\nNo data found for {station_filter}")
            self.fail(f"No data found for station: {station_filter}")

            # Show all available stations as a fallback
            print("\nAll available stations:")
            for i, river in enumerate(sensor.all_rivers, 1):
                print(f"{i}. {river.station_name} - Height: {river.height}m")

    def test_consolidated_entity(self):
        """Test the new consolidated entity approach with coordinator."""
        url = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDQ60005.html"
        station_filter = "Coomera R at Oxenford Weir #"

        print(f"\nTesting consolidated entity")
        print(f"Fetching river height data from {url}")
        print(f"Looking for station: {station_filter}")

        # Create a simple sensor to fetch the data
        sensor = RiverHeightSensor(
            name="River Height Test",
            url=url,
            unit_of_measurement="m",
            station_filter=station_filter
        )
        sensor.update()

        if not sensor.available:
            self.fail(f"No data found for station: {station_filter}")
            return

        # Create a mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.data = RiverData(
            station_name=sensor._station_name,
            timestamp=sensor._timestamp,
            height=sensor._state,
            trend=sensor._trend,
            status=sensor._status,
            metadata=sensor._metadata
        )
        mock_coordinator.last_update_success = True
        mock_coordinator.rivers = sensor._rivers

        # Create the consolidated entity
        entity = RiverHeightEntity(mock_coordinator, "River Height Test", "m")

        # Test entity properties
        print("\nFound matching river station for consolidated entity:")
        self.assertIsNotNone(entity.native_value)
        self.assertIsInstance(entity.native_value, float)

        # Check attributes
        attributes = entity.extra_state_attributes
        self.assertIsNotNone(attributes)
        self.assertIn("station_name", attributes)
        self.assertIn("timestamp", attributes)
        self.assertIn("trend", attributes)
        self.assertIn("status", attributes)
        self.assertIn("all_stations", attributes)

        # Check if the station name matches our filter
        self.assertTrue(station_filter in attributes["station_name"])

        print(
            f"Entity state: {entity.native_value} {entity.native_unit_of_measurement}")
        print(f"Station: {attributes.get('station_name')}")
        print(f"Timestamp: {attributes.get('timestamp')}")
        print(f"Trend: {attributes.get('trend')}")
        print(f"Status: {attributes.get('status')}")
        print(
            f"Number of all stations available: {len(attributes.get('all_stations', []))}")


if __name__ == "__main__":
    unittest.main()
