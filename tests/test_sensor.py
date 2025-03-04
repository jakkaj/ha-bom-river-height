import unittest
from bs4 import BeautifulSoup
from river_height.sensor import RiverHeightSensor, _parse_table, RiverData


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
