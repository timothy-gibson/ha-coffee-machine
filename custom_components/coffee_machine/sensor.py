"""Sensors for the Coffee Machine integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoffeeMachineConfigEntry
from .entity import CoffeeMachineEntity
from .machine import MachineState

STATE_ICONS = {
    MachineState.OFF: "mdi:power-plug-off-outline",
    MachineState.WAKING: "mdi:coffee-maker-outline",
    MachineState.HEATING: "mdi:coffee-maker",
    MachineState.READY: "mdi:coffee",
    MachineState.SLEEPING: "mdi:sleep",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoffeeMachineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    machine = entry.runtime_data
    async_add_entities([CoffeeStatusSensor(machine), CoffeeSleepAtSensor(machine)])


class CoffeeStatusSensor(CoffeeMachineEntity, SensorEntity):
    """off / waking / heating / ready / sleeping."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in MachineState]

    def __init__(self, machine) -> None:
        super().__init__(machine, "status")

    @property
    def native_value(self) -> str:
        return self.machine.state.value

    @property
    def icon(self) -> str:
        return STATE_ICONS.get(self.machine.state, "mdi:coffee-maker")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self.machine
        return {
            "heating_since": m.heating_since.isoformat() if m.heating_since else None,
            "ready_since": m.ready_since.isoformat() if m.ready_since else None,
            "sleep_at": m.sleep_at.isoformat() if m.sleep_at else None,
            "reading": m.reading,
            "threshold": m.threshold,
            "sleep_timeout_minutes": m.sleep_timeout.total_seconds() / 60,
            "plug_entity": m.switch_entity,
            "power_entity": m.power_entity,
        }


class CoffeeSleepAtSensor(CoffeeMachineEntity, SensorEntity):
    """When the machine will go to sleep (only set while ready)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-sand"

    def __init__(self, machine) -> None:
        super().__init__(machine, "sleep_at")

    @property
    def native_value(self) -> datetime | None:
        return self.machine.sleep_at
