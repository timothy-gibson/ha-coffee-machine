"""Power switch for the Coffee Machine integration (controls the smart plug)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoffeeMachineConfigEntry
from .entity import CoffeeMachineEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoffeeMachineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([CoffeePowerSwitch(entry.runtime_data)])


class CoffeePowerSwitch(CoffeeMachineEntity, SwitchEntity):
    """Turns the smart plug on and off."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_icon = "mdi:power"

    def __init__(self, machine) -> None:
        super().__init__(machine, "power")

    @property
    def available(self) -> bool:
        return self.machine.plug_available

    @property
    def is_on(self) -> bool:
        return self.machine.plug_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.machine.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.machine.async_turn_off()
