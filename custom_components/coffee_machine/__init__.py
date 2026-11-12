"""Coffee Machine integration: turns a smart plug + current sensor into a coffee machine."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import CARD_FILENAME, CARD_URL, DOMAIN
from .machine import CoffeeMachine

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type CoffeeMachineConfigEntry = ConfigEntry[CoffeeMachine]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> None | bool:
    """Serve the dashboard card and load it on every dashboard automatically."""
    if hass.http is not None:
        card_path = Path(__file__).parent / "www" / CARD_FILENAME
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(card_path), False)]
        )
        # The version comes from manifest.json; it busts the browser cache on upgrade.
        integration = await async_get_integration(hass, DOMAIN)
        add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CoffeeMachineConfigEntry) -> bool:
    machine = CoffeeMachine(hass, entry)
    entry.runtime_data = machine

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    machine.async_start()

    entry.async_on_unload(machine.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoffeeMachineConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: CoffeeMachineConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
