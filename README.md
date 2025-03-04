# Home Assistant River Height Sensor

A Home Assistant integration that provides real-time river height data from the Australian Bureau of Meteorology (BOM). This integration allows you to monitor river levels, trends, and status updates directly in your Home Assistant dashboard.

## Features

- Real-time river height monitoring
- Automatic updates every 30 minutes (configurable)
- Includes additional data attributes:
  - River height trend (rising/falling/steady)
  - Last update timestamp
  - Station status information
- Filter for specific monitoring stations
- Supports metric measurements
- Easy integration with Home Assistant automations and alerts

## Installation

### Method 1: HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations
   - Click on the three dots in the top right corner
   - Select "Custom repositories"
   - Add `https://github.com/USERNAME/ha-bom-river-height` as a new repository
   - Category: Integration
3. Click "Install"
4. Restart Home Assistant

### Method 2: Manual Installation

1. Copy the `river_height` directory to your Home Assistant's `custom_components` directory:
   ```bash
   cd /config/custom_components
   git clone https://github.com/USERNAME/ha-bom-river-height.git
   mv ha-bom-river-height/river_height .
   rm -rf ha-bom-river-height
   ```
2. Restart Home Assistant

## Configuration

Add the following to your `configuration.yaml`:

```yaml
sensor:
  - platform: river_height
    url: "ftp://ftp.bom.gov.au/anon/gen/fwo/IDQ60005.html"
    name: "Coomera River"  # Change this to your preferred name
    unit_of_measurement: "m"
    station_filter: "Coomera R at Oxenford Weir"  # Change this to your local station
    scan_interval: 00:30:00  # Optional: customize update interval
```

### Configuration Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `url` | BOM FTP URL for river height data | Yes | - |
| `name` | Name for the sensor | No | "River Height" |
| `unit_of_measurement` | Unit of measurement | No | "m" |
| `station_filter` | Filter for specific station | No | - |
| `scan_interval` | Update interval | No | 30 minutes |

## Using Template Sensors

You can create template sensors to display individual attributes. Add this to your `configuration.yaml`:

```yaml
template:
  - sensor:
      - name: "River Trend"
        unique_id: river_trend
        state: "{{ state_attr('sensor.river_height', 'trend') }}"
        icon: "mdi:trending-up"
        
      - name: "River Status"
        unique_id: river_status
        state: "{{ state_attr('sensor.river_height', 'status') }}"
        icon: "mdi:information"
        
      - name: "River Last Updated"
        unique_id: river_last_updated
        state: "{{ state_attr('sensor.river_height', 'timestamp') }}"
        icon: "mdi:clock-outline"
```

## Example Automation

Here's an example automation to get notifications when the river height exceeds a threshold:

```yaml
automation:
  - alias: "High River Alert"
    description: "Notify when river height is above threshold"
    trigger:
      - platform: numeric_state
        entity_id: sensor.river_height
        above: 2.5
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ High River Level Alert"
          message: "River height is {{ states('sensor.river_height') }}m and {{ state_attr('sensor.river_height', 'trend') }}"
```

## Requirements

- Home Assistant 2023.1.0 or later
- Python 3.12 or later
- Internet connection to access BOM data

## Dependencies

The following Python packages are required and will be automatically installed:
- beautifulsoup4>=4.11.0
- requests>=2.27.0
- voluptuous>=0.13.1

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you encounter any issues or have questions, please open an issue on GitHub.