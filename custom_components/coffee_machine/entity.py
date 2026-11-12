"""Base entity for the Coffee Machine integration."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity

from .machine import CoffeeMachine


class CoffeeMachineEntity(Entity):
    """Entity that re-renders whenever the machine's state changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, machine: CoffeeMachine, key: str) -> None:
        self.machine = machine
        self._attr_unique_id = f"{machine.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = machine.device_info

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.machine.add_listener(self.async_write_ha_state))
