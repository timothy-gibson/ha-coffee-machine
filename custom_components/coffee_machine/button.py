"""Wake button for the Coffee Machine integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoffeeMachineConfigEntry
from .entity import CoffeeMachineEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoffeeMachineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([CoffeeWakeButton(entry.runtime_data)])


class CoffeeWakeButton(CoffeeMachineEntity, ButtonEntity):
    """Power-cycles the smart plug so the machine starts heating again."""

    _attr_icon = "mdi:alarm"

    def __init__(self, machine) -> None:
        super().__init__(machine, "wake")

    async def async_press(self) -> None:
        await self.machine.async_wake()
