# home-assistant-solarfocus
Custom component for Home-Assistant to integrate Solarfocus eco manager-touch

## Installation

### Hacs

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

- Install [Home Assistant Community Store (HACS)](https://hacs.xyz/)
- Add custom repository https://github.com/lavermanjj/home-assistant-solarfocus to HACS
- Add integration repository (search for "Solarfocus" in "Explore & Download Repositories")
    - Select latest version or `master`
- Restart Home Assistant to install all dependencies

### Manual

- Copy all files from `custom_components/solarfocus/` to `custom_components/solarfocus/` inside your config Home Assistant directory.
- Restart Home Assistant to install all dependencies

### Adding or enabling integration

Add custom integration using the web interface and follow instruction on screen.

- Go to `Configuration -> Integrations` and add "Solarfocus" integration
- Provide name for the device and it's IP-address
- Provide area where the heat pump is located
