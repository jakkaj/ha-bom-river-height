# BOM River Height Sensor

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

This Home Assistant integration provides real-time river height data from the Australian Bureau of Meteorology (BOM).

## Features

- Real-time river height monitoring
- Automatic updates every 30 minutes (configurable)
- River height trend information
- Last update timestamp
- Station status information
- Supports metric measurements

## Configuration

Example configuration:

```yaml
sensor:
  - platform: river_height
    url: "ftp://ftp.bom.gov.au/anon/gen/fwo/IDQ60005.html"
    name: "Coomera River"
    station_filter: "Coomera R at Oxenford Weir"
```