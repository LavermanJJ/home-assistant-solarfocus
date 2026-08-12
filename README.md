[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Installs][installs-shield]][installs]
[![Version](https://img.shields.io/github/v/tag/lavermanjj/home-assistant-solarfocus?style=for-the-badge&label=Version&color=orange)](https://img.shields.io/github/v/tag/lavermanjj/home-assistant-solarfocus?style=for-the-badge&label=Version&color=orange)
[![License](https://img.shields.io/github/license/lavermanjj/home-assistant-solarfocus?style=for-the-badge)](https://img.shields.io/github/license/lavermanjj/home-assistant-solarfocus?style=for-the-badge)


<p align="center">
  <a href="https://github.com/lavermanjj/home-assistant-solarfocus">
    <img src="https://brands.home-assistant.io/solarfocus/logo.png" alt="Logo" height="80">
  </a>
</p>

<h3 align="center">Home Assistant Solarfocus eco<sup>manager-touch</sup> integration</h3>

<p align="center">
  Custom component for integrating <a href="https://www.solarfocus.com/">Solarfocus</a> heating systems into Home Assistant.
</p>


<details open="open">
  <summary>Table of Contents</summary>

1. [About](#about)
2. [Home Assistant Device Types](#home-assistant-device-types)
3. [Supported Solarfocus Software and Hardware](#supported-solarfocus-software-and-hardware)
4. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [HACS Installation](#hacs-installation)
   - [Manual Installation](#manual-installation)
   - [Integration Setup](#integration-setup)
5. [Contribution](#contribution)
6. [Localization](#localization)
   
</details>


## About

This Home Assistant custom component is a community driven effort to integrate Solarfocus heating systems to Home Assistant allowing to monitor and control heat pumps, biomass boilers, domestic hot water, buffers, solar, and more. It is not affiliated, associated, authorized, endorsed by, or in any way officially connected with the [SOLARFOCUS GmbH](https://www.solarfocus.com/en/footer-bar/about-us).

> **Warning**
> Use with caution, in case of doubt check with Solarfocus or your installer if a feature / functionality (e.g. cooling) is supported by your installation to avoid damages to your heating system or the building.

The project uses the Python library [pysolarfocus](https://github.com/LavermanJJ/pysolarfocus) for retrieving values via Modbus TCP from the heating system.

## Home Assistant Device Types

There is currently support for the following device types within Home Assistant:

- Sensors
- Binary Sensors
- Numbers
- Buttons
- Selects
- Water Heater
- Climate


### Climate

The climate entity supports heating, cooling and switching the heating circuit off, and it
sets the flow temperature (_target temperature_) as well as the state (_preset_).

Section 6.2 of the Solarfocus Modbus specification requires all registers of a heating
circuit to be written together whenever the mode changes, otherwise the controller can end
up in an undefined state. Selecting a mode therefore writes:

| Mode | 32600 flow setpoint | 32602 cooling | 32603 operating mode | 32608 circuit mode |
|---|---|---|---|---|
| Heat | setpoint | 0 | preset | 2 (heating + cooling) |
| Cool | setpoint | 1 | preset | 2 (heating + cooling) |
| Off | 0 | 0 | 3 (off) | 2 (heating + cooling) |

The specification writes 0 (continuous operation) into 32603 for heating and cooling. The
integration keeps the preset you configured instead and only switches a circuit that is off
back on, so a comfort, eco or auto schedule is not discarded when you switch modes.

Because switching off writes a flow setpoint of 0, the integration remembers the last
setpoint per mode and restores it when the circuit is switched on again. It survives a
Home Assistant restart.

#### Cooling

> **Warning**
> Writing register 32602 **disables the dew point monitoring of the Solarfocus controller**.
> From then on the flow temperature has to be kept above the dew point of every room by
> Home Assistant. If it is not, condensate forms and can damage the building. A heat pump
> system that was not built for cooling can also be damaged. Check with Solarfocus or your
> installer whether cooling is supported by your installation before you use it.

Cooling is only offered from api version 22.090 on, as register 32608 does not exist below
it and the circuit cannot be switched to "heating + cooling" without it.

The integration does not calculate the dew point for you - it logs a warning the first time
a circuit is switched to cooling and otherwise leaves the responsibility with your
automations. The heating circuit exposes `room_temperature` and `humidity` sensors you can
build that on.

> **Warning**
> Feeding the external room humidity back to the heating system does **not** give you dew
> point protection. Per the specification, register 32607 "is only used for display in the
> visualization, the value is ignored for the dew point calculation". Active dew point
> monitoring means Home Assistant computing the dew point itself and driving the cooling
> flow setpoint (register 32600) accordingly, which is what the climate entity writes when
> you set its target temperature.

Note that the "outdoor shutdown temperature heating" parameter on the control panel stays
active for heating. If the outdoor temperature is above it, the circuit will not start
heating regardless of what is written over Modbus; set the parameter to 45°C to disable it.

![example](img/example.png)

### Photovoltaic

Next to the photovoltaic sensors read from the heating system, the integration provides `number` entities to feed the
heating system with values measured elsewhere in Home Assistant. This allows the eco<sup>manager-touch</sup> to optimize
the heating times and the consumption of self-produced electricity:

| Entity | Register | Description |
|---|---|---|
| `number.solarfocus_photovoltaic_smart_meter` | 33407 | Measured power at the house feed-in |
| `number.solarfocus_photovoltaic_photovoltaic` | 33408 | Generated power of the PV system |
| `number.solarfocus_photovoltaic_grid_im_export` | 33409 | Grid consumption (positive) / feed-in (negative) |
| `number.solarfocus_photovoltaic_hems_target_electrical_power` | 33415 | Target electrical power of the heat generator during PV overcharge (requires version `26.020`) |

Use an automation to forward the values of your own meters, e.g. on every state change of the corresponding sensor.

> **Important**
> The eco<sup>manager-touch</sup> rejects these values unless it is configured to accept them. In the _Photovoltaic_ mask
> of the display, set the source to `Modbus` and enter the IP address of your Home Assistant instance. Without this, all
> writes to these registers are ignored. It may take a moment until the transmitted values are shown on the display.

### External room sensors

A heating circuit can be fed with a room temperature and a room humidity measured elsewhere in
Home Assistant, so that a circuit without a Solarfocus room sensor can still be controlled:

| Entity | Register | Range | Description |
|---|---|---|---|
| `number.solarfocus_heating_circuit_1_indoor_temperature_external` | 32606 | 0 - 45 °C | Room temperature from an external controller |
| `number.solarfocus_heating_circuit_1_indoor_humidity_external` | 32607 | 0 - 100 % | Room humidity from an external controller |

Writing `0` is not a measurement of zero - the heating system then ignores the register and falls
back to its own sensor. Note that the humidity is only used for the display in the visualization
of the eco<sup>manager-touch</sup>, see the warning about the dew point under [Climate](#climate).

## Supported Solarfocus Software and Hardware

### Software

> **Important**
> This integration has been tested with Solarfocus eco<sup>manager-touch</sup> version `25.030`.

Supported versions: `21.140` - `26.020`. Features added in later versions are not yet supported.

The eco<sup>manager-touch</sup> Modbus TCP specification can be found [here](https://www.solarfocus.com/de/partnerportal/pdf/open/UGFydG5lcmJlcmVpY2gtREUvUmVnZWx1bmdfZWNvbWFuYWdlci10b3VjaC9BbmxlaXR1bmdlbi9lY29tYW5hZ2VyLXRvdWNoX01vZGJ1cy1UQ1AtUmVnaXN0ZXJkYXRlbl9BbmxlaXR1bmcucGRm/117920/0/Lng_YSxpM245S30zMTc4W2Y8cVRRXWlJVWRQJDsv?serialNumber=21010).

### Hardware

The eco<sup>manager-touch</sup> can integrate the following heating systems
- [Vamp<sup>air</sup>](https://www.solarfocus.com/en/products/air-source-heat-pump-vampair) heat pumps
- [Thermin<sup>nator</sup>](https://www.solarfocus.com/en/products/biomassheating) biomass boilers
- [Ecotop<sup>light</sup> / Ecotop<sup>zero</sup>](https://www.solarfocus.com/de/produkte/biomasseheizung/pelletkessel/ecotop) biomass boilers (_beta_)
- [Octo<sup>plus</sup>](https://www.solarfocus.com/en/products/biomassheating/pellet-boiler/octoplus) biomass boilers
- [pellet<sup>elegance</sup>](https://www.solarfocus.com/pelletelegance) biomass boilers (select ecotop)

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

Home Assistant v2024.1.2 or above.

### HACS Installation

You can find it in the default HACS repo. Just search `Solarfocus`.

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)


### Manual Installation

- Copy all files from `custom_components/solarfocus/` to `custom_components/solarfocus/` inside your config Home Assistant directory.
- Restart Home Assistant to install all dependencies

### Integration Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solarfocus) 

## Contribution

If you encounter issues or have any suggestions consider opening issues and contributing through PR. If you are ready to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md).

## Localization

Currently the integration supports the following languages:

- English
- German



[installs-shield]: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.solarfocus.total&style=for-the-badge&label=Installs&color=green
[installs]: https://analytics.home-assistant.io/custom_integrations.json
