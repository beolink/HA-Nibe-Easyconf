"""Shared entity behaviour: naming, the description attribute, subscriptions."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, is_core_register, platform_for
from .coordinator import NibeCoordinator
from .descriptions import describe, friendly_name


class NibeRegisterEntity(CoordinatorEntity[NibeCoordinator]):
    """One Modbus register, presented as one entity.

    The generated description is attached as a state attribute rather than kept
    in a wiki somewhere: NIBE's own titles are service-manual shorthand, and a
    third of them are nothing but a component designation, so the explanation
    needs to travel with the entity.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NibeCoordinator,
        register: int,
        meta: dict,
        language: str = "sv",
    ) -> None:
        super().__init__(coordinator)
        self.register = register
        self.meta = meta
        self._language = language

        title = meta.get("title", str(register))
        self._attr_name = coordinator.entity_names.get(register) or friendly_name(
            title, language
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{register}"
        self._description = describe(title, register, meta, language)

        # Only the registers a normal installation cares about are on by
        # default; the rest exist but stay dormant until switched on.
        self._attr_entity_registry_enabled_default = is_core_register(title, meta)

        self._attr_device_info = device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.subscribe(self.register)
        # A newly enabled entity should not sit unavailable until the next tick.
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.unsubscribe(self.register)
        await super().async_will_remove_from_hass()

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.get(self.register) is not None
        )

    @property
    def native_value_raw(self) -> float | int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.register)

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        attributes: dict[str, str | int] = {
            "description": self._description,
            "modbus_register": self.register,
            "nibe_title": self.meta.get("title", ""),
        }
        if self.register in self.coordinator.discovery.unavailable:
            attributes["note"] = (
                "Registret finns i pumpen men rapporterar inget värde - "
                "givaren eller tillbehöret är troligen inte monterat."
                if self._language.startswith("sv")
                else "The register exists but reports no value - the sensor or "
                "accessory is probably not fitted."
            )
        return attributes


def async_add_register_entities(entry, platform: str, factory, async_add_entities) -> None:
    """Create one entity per discovered register that belongs on `platform`.

    Every platform module does the same thing, differing only in which entity
    class it builds, so the selection lives here.
    """
    coordinator: NibeCoordinator = entry.runtime_data
    language = entry.data.get("language", "sv")
    async_add_entities(
        factory(coordinator, register, coordinator.registers[register], language)
        for register in sorted(coordinator.discovery.present)
        if register in coordinator.registers
        and platform_for(coordinator.registers[register]) == platform
    )


def device_info(coordinator: NibeCoordinator) -> DeviceInfo:
    """The device card: exact model and size when the serial named them."""
    entry = coordinator.config_entry
    model = entry.data.get("model_label", "S-series")
    serial = coordinator.serial
    if serial is not None and serial.size:
        model = f"{model}-{serial.size}"
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="NIBE",
        model=model,
        # NIBE's article number: one per model, size and material variant.
        model_id=serial.article if serial is not None else None,
        serial_number=serial.serial if serial is not None else None,
        sw_version=str(coordinator.firmware) if coordinator.firmware else None,
        name=entry.title,
        configuration_url=f"http://{coordinator.client.host}",
    )
