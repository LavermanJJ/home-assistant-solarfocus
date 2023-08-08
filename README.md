[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Installs][installs-shield]][installs]
[![Version](https://img.shields.io/github/v/tag/lavermanjj/home-assistant-solarfocus?style=for-the-badge&label=Version&color=orange)](https://img.shields.io/github/v/tag/lavermanjj/home-assistant-solarfocus?style=for-the-badge&label=Version&color=orange)

<p align="center">
  <a href="https://github.com/leikoilja/ha-google-home">
    <img src="https://brands.home-assistant.io/solarfocus/logo.png" alt="Logo" height="80">
  </a>
</p>

<h3 align="center">Home Assistant Solarfocus eco<sup><i>manager-touch</i></sup> integration</h3>

<p align="center">
  Custom component for Home-Assistant to integrate [Solarfocus](https://www.solarfocus.com/) heating systems eco<sup><i>manager-touch</i></sup> and thermi<sup><i>nator</i></sup> II into Home Assistant.
</p>


<details open="open">
  <summary>Table of Contents</summary>

5. [About](#about)
1. [Home Assistant Device Types](#home-assistant-device-types)
2. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [HACS Installation](#hacs-installation)
   - [Manual Installation](#manual-installation)
   - [Integration Setup](#integration-setup)
3. [Contribution](#contribution)
4. [Localization](#localization)
5. [Credits](#credits)

</details>


## About

This Home Assistant custom component is not affiliated with the [SOLARFOCUS GmbH](https://www.solarfocus.com/en/footer-bar/about-us) but a community driven effort to integrate Solarfocus heating systems to Home Assistant allowing to monitor and control heat pumps, biomass boilers, domestic hot water, buffers, solar, and more. 

The project uses the Python library [pysolarfocus](https://github.com/LavermanJJ/pysolarfocus) for retrieving values via Modbus TCP from the heating system.

## Home Assistant Device Types

There is currently support for the following device types within Home Assistant:

- Sensors
- Binary Sensors
- Numbers
- Buttons
- Selects
- Water Heater

![image](images/sf-screenshot.png?raw=true)

## Supported Solarfocus Software and Hardware

### Software

This integration has been tested with Solarfocus eco<sup>_manager-touch_</sup> version `23.020`.
[->Link to specification](https://www.solarfocus.com/de/partnerportal/pdf/open/UGFydG5lcmJlcmVpY2gtREUvUmVnZWx1bmdfZWNvbWFuYWdlci10b3VjaC9BbmxlaXR1bmdlbi9lY29tYW5hZ2VyLXRvdWNoX01vZGJ1cy1UQ1AtUmVnaXN0ZXJkYXRlbl9BbmxlaXR1bmcucGRm/117920/0/Lng_YSxpM245S30zMTc4W2Y8cVRRXWlJVWRQJDsv?serialNumber=21010)

Supported versions: `21.140` - `23.020`. Features added in later versions are not yet supported.

### Hardware

The eco<sup>_manager-touch_</sup> can integrate the following heating systems
- [Vamp<sup>_air_</sup>](https://www.solarfocus.com/en/products/air-source-heat-pump-vampair) heat pumps
- [Thermin<sup>_nator_</sup>](https://www.solarfocus.com/en/products/biomassheating) biomass boilers
- Ecotop light biomass boilers (_in progress_)

| Components | Supported |
|---|---|
| Heating Circuit 1 - 8 (_Heizkreis_)| :white_check_mark: |
| Buffer 1 - 4 (_Puffer_) | :white_check_mark: |
| Solar (_Solar_)| :white_check_mark: |
| Boiler 1 - 4 (_Boiler_) | :white_check_mark: |
| Heat Pump (_Wärmepumpe_) | :white_check_mark: |
| Biomass Boiler (_Kessel_) | :white_check_mark: | 
| Fresh Water Module 1 - 4 (_Frischwassermodul_) | :white_check_mark: |

## Getting Started

### Prerequisites

Home Assistant v2023.1.2 or above.

### HACS Installation

You can find it in the default HACS repo. Just search `Solarfocus`.

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)


#### Manual Installation

- Copy all files from `custom_components/solarfocus/` to `custom_components/solarfocus/` inside your config Home Assistant directory.
- Restart Home Assistant to install all dependencies

### Integration Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solarfocus) 
> **Note**
> Requires `2021.3+`

## Contribution

If you encounter issues or have any suggestions consider opening issues and contributing through PR. If you are ready to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md).

## Localization

Currently the integration supports the following languages:

- English
- German



[installs-shield]: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.solarfocus.total&style=for-the-badge&label=Installs&color=green
[installs]: https://analytics.home-assistant.io/custom_integrations.json
