"""Binary sensor for the Coffee Machine integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoffeeMachineConfigEntry
from .entity import CoffeeMachineEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoffeeMachineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([CoffeeAwakeBinarySensor(entry.runtime_data)])


class CoffeeAwakeBinarySensor(CoffeeMachineEntity, BinarySensorEntity):
    """On while heating or ready."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, machine) -> None:
        super().__init__(machine, "awake")

    @property
    def is_on(self) -> bool:
        return self.machine.is_awake
