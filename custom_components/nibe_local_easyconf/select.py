"""Writable registers with a documented set of values, and the heating mode."""

from __future__ import annotations

from dataclasses import asdict
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import heating_mode
from .const import PLATFORM_SELECT
from .entity import NibeRegisterEntity, async_add_register_entities, device_info
from .explanations import explain_own
from .storage import heating_mode_store

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_register_entities(entry, PLATFORM_SELECT, NibeSelect, async_add_entities)

    coordinator = entry.runtime_data
    register = heating_mode.offset_register(coordinator.registers, coordinator.discovery.present)
    if register is not None:
        async_add_entities(
            [
                NibeHeatingModeSelect(
                    coordinator,
                    register,
                    entry.data.get("language", "sv"),
                    heating_mode.steps_from(entry.options),
                    heating_mode_store(hass, entry.entry_id),
                )
            ]
        )


class NibeSelect(NibeRegisterEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, register, meta, language="sv") -> None:
        super().__init__(coordinator, register, meta, language)
        mappings: dict[str, str] = self._labels
        # NIBE's value tables are sparse (hot water mode is 0, 1, 2 and 4), so
        # the raw value is looked up rather than treated as an index.
        self._to_label = {int(key): label for key, label in mappings.items()}
        self._to_value = {label: value for value, label in self._to_label.items()}
        self._attr_options = list(self._to_value)

    @property
    def current_option(self) -> str | None:
        value = self.native_value_raw
        return None if value is None else self._to_label.get(int(value))

    async def async_select_option(self, option: str) -> None:
        if option not in self._to_value:
            raise HomeAssistantError(f"{option} is not a valid option for this register")
        await self.coordinator.async_write(self.register, self._to_value[option])


class NibeHeatingModeSelect(CoordinatorEntity, SelectEntity):
    """Blocked, eco, normal or boost, through the heat offset of climate system 1.

    The options are the ids an energy manager writes; the translations show
    them as words. heating_mode.py has what each mode writes and how an offset
    changed by hand is taken.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "heating_mode"
    _attr_options = list(heating_mode.MODES)
    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(
        self,
        coordinator,
        register: int,
        language: str,
        steps: dict[str, int],
        store: Store,
    ) -> None:
        super().__init__(coordinator)
        self.register = register
        meta = coordinator.registers[register]
        self._low = int(meta.get("min", -10))
        self._high = int(meta.get("max", 10))
        self._steps = steps
        self._store = store
        self._state: heating_mode.ModeState | None = None
        #: True while a mode is written, so its read-back is not taken for a
        #: change made by hand.
        self._writing = False
        self._language = language
        self._attr_name = "Värmeläge" if language.startswith("sv") else "Heating mode"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-heating_mode"
        self._attr_device_info = device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        # Loaded before the coordinator can call in, which would otherwise
        # learn normal from whatever mode the pump was left in.
        stored = await self._store.async_load()
        if stored and stored.get("mode") in heating_mode.MODES:
            self._state = heating_mode.ModeState(
                stored["mode"], int(stored["normal"]), int(stored["offset"])
            )
        await super().async_added_to_hass()
        self.coordinator.subscribe(self.register)
        self._follow_pump()
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.unsubscribe(self.register)
        await super().async_will_remove_from_hass()

    def _offset(self) -> int | None:
        data = self.coordinator.data
        value = None if data is None else data.get(self.register)
        return None if value is None else int(value)

    @callback
    def _follow_pump(self) -> None:
        """Take in an offset the pump has now, if it is not the one last seen."""
        offset = self._offset()
        if offset is None or self._writing:
            return
        if self._state is None:
            state = heating_mode.learn(offset)
        else:
            state = heating_mode.follow(self._state, offset)
        if state == self._state:
            return
        if self._state is not None:
            _LOGGER.info(
                "Heat offset changed to %s outside the heating mode select; "
                "mode %s, normal offset %s",
                offset,
                state.mode,
                state.normal,
            )
        self._state = state
        self._store.async_delay_save(self._data_to_store, 1)

    def _data_to_store(self) -> dict:
        return asdict(self._state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._follow_pump()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return super().available and self._state is not None and self._offset() is not None

    @property
    def current_option(self) -> str | None:
        return None if self._state is None else self._state.mode

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._state is None:
            return None
        return {
            "normal_offset": self._state.normal,
            "offsets": {
                mode: heating_mode.offset_for(
                    mode, self._state.normal, self._steps, self._low, self._high
                )
                for mode in heating_mode.MODES
            },
            "modbus_register": self.register,
            # As for every other control on the page: no explanation, no "i".
            "description": explain_own("heating_mode", self._language),
        }

    async def async_select_option(self, option: str) -> None:
        if option not in heating_mode.MODES:
            raise HomeAssistantError(f"{option} is not a heating mode")
        if self._state is None:
            raise HomeAssistantError("The heat offset has not been read from the pump yet")
        target = heating_mode.offset_for(
            option, self._state.normal, self._steps, self._low, self._high
        )
        self._writing = True
        try:
            await self.coordinator.async_write(self.register, target)
        finally:
            self._writing = False
        stored = self._offset()
        self._state = heating_mode.chosen(self._state, option, target if stored is None else stored)
        await self._store.async_save(asdict(self._state))
        self.async_write_ha_state()
