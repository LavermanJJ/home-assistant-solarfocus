# Modbus TCP register data — eco manager-touch

A transcription of the register documentation this integration is written
against. It is here because the same lookups are needed over and over: what a
register is called in German, which values a status can take, which component a
number belongs to, and whether anything reads it yet.

| | |
| --- | --- |
| Document | Regelung ecomanager-touch: Modbus TCP - Registerdaten |
| Version | **DR-0180-DE / v14-260212** |
| Source | <https://www.solarfocus.com/partnerbereich/ecomanager-touch_modbus-tcp_registerdaten_anleitung1.pdf> |
| Transcribed | 2026-08-16, 20 pages |
| Coverage | 102 of the 110 documented registers are read by the integration |

**Solarfocus is the authority, not this file.** It is a machine transcription of
a PDF, kept for looking things up quickly; where the two disagree the document
is right. The version above is the one it was taken from — if Solarfocus
publishes a newer one, this file is stale rather than wrong, and the version
line is what says so.

Redoing it means pulling the text out of the PDF, splitting each row at its type
column (`int16`, `uint16`, `int32`, `uint32`) into name and remark, rejoining
the words the layout breaks across lines, and keeping only the first instance of
each repeated component block. The `Gelesen als` column is joined on the address:
the base address of a `pysolarfocus` component plus the relative address of its
`DataValue` is the `Adr.` of the table.

## How to read it

- **Adr.** is the absolute register address of the *first* instance of a
  component. The note under each heading gives the stride to the others, so
  heating circuit 3 supply temperature is `1100 + 2 × 50 = 1200`.
- **Bezeichnung** is the German name from the `Bezeichnung` column, which is
  what the entity names in `translations/de.json` are taken from.
- **Gelesen als** is the `pysolarfocus` attribute the integration reads the
  register through, prefixed with the component the entity keys use — `hc` for
  the heating circuit, `bo` boiler, `bu` buffer, `hp` heat pump, `bb` biomass
  boiler, `pv` photovoltaic, `so` solar, `fm` fresh water module. A dash means
  the register is documented but nothing reads it.
- The value lists behind each status register are what the `state` sections of
  `strings.json` translate. Where a register documents a second enumeration at
  an offset of +200 (the therminator systems), both are in the list.

Input registers are read-only (`0x04`); holding registers are the ones that can
be written (`0x03` / `0x06`).

## Register

### Boiler — Input

_Boiler 1-4, +50 je Boiler (500, 550, 600, 650)_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 500 | Boiler – Temperatur | `int16` | `bo_temperature` |
| 501 | Boiler Status | `uint16` | `bo_state` |
| 502 | Boiler Freigabeart – Ist | `uint16` | `bo_mode` |

<details><summary><code>501</code> Boiler Status</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Boilerstatus nicht vorhanden |
| 1 | Bereitschaft |
| 2 | Laden |
| 3 | Frostschutz |
| 4 | Rauchfangkehrermodus |
| 5 | Legionellenschutz |
| 6 | Anforderung |
| 7 | Energiequelle zu heiß |
| 8 | Blockadeschutz |
| 9 | einmalige Freigabe aktiv |
| 10 | Fühler Kurzschluss |
| 11 | Fühler Unterbrechung |
| 12 | Ferienbetrieb |
| 13 | Defrost |
| 14 | Kühlen hat Vorrang |
| 15 | Heizen hat Vorrang |
| 16 | Sollbegrenzung wegen Wärmepumpenfehler |
| 200 | Trinkwasserspeicher ist nicht freigeschaltet |
| 201 | Bereitschaft |
| 202 | Trinkwasserspeicher wird beladen |
| 203 | Frostschutzbetrieb |
| 204 | Kaminkehrer |
| 205 | Legionellenschutzbetrieb |
| 206 | Trinkwasserspeicher fordert an |
| 207 | Wärmeableitung |
| 208 | Pumpentestlauf ist aktiv |
| 209 | Einmalladung |
| 210 | Trinkwasserspeicherfühler hat einen Kurzschluss! |
| 211 | Trinkwasserspeicherfühler hat eine Unterbrechung! |

</details>

<details><summary><code>502</code> Boiler Freigabeart – Ist</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Immer Aus |
| 1 | Immer Ein |
| 2 | Montag – Sonntag |
| 3 | Blockweise (Montag – Freitag, Samstag – Sonntag) |
| 4 | Tagweise |

</details>

### Frischwassermodul — Input

_Frischwassermodul 1-4, +25 je Modul_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 700 | Statuszeile | `uint16` | `fm_state` |
| 701 | WW-Vorlauftemperatur | `int16` | `fm_supply_temperature` |
| 702 | WW-Durchfluss | `int16` | `fm_flow_rate` |
| 703 | WW-Solltemperatur | `int16` | `fm_target_temperature` |
| 704 | Ventilstellung FWM Kaskade | `uint16` | `fm_valve` |

### Zirkulation — Input

_gehört zum Boiler, 1-4, +25 je Boiler_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 900 | Zirkulationstemperatur | `int16` | — |
| 901 | Zirkulationspumpe Ein/Aus | `uint16` | — |

### Heizkreis — Input

_Heizkreis 1-8, +50 je Heizkreis_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 1100 | Vorlauftemperatur | `int16` | `hc_supply_temperature` |
| 1101 | Raumtemperatur | `int16` | `hc_room_temperature` |
| 1102 | Feuchte | `int16` | `hc_humidity` |
| 1103 | Begrenzungsthermostat offen/geschlossen | `uint16` | `hc_limit_thermostat` |
| 1105 | Heizkreispumpe Ein/Aus | `uint16` | `hc_circulator_pump` |
| 1106 | Mischerstellung | `uint16` | `hc_mixer_valve` |
| 1107 | Status Heizkreis | `uint16` | `hc_state` |

<details><summary><code>1107</code> Status Heizkreis</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Heizkreis ist ausgeschaltet |
| 1 | Absenkbetrieb |
| 2 | Heizbetrieb |
| 3 | Ferienbetrieb |
| 4 | Estrichprogramm |
| 5 | Frostschutzbetrieb |
| 6 | Kaminkehrer |
| 7 | Heizkreis nicht freigeschaltet |
| 8 | Wärmeableitung |
| 9 | Außenabschalttemperatur Heizbetrieb erreicht |
| 10 | Raumsolltemperatur Heizbetrieb erreicht |
| 11 | Trinkwasserspeichervorrang ist aktiv |
| 12 | Dauerheizbetrieb |
| 13 | Dauerabsenkbetrieb |
| 14 | Aussenfühlerunterbrechung |
| 15 | min. Energiequellentemperatur unterschritten |
| 16 | Vorlauffühler defekt |
| 17 | min. Energiequellentemperatur unterschritten, Frostschutzbetrieb |
| 18 | Testlauf Pumpe ist aktiv |
| 19 | Partybetrieb |
| 20 | Begrenzungsthermostat ist offen |
| 21 | Pumpen Nachlauf |
| 22 | Defrost |
| 23 | Kühlbetrieb |
| 24 | Kühlen hat Vorrang |
| 25 | Heizen hat Vorrang |
| 26 | Pool hat Vorrang |
| 27 | Außenabschalttemperatur Absenkbetrieb erreicht |

</details>

### Puffer — Input

_Puffer 1-4, +20 je Puffer_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 1900 | Puffertemperatur oben | `int16` | `bu_top_temperature` |
| 1901 | Puffertemperatur unten | `int16` | `bu_bottom_temperature` |
| 1902 | Puffertemperatur X35 | `int16` | `bu_x35_temperature` |
| 1903 | Puffer – Ladepumpe | `int16` | `bu_pump` |
| 1904 | Pufferstatus | `uint16` | `bu_state` |
| 1905 | Puffer – Freigabeart | `uint16` | `bu_mode` |

<details><summary><code>1904</code> Pufferstatus</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Status nicht vorhanden |
| 1 | Bereitschaft |
| 2 | Puffer wird beladen |
| 3 | Frostschutzbetrieb |
| 4 | Kaminkehrer |
| 5 | Wärmeableitung |
| 6 | Testlauf Pumpe ist aktiv |
| 7 | Trinkwasserspeicher wird beladen |
| 8 | Sollbegrenzung wegen Wärmepumpenfehler |
| 200 | Puffer ist nicht freigeschaltet |
| 201 | Bereitschaft |
| 202 | Puffer wird beladen |
| 203 | Frostschutzbetrieb |
| 204 | Kaminkehrer |
| 205 | Wärmeableitung |
| 206 | Testlauf Pufferpumpe ist aktiv |
| 207 | Testlauf RLA -Pumpe ist aktiv |
| 208 | Puffer benötigt Energie |

</details>

<details><summary><code>1905</code> Puffer – Freigabeart</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Immer Aus |
| 1 | Immer Ein |
| 2 | Zeitschaltung |

</details>

### Solar — Input

_Solarkreis 1-4, +20 je Kreis_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 2100 | Kollektortemperatur 1 | `int16` | `so_collector_temperature_1` |
| 2101 | Kollektortemperatur 2 | `int16` | `so_collector_temperature_2` |
| 2102 | Kollektorvorlauftemperatur | `int16` | `so_collector_supply_temperature` |
| 2103 | Kollektorrücklauftemperatur | `int16` | `so_collector_return_temperature` |
| 2104 | Durchfluss WMZ | `int16` | `so_flow_heat_meter` |
| 2105 | aktuelle Leistung | `int16` | `so_current_power` |
| 2106 | Ertrag WMZ | `int32` | `so_current_yield_heat_meter` |
| 2108 | Tagesertrag | `int32` | `so_today_yield` |
| 2110 | Speicherfühler 1 | `int16` | `so_buffer_sensor_1` |
| 2111 | Speicherfühler 2 | `int16` | `so_buffer_sensor_2` |
| 2112 | Speicherfühler 3 | `int16` | `so_buffer_sensor_3` |
| 2113 | Solar – Statuszeile | `uint16` | `so_state` |
| 2114 | Relais O1 Ein/Aus | `uint16` | `so_relay_o1` |
| 2115 | Ansteuerung Out 1 | `uint16` | `so_control_out_1` |
| 2116 | Relais O2 Ein/Aus | `uint16` | `so_relay_o2` |
| 2117 | Ansteuerung Out 2 | `uint16` | `so_control_out_2` |

<details><summary><code>2113</code> Solar – Statuszeile</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Solarkreis in Betrieb |
| 1 | Kollektorfühler Kurzschluss |
| 2 | Solarkreis ausgeschaltet |
| 3 | Speicherfühler Kurzschluss |
| 4 | Speicherfühler Unterbrechung |
| 5 | Zirkulation überprüfen |
| 6 | Kollektorübertemperatur |
| 7 | Wartezeit |
| 8 | Messspülimpuls |
| 9 | Kollektortemperatur zu gering |
| 10 | maximale Speichertemperatur unten erreicht |
| 11 | Messzeit |
| 12 | keine Freigabe |
| 13 | Pumpen Nachlauf |
| 14 | Frostschutzbetrieb |
| 15 | Wärmeableitung |
| 16 | Speicherkühlung |
| 17 | Pumpentestlauf ist aktiv |
| 18 | Ausgangstest Solar |
| 201 | Kollektorfühler Kurzschluss! |
| 203 | Speicherfühler Kurzschluss! |
| 204 | Speicherfühler Unterbrechung! |
| 205 | Zirkulation überprüfen! |
| 206 | Kollektorübertemperatur! |
| 207 | Wartezeit |
| 208 | Messpülimpuls |

</details>

### Differenzregelmodul — Input

_Regelkreis 1-4, +10 je Modul_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 2200 | Relais Regelkreis 1 O1 Ein/Aus | `uint16` | — |
| 2201 | Temperatur 1 Regelkreis 1 | `int16` | — |
| 2202 | Temperatur 2 Regelkreis 1 | `int16` | — |
| 2203 | Relais Regelkreis 2 O2 Ein/Aus | `uint16` | — |
| 2204 | Temperatur 1 Regelkreis 2 | `int16` | — |
| 2205 | Temperatur 2 Regelkreis 2 | `int16` | — |

### Wärmepumpe — Input

_einmalig_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 2300 | Vorlauftemperatur Wärmepumpe | `int16` | `hp_supply_temperature` |
| 2301 | Rücklauftemperatur Wärmepumpe | `int16` | `hp_return_temperature` |
| 2302 | Durchfluss | `int16` | `hp_flow_rate` |
| 2303 | Kompressordrehzahl | `int16` | `hp_compressor_speed` |
| 2304 | EVU – Lock aktiv | `uint16` | `hp_evu_lock_active` |
| 2306 | Defrost aktiv | `uint16` | `hp_defrost_active` |
| 2307 | Boilerladung | `uint16` | `hp_boiler_charge` |
| 2310 | Gesamtenergie thermisch Heizung + Trinkwassererwärmung | `int32` | `hp_thermal_energy_total` |
| 2312 | thermische Energie Trinkwassererwärmung | `int32` | `hp_thermal_energy_drinking_water` |
| 2314 | thermische Energie Heizung | `int32` | `hp_thermal_energy_heating` |
| 2316 | Gesamtenergie elektrisch Heizung + Trinkwassererwärmung | `int32` | `hp_electrical_energy_total` |
| 2318 | elektr. Energie Trinkwassererwärmung | `int32` | `hp_electrical_energy_drinking_water` |
| 2320 | elektr. Energie Heizung | `int32` | `hp_electrical_energy_heating` |
| 2322 | aktuell aufgenommene elektr. Leistung | `int16` | `hp_electrical_power` |
| 2323 | aktuelle thermische Leistung Kühlen | `int16` | `hp_thermal_power_cooling` |
| 2324 | aktuelle thermische Leistung Heizen | `int16` | `hp_thermal_power_heating` |
| 2326 | thermische Energie Kühlung | `int32` | `hp_thermal_energy_cooling` |
| 2328 | el. Energie Kühlung | `int32` | `hp_electrical_energy_cooling` |
| 2330 | vampair Status | `uint16` | `hp_vampair_state` |

### Kessel (Biomasse) — Input

_einmalig_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 2400 | Kesseltemperatur | `int16` | `bb_temperature` |
| 2401 | Statuszeile Kessel | `uint16` | `bb_status` |
| 2402 | Betriebsminuten zum Wartungszeitpunkt | `int32` | `bb_time_of_operation_at_maintenance` |
| 2404 | Nachrichtennummer | `int16` | `bb_message_number` |
| 2405 | Türkontakt  offen/geschlossen | `int16` | `bb_door_contact` |
| 2406 | Kesselreinigung | `int16` | `bb_cleaning` |
| 2407 | Ascheboxfüllstand | `int16` | `bb_ash_container` |
| 2408 | Außentemperatur | `int16` | `hp_outdoor_temperature`, `bb_outdoor_temperature` |
| 2409 | Kesselbetriebsart therminator | `int16` | `bb_boiler_operating_mode` |
| 2410 | Sigmatek: octoplus: Speichertemperatur-Unten alle anderen Sigmatek Kessel (ohne vampair): Rücklauftemperatur Therminator: nicht belegt | `int16` | `bb_octoplus_buffer_temperature_bottom` |
| 2411 | SpeichertemperaturOben octoplus | `int16` | `bb_octoplus_buffer_temperature_top` |
| 2412 | Stückholz therminator | `uint16` | `bb_log_wood` |
| 2414 | Pelletverbrauch seit letzter Lagerraumbefüllung | `uint32` | `bb_pellet_usage_last_fill` |
| 2416 | Pelletverbrauch gesamt seit Update auf V21.050 oder jünger | `uint32` | `bb_pellet_usage_total` |
| 2418 | produzierte Wärmemenge gesamt seit Update auf V21.050 oder jünger | `uint32` | `bb_heat_energy_total` |
| 2420 | Kaminkehrer kurz vor Ende | `int16` | `bb_sweep_almost_done` |
| 2421 | Restsauerstoffgehalt | `uint16` | `bb_residual_oxygen_level` |
| 2422 | Rücklaufanhebungspumpe Ein/Aus | `uint16` | `bb_return_flow_booster_pump` |

<details><summary><code>2409</code> Kesselbetriebsart therminator</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Stückholz |
| 1 | Stückholz Automatik |
| 2 | Stückholz + Pellets |
| 3 | Stückholz Automatik + Pellets |
| 4 | Pellets |
| 5 | Hackgut |

</details>

### Photovoltaik — Input

_einmalig_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 2500 | Leistung PV | `int32` | `pv_power` |
| 2502 | Verbrauch | `int32` | `pv_house_consumption` |
| 2504 | Verbrauch WP | `int32` | `pv_heatpump_consumption` |
| 2506 | Netzbezug | `int32` | `pv_grid_import` |
| 2508 | Einspeisung | `int32` | `pv_grid_export` |
| 2510 | PV Überladung möglich | `int16` | `pv_overcharge_possible` |
| 2511 | PV-Überladung aktiv | `int16` | `pv_overcharge_active` |

### Boiler — Holding

_Boiler 1-8, +10 je Boiler_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 32000 | Boiler – Solltemperatur | `int16` | `bo_target_temperature` |
| 32001 | Boiler – Einmalladung | `int16` | `bo_single_charge` |
| 32002 | Boiler – Freigabeart | `int16` | `bo_holding_mode` |
| 32003 | Zirkulation 1 anfordern | `int16` | `bo_circulation` |

<details><summary><code>32002</code> Boiler – Freigabeart</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Immer Aus |
| 1 | Immer Ein |
| 2 | Montag – Sonntag |
| 3 | Blockweise (Montag – Freitag, Samstag – Sonntag) |
| 4 | Tagweise |

</details>

### Heizkreis — Holding

_Heizkreis 1-8, +20 je Heizkreis_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 32600 | Vorlaufsolltemperatur Heizen | `int16` | `hc_target_supply_temperature` |
| 32602 | Kühlen Ein/Aus | `int16` | `hc_cooling` |
| 32603 | Heizkreisbetriebsart | `int16` | `hc_mode` |
| 32605 | Raumtemperatur Soll | `int16` | `hc_target_room_temperature` |
| 32606 | Raumtemperatur Ist extern | `int16` | `hc_indoor_temperature_external` |
| 32607 | Raumfeuchte ist extern | `int16` | `hc_indoor_humidity_external` |
| 32608 | Heizkreismodus | `int16` | `hc_heating_mode` |

<details><summary><code>32603</code> Heizkreisbetriebsart</summary>

| Wert | Bedeutung |
| --- | --- |
| 0 | Dauerbetrieb |
| 1 | Absenkbetrieb |
| 2 | Automatik (Zeiteinstellung wird beachtet) |
| 3 | Heizkreis ausgeschaltet (nur Frostwache) |

</details>

<details><summary><code>32608</code> Heizkreismodus</summary>

| Wert | Bedeutung |
| --- | --- |
| 2 | Voraussetzung Raumeinfluss Ein/Gleitend + Kühfreigabe Ein |
| 0 | Heizen |
| 1 | Kühlen |
| 2 | Heizen+Kühlen V22.090 |

</details>

### Wärmepumpe, Kessel, Photovoltaik — Holding

_einmalig_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 33404 | EVU – Lock | `int16` | `hp_evu_lock` |
| 33405 | Betriebsart SG – Ready | `int16` | `hp_smart_grid` |
| 33406 | Außentemperatur extern | `int16` | `hp_outdoor_temperature_external`, `bb_outdoor_temperature_external` |
| 33410 | Kaminkehrerfunktion Start/Stopp | `int16` | `bb_sweep_function_start_stop` |
| 33411 | Kaminkehrer Messung verlängern | `int16` | `bb_sweep_function_extend` |
| 33412 | Pelletvorratslagerraum befüllt | `int16` | `bb_pellet_usage_reset` |
| 33415 | Elektrische Sollleistung HEMS (PV) | `int16` | `pv_hems_target_electrical_power` |

### Puffer — Holding

_Puffer 1-4, +10 je Puffer_

| Adr. | Bezeichnung | Typ | Gelesen als |
| --- | --- | --- | --- |
| 34000 | Puffertemperatur oben X44 extern | `int16` | `bu_external_top_temperature_x44` |
| 34001 | Puffertemperatur unten/Mitte X36 extern | `int16` | `bu_external_middle_temperature_x36` |
| 34002 | Puffertemperatur unten X35 extern | `int16` | `bu_external_bottom_temperature_x35` |
