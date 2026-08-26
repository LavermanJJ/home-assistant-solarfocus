# Home Assistant Core changes relevant to `home-assistant-solarfocus`

Review of <https://developers.home-assistant.io/blog/> covering **August 2024 – August 2026**
(a few slightly older posts are included where the enforcement deadline falls inside that window).

Trigger for this review: [PR #164 "Fix Config-Flow in 2025.12"](https://github.com/LavermanJJ/home-assistant-solarfocus/pull/164).

Baseline reviewed: `main` @ `01e5a6b`, integration version `6.0.0`, `pysolarfocus==5.1.4`.
Note: the pinned dev environment (`.venv`) is on **Home Assistant 2025.1**, while the current HA dev
branch is **2026.9**. Several items below are already broken for users on current HA but invisible
in local test runs.

---

## 1. Breaking / already causing failures

### 1.1 `OptionsFlow.config_entry` must not be set manually
- **Post:** [2024-11-12 — New options flow properties](https://developers.home-assistant.io/blog/2024/11/12/options-flow)
- **Deadline:** warning until 2025.12, then hard failure. This is exactly what PR #164 hit.
- **What changed:** `OptionsFlow` gained `self.config_entry` and `self._config_entry_id` as
  built-in properties. Assigning `self.config_entry = config_entry` in `__init__` shadows the
  property and now raises.
- **Impact here:** `custom_components/solarfocus/config_flow.py`
  - `async_get_options_flow()` (~line 271) passes `config_entry` into the handler.
  - `SolarfocusOptionsFlowHandler.__init__` (~line 283) does `self.config_entry = config_entry`.
- **Fix:**
  ```python
  @staticmethod
  @callback
  def async_get_options_flow(
      config_entry: config_entries.ConfigEntry,
  ) -> config_entries.OptionsFlow:
      return SolarfocusOptionsFlowHandler()

  class SolarfocusOptionsFlowHandler(config_entries.OptionsFlow):
      def __init__(self) -> None:
          self._errors: dict[str, str] = {}
  ```
  Read options via `self.config_entry.options` directly (already done throughout
  `_show_init_form` / `async_step_init`). The locally cached `self.options` dict can go away, or
  be replaced with a `deepcopy` if mutation across steps is still wanted.

### 1.2 `WaterHeaterEntityEntityDescription` removed
- **Post:** [2024-12-13 — Changed name of WaterHeaterEntityDescription](https://developers.home-assistant.io/blog/2024/12/13/water-heater-entity-description)
- **Timeline:** renamed in 2025.1, old alias **removed in 2026.1**.
- **Impact here:** `custom_components/solarfocus/water_heater.py:11-16` still carries a
  `try/except ImportError` fallback to `WaterHeaterEntityEntityDescription`.
- **Fix:** delete the `try/except` and import `WaterHeaterEntityDescription` directly. Anything
  older than 2025.1 is out of support anyway.

### 1.3 Climate turn-on/off backwards-compat flag removed
- **Post:** [2024-01-24 — New entity features in Climate entity](https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded)
- **Timeline:** `_enable_turn_on_off_backwards_compatibility` served its purpose and was removed
  from core in 2025.1 (core PRs #132417/#132418/#132422).
- **Impact here:** `custom_components/solarfocus/climate.py:83` still sets
  `_enable_turn_on_off_backwards_compatibility = False`. Harmless today (it is just a dead class
  attribute) but should be dropped. `ClimateEntityFeature.TURN_ON | TURN_OFF` are already declared
  correctly on lines 84-89, so no behavioural change.
- **Also note:** `async_turn_on` / `async_turn_off` (lines 232-238) call
  `self.async_set_hvac_mode(...)` **without `await`** — the coroutine is never run. Not a core
  change, but it is in the same code the flag relates to.

---

## 2. Deprecated with a deadline

### 2.1 `PERCENTAGE` deprecated as a unit of measurement; new unit enums
- **Post:** [2026-06-30 — Introducing new unit enumerators](https://developers.home-assistant.io/blog/2026/06/30/new-unit-enumerators)
- **Effective:** 2026.7. Concentration constants removed in **2027.8**.
- **What changed:** new `UnitOfRatio` (`PARTS_PER_MILLION`, `PARTS_PER_BILLION`, `PERCENTAGE = "%"`)
  and `UnitOfDensity`. The bare `PERCENTAGE` constant is deprecated *when used as a unit of
  measurement* (the constant itself stays).
- **Impact here:**
  - `sensor.py` — `native_unit_of_measurement=PERCENTAGE` on humidity, mixer valve, modulation,
    pump, oxygen and similar entities.
  - `number.py:143` — humidity number entity.
- **Fix:** replace `PERCENTAGE` with `UnitOfRatio.PERCENTAGE` in
  `native_unit_of_measurement=` positions. `UnitOfDensity` is not used by this integration.

### 2.2 Advanced mode in data entry flows
- **Post:** [2026-05-26 — Deprecation of advanced mode in data entry flow](https://developers.home-assistant.io/blog/2026/05/26/advanced-mode-config-flow-deprecation)
- **Removal:** 2027.6.
- **Impact here:** none today — the config/options flow does not use `show_advanced_options`.
- **Why it is listed:** the options form is long (host, port, scan interval, API version, plus six
  component counters). If a future change tries to hide expert fields behind advanced mode, use
  form **sections** instead.

### 2.3 Config entry listener together with reloading methods in a config flow
- **Post:** [2026-05-07 — Deprecating config entry listener with reloading methods in config flow](https://developers.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods)
- **Timeline:** warning in 2026.6, **error in 2026.12**.
- **What changed:** having `entry.add_update_listener(...)` *and* a config flow that calls
  `async_update_reload_and_abort()` (or `_abort_if_unique_id_configured()` with
  `reload_on_update=True`) double-reloads the entry.
- **Impact here:** currently **not affected**. `__init__.py:82` registers an update listener, but
  the config flow uses plain `async_create_entry` and never calls a reloading method.
- **Watch out:** this becomes a hard error the moment a reconfigure flow is added (see 3.5). Pair
  any new reconfigure step with `async_update_and_abort()`, or drop the update listener.

### 2.4 Device registry: one config entry per device
- **Post:** [2026-07-21 — Devices are restricted to a single config entry and at most one subentry](https://developers.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry)
- **Released:** 2026.8. Compat shims until **2027.8**.
- **Deprecated:** `DeviceEntry.config_entries`, `config_entries_subentries`,
  `primary_config_entry`, `DeviceRegistry.async_get_device()`, the `via_device` parameter, and the
  config-entry-management kwargs of `async_update_device()`.
- **Impact here:** low — `entity.py` only returns a `DeviceInfo`-shaped dict and never touches the
  device registry API from the entity. The identifier used to be
  `{(DOMAIN, self.coordinator._entry.title)}`, i.e. keyed on the user-chosen entry *title*, which
  two entries of the same name would have made collide under the one-device-one-entry rule.
- **Done** in #210: entry version 9 keys the identifier off `entry.entry_id` and re-identifies the
  existing device in place, so it keeps its id, area and name override. Where an earlier rename had
  already built a second device, the migration removes the one the entities are not on — with
  `async_remove_device()` rather than the config-entry-management kwargs of
  `async_update_device()`, which this post deprecates.
- The entity `unique_id` was keyed on the title in the same way and is **done** in #212: entry
  version 10 rewrites it to `f"{entry_id}_{key}"` with `async_migrate_entries()`, and removes the
  entities an earlier rename left behind.

---

## 3. Recommended modernization (no hard deadline, but this is the current best practice)

### 3.1 Store runtime data on the config entry instead of `hass.data`
- **Post:** [2024-04-30 — Store runtime data inside the config entry](https://developers.home-assistant.io/blog/2024/04/30/store-runtime-data-inside-config-entry)
  and [2024-05-01 — Improved typing for hass.data](https://developers.home-assistant.io/blog/2024/05/01/improved-hass-data-typing)
- **Impact here:** `__init__.py` builds `hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]`, and
  every platform (`sensor.py`, `climate.py`, `number.py`, `select.py`, `switch.py`, `button.py`,
  `binary_sensor.py`, `water_heater.py`) reads it back. `async_unload_entry` has to pop it by hand.
- **Fix:**
  ```python
  type SolarfocusConfigEntry = ConfigEntry[SolarfocusDataUpdateCoordinator]

  async def async_setup_entry(hass, entry: SolarfocusConfigEntry) -> bool:
      ...
      entry.runtime_data = coordinator
  ```
  Platforms then use `config_entry.runtime_data`. `runtime_data` is cleaned up automatically, so
  the `hass.data` bookkeeping and the `DATA_COORDINATOR` constant can be deleted.

### 3.2 Pass `config_entry` explicitly to `DataUpdateCoordinator`
- **Source:** core issue [#128077](https://github.com/home-assistant/core/issues/128077); core
  deadline was 2025.11.
- **Impact here:** `coordinator.py:45-50` calls `super().__init__(hass, _LOGGER, name=..., update_interval=...)`
  without `config_entry`, so core falls back to the `current_entry` ContextVar.
- **Enforcement:** core sets `custom_integration_behavior=ReportBehavior.IGNORE`, and the source
  comment says *"It is not planned to enforce this for custom integrations."* So this will **not**
  break — but passing it explicitly removes a fragile ContextVar dependency and is a prerequisite
  for the coordinator storing `self.config_entry` reliably (the class already keeps its own
  `self._entry`, which becomes redundant).
- **Fix:** `super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=...)`.

### 3.3 Coordinator `_async_setup` and first-refresh handling
- **Posts:** [2024-08-05 — Set up your DataUpdateCoordinator with a setup method](https://developers.home-assistant.io/blog/2024/08/05/coordinator_async_setup),
  [2025-10-05 — Update coordinator now allows retriggering](https://developers.home-assistant.io/blog/2025/10/05/coordinator-retrigger),
  [2025-11-17 — Data Update Coordinator now supports Retry After](https://developers.home-assistant.io/blog/2025/11/17/retry-after-update-failed)
- **Impact here:**
  - `coordinator.py:33` calls the blocking `self.api.connect()` **inside `__init__`**, i.e. in the
    event loop. It belongs in `async _async_setup()`, which runs inside
    `async_config_entry_first_refresh()` and gets proper `ConfigEntryNotReady` /
    `ConfigEntryAuthFailed` handling.
  - `__init__.py:67-71` uses `await coordinator.async_refresh()` plus a manual
    `if not coordinator.last_update_success: raise ConfigEntryNotReady`. The supported pattern is
    `await coordinator.async_config_entry_first_refresh()`, which raises for you.
  - `_async_update_data` swallows failures into a debug log and returns `None`; it should
    `raise UpdateFailed(...)` so the coordinator marks entities unavailable. Since 2025.11
    `UpdateFailed(retry_after=<seconds>)` can also back off the next poll — useful when the
    Modbus TCP connection to the boiler drops.
  - Retriggering (2025.10): a refresh requested while one is in flight is now queued instead of
    dropped. Combined with `_attr_should_poll = True` on `SolarfocusEntity` (`entity.py:104`), which
    makes every entity call `async_request_refresh()` on its own poll cycle, this could produce
    noticeably more Modbus traffic than before. Coordinator-backed entities should set
    `should_poll = False`; consider using `CoordinatorEntity` instead of the hand-rolled listener
    in `async_added_to_hass`.

### 3.4 Icon translations instead of hardcoded `icon=`
- **Posts:** [2024-01-19 — Icon translations](https://developers.home-assistant.io/blog/2024/01/19/icon-translations),
  [2024-08-27 — Changes to the icon translations schema](https://developers.home-assistant.io/blog/2024/08/27/changed-icon-translations-schema)
- **Impact here:** roughly a hundred `icon="mdi:..."` entries across `sensor.py`, `number.py`,
  `select.py`, `switch.py`, `button.py`, `binary_sensor.py`. There is no `icons.json`.
- **Fix:** move icons into `custom_components/solarfocus/icons.json` keyed by
  `translation_key` — which the integration already generates in
  `entity.py:65-74`. This also unlocks state-based and (since 2025.5) range-based icons, e.g. a
  different icon per boiler state.
- **Related:** [2025-05-22 — Icon translations now support ranges](https://developers.home-assistant.io/blog/2025/05/22/range-based-icons).

### 3.5 Config flow unique ID
- **Post:** [2025-03-01 — New checks for config flow unique ID](https://developers.home-assistant.io/blog/2025/03/01/config-flow-unique-id)
- **What changed:** creating a config entry whose unique ID collides with an existing one now logs
  a warning instead of silently replacing the old entry; flows are expected to abort instead.
- **Impact here:** `ConfigFlow.async_step_user` never calls `async_set_unique_id`. Nothing stops a
  user from adding the same host/port twice, which then produces duplicate entities and (per 2.4)
  a device identifier collision.
- **Fix:** `await self.async_set_unique_id(f"{host}:{port}")` then `self._abort_if_unique_id_configured()`.
- **Related:** [2024-10-21 — New helpers and best practises for reauth and reconfigure flows](https://developers.home-assistant.io/blog/2024/10/21/reauth-reconfigure-helpers)
  and [2024-03-21 — Config Entries can now provide a reconfigure step](https://developers.home-assistant.io/blog/2024/03/21/config-entry-reconfigure-step).
  A reconfigure step is the modern replacement for using the options flow to change the host/port;
  if added, mind item 2.3.

### 3.6 Suggested display precision on sensors
- **Post:** [2025-05-26 — Sensor device classes now have default display precision](https://developers.home-assistant.io/blog/2025/05/26/sensor-default-display-precision)
- **What changed:** rounding during unit conversion was removed, so raw states now keep their full
  value. Core supplies a default precision per device class, but integrations are still expected to
  set `suggested_display_precision`.
- **Impact here:** no `suggested_display_precision` anywhere in `sensor.py`. Temperature and flow
  sensors will now display more decimals than before. Worth adding, especially after commit
  `82e0d56` changed the volume/flow-rate units.

### 3.7 Unit-of-measurement translations
- **Post:** [2024-11-21 — Translating units of measurement](https://developers.home-assistant.io/blog/2024/11/21/unit-of-measurement-translations)
- **Available since:** 2024.12.
- **Impact here:** any sensor with a non-standard unit (pellet mass/consumption, run hours, counts)
  can define `unit_of_measurement` under its entity key in `strings.json` rather than hardcoding a
  German/English string. Only relevant for the custom units; SI/`UnitOf*` values stay as they are.

### 3.8 Ship brand images locally
- **Post:** [2026-02-24 — Custom integrations can now ship their own brand images](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api)
- **Available since:** 2026.3.
- **What:** drop `brand/icon.png`, `brand/logo.png` (+ `dark_` and `@2x` variants) into
  `custom_components/solarfocus/`. No manifest change needed; local images beat the brands CDN.
- **Impact here:** there is no `brand/` folder, and the repo already carries artwork in `img/`.
  Cheap win for HACS users.

### 3.9 Config subentries
- **Post:** [2025-02-16 — Support for config subentries](https://developers.home-assistant.io/blog/2025/02/16/config-subentries),
  [2025-03-24 — Changes to ConfigSubentryFlow](https://developers.home-assistant.io/blog/2025/03/24/config-subentry-flow-changes)
- **Impact here:** speculative but a good architectural fit. Today the number of heating circuits
  (0-8), buffers, boilers, solar circuits (0-4) and fresh water modules is a bank of sliders in the
  options flow, with migrations needed every time the model changes (`async_migrate_entry` is
  already at version 6). Subentries would let each heating circuit / buffer / boiler be added and
  removed individually, and give each one its own device.

### 3.10 Config entry state transitions
- **Post:** [2025-02-19 — Changed config entry state transitions](https://developers.home-assistant.io/blog/2025/02/19/new-config-entry-states)
- **What changed:** new `UNLOAD_IN_PROGRESS` and `FAILED_UNLOAD` states; entries are removed from
  `hass.config_entries` *before* `async_remove_entry` runs.
- **Impact here:** `__init__.py:async_unload_entry` guards on `hass.data.get(DOMAIN)` and pops the
  entry manually. Moving to `runtime_data` (3.1) makes all of this disappear. Also,
  `async_reload_entry` (`__init__.py:105-108`) hand-rolls unload+setup instead of calling
  `hass.config_entries.async_reload(entry.entry_id)`, which bypasses the new state machine.

### 3.11 Integration quality scale
- **Post:** [2024-11-20 — Integration quality scale](https://developers.home-assistant.io/blog/2024/11/20/integration-quality-scale)
- **Tiers:** Bronze / Silver / Gold / Platinum, plus Legacy.
- **Impact here:** the scale is a core-integration gate and does not bind a HACS custom
  integration, but its rule list is the cleanest checklist for most of section 3 above
  (`runtime_data`, unique ID, `has_entity_name`, icon translations, strict typing, test coverage).
  Adding a `quality_scale.yaml` would be a way to track this work.

---

## 4. Reviewed and not applicable

Checked against the codebase and confirmed no impact:

| Post | Why not applicable |
|---|---|
| [2026-04-07 — Entity IDs with mismatched domains deprecated](https://developers.home-assistant.io/blog/2026/04/07/entity-id-mismatched-domain-deprecated) | The integration never sets `entity_id` manually; IDs are generated by the platform. |
| [2025-08-20 — Standardize encoding of μ in units](https://developers.home-assistant.io/blog/2025/08/20/micro-sign-encoding) | No micro-prefixed units anywhere in the codebase. |
| [2025-08-01 — `DeviceEntry.suggested_area` deprecated](https://developers.home-assistant.io/blog/2025/08/01/suggested-area-removed-from-deviceentry) | `device_info` does not set `suggested_area`. |
| [2025-07-31 — `result` removed from `FlowResult`](https://developers.home-assistant.io/blog/2025/07/31/result-removed-from-flowresult) | `config_flow.py` uses `FlowResult` only as a return annotation and never reads `.result`. Switching the annotation to `ConfigFlowResult` is a typing nicety, not a fix. |
| [2025-09-22 — Deprecate `hass` argument in service helpers](https://developers.home-assistant.io/blog/2025/09/22/deprecate-hass-argument-service-helpers) / [2025-09-25 — Entity services API](https://developers.home-assistant.io/blog/2025/09/25/entity-services-api-changes) | The integration registers no services or entity services. |
| [2025-01-15 — Relocate dhcp/ssdp/usb/zeroconf ServiceInfo models](https://developers.home-assistant.io/blog/2025/01/15/service-info) | No discovery. The empty `homekit`/`ssdp`/`zeroconf` keys in `manifest.json` do nothing and could be deleted. |
| [2025-10-16 — Recorder statistics API changes](https://developers.home-assistant.io/blog/2025/10/16/recorder-statistics-api-changes) | No external statistics are inserted. |
| [2025-11-25 — Store serialization opt-in](https://developers.home-assistant.io/blog/2025/11/25/storage-helper-opt-in-serialize-in-executor) | The storage helper is not used. |
| [2026-02-16 — `async_listen` in Labs deprecated](https://developers.home-assistant.io/blog/2026/02/16/labs-async-listen-deprecation) | Labs is not used. |
| [2026-05-13 — Condition and script API changes](https://developers.home-assistant.io/blog/2026/05/13/condition-script-api-changes) | No conditions or scripts are provided. |
| [2024-09-24 — Additional validation in Climate `set_temperature`](https://developers.home-assistant.io/blog/2024/09/24/climate-set-temp-validation) / [2024-07-24 — Climate min/max temperature check](https://developers.home-assistant.io/blog/2024/07/24/climate-min-max-temperature-check) | `climate.py` does not implement `async_set_temperature` (it is commented out) and does not declare `TARGET_TEMPERATURE`. Becomes relevant if that code is re-enabled — `min_temp`/`max_temp` are already implemented, so validation would pass. |
| Frontend component update posts (2026.4–2026.8), backup agents, media source, assist satellite, notify/lawn mower/vacuum/lock/cover/camera/light/fan platform posts | Wrong domains or frontend-only. |
| [2026-07-05 — Modernizing Modbus](https://developers.home-assistant.io/blog/2026/07/05/modernizing-modbus) | See note below. |

### Note on the Modbus post

[2026-07-05 — Modernizing Modbus](https://developers.home-assistant.io/blog/2026/07/05/modernizing-modbus)
introduces a `modbus_connection` integration and a backend-neutral `modbus-connection` PyPI library,
so several integrations can share one bus. That is directly on-topic for this integration, which
talks Modbus TCP to the Solarfocus controller through `aiosolarfocus`.

**Do nothing yet.** The post explicitly says: *"If you are working on a device integration, hold off
on wiring it up to the `modbus_connection` integration described below — we will share the updated
approach here soon."* Worth tracking for a future `aiosolarfocus` change, since a shared connection
would fix the case where a user runs both this integration and the core `modbus` integration against
the same controller.

---

## 5. Suggested order of work

1. **1.1** OptionsFlow `config_entry` — merge PR #164 (users on 2025.12+ are broken now).
2. **1.2 / 1.3** Delete the dead `WaterHeaterEntityEntityDescription` fallback and the
   `_enable_turn_on_off_backwards_compatibility` flag; fix the un-awaited `async_set_hvac_mode`.
3. **3.1** Move to `entry.runtime_data` — this is the change that unblocks 3.10 and most quality
   scale rules, and touches every platform file once.
4. **3.2 / 3.3** Coordinator cleanup: pass `config_entry`, move `api.connect()` into `_async_setup`,
   use `async_config_entry_first_refresh()`, raise `UpdateFailed`, turn off entity polling.
5. **3.5 + 2.4** Add a config flow unique ID and key the device identifier off `entry_id`. Both
   done: the unique id in #185 (entry version 7), the device identifier in #210 (entry version 9),
   the entity unique id in #212 (entry version 10).
6. **2.1** Swap `PERCENTAGE` for `UnitOfRatio.PERCENTAGE`.
7. **3.4 / 3.6 / 3.7 / 3.8** Polish: `icons.json`, `suggested_display_precision`, unit translations,
   `brand/` images.
8. **3.9** Consider config subentries as the long-term answer to the component-count sliders.
