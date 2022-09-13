# Home Assistant Sensor for Solarfocus eco<sup>_manager-touch_</sup>
Custom component for Home-Assistant to integrate [Solarfocus](https://www.solarfocus.com/) eco<sup>_manager-touch_</sup>

## Getting Started
### 1: Installation

#### Hacs

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

- Install [Home Assistant Community Store (HACS)](https://hacs.xyz/)
- Add custom repository https://github.com/lavermanjj/home-assistant-solarfocus to HACS
- Add integration repository (search for "Solarfocus" in "Explore & Download Repositories")
    - Select latest version or `master`
- Restart Home Assistant to install all dependencies

#### Manual

- Copy all files from `custom_components/solarfocus/` to `custom_components/solarfocus/` inside your config Home Assistant directory.
- Restart Home Assistant to install all dependencies

### 2: Adding or enabling integration

via [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solarfocus) 
> **Note**
> Requires `2021.3+`

#### or manual
 Add custom integration using the web interface and follow instruction on screen.

 - Go to `Configuration -> Integrations` and add "Senec" integration

Add custom integration using the web interface and follow instruction on screen.

- Go to `Configuration -> Integrations` and add "Solarfocus" integration
- Provide name for the device and it's IP-address
- Select components for which you would like to add the sensors
- Provide area where the heat pump is located

## What's Supported 

### Software Version

This integration has been tested with Solarfocus eco<sup>_manager-touch_</sup> version `21.040`.
[->Link to specification](https://www.solarfocus.com/de/partnerportal/pdf/open/UGFydG5lcmJlcmVpY2gtREUvUmVnZWx1bmdfZWNvbWFuYWdlci10b3VjaC9BbmxlaXR1bmdlbi9lY29tYW5hZ2VyLXRvdWNoX01vZGJ1cy1UQ1AtUmVnaXN0ZXJkYXRlbl9BbmxlaXR1bmcucGRm/117920/0/Lng_YSxpM245S30zMTc4W2Y8cVRRXWlJVWRQJDsv?serialNumber=21010)

### Solarfocus Components

| Components | Supported |
|---|---|
| Heating Circuit 1 (_Heizkreis_)| :white_check_mark: |
| Buffer 1 (_Puffer_) | :white_check_mark: |
| Solar (_Solar_)| :x:|
| Boiler 1 (_Boiler_) | :white_check_mark: |
| Heatpump (_Wärmepumpe_) | :white_check_mark: |
| Pelletsboiler (_Kessel_) | :white_check_mark: | 

> **Note**
> The number of supported Heating Circuits, Buffers, and Boilers could be extended in the future


### Provided Controls
<img src="images/sf-controls.png?raw=true" width="500">

<img src="images/sf-configuration.png?raw=true" width="500">

### Provided Services

<img src="images/sf-services.png?raw=true" width="500">

### Provided Sensors

#### Heating
<img src="images/sf-heating-sensors.png?raw=true" width="500">

#### Buffer
<img src="images/sf-buffer-sensors.png?raw=true" width="500">

#### Boiler
<img src="images/sf-boiler-sensors.png?raw=true" width="500">

#### Heatpump
<img src="images/sf-heatpump-sensors.png?raw=true" width="500">

#### Photovoltaic
<img src="images/sf-photovoltaic-sensors.png?raw=true" width="500">
