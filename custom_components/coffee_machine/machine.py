"""State machine that infers what the coffee machine is doing from its smart plug."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACTIVITY_WINDOW,
    CONF_MIN_HEATING,
    CONF_POWER,
    CONF_SLEEP_TIMEOUT,
    CONF_SWITCH,
    CONF_THRESHOLD,
    CONF_WAKE_OFF,
    DEFAULT_ACTIVITY_WINDOW,
    DEFAULT_MIN_HEATING,
    DEFAULT_SLEEP_TIMEOUT,
    DEFAULT_THRESHOLD,
    DEFAULT_WAKE_OFF,
    DOMAIN,
    TOPUP_CHECK_GRACE_SECONDS,
    WAKE_GRACE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class MachineState(StrEnum):
    """Possible states of the coffee machine."""

    OFF = "off"  # smart plug is off
    WAKING = "waking"  # plug just switched on / power-cycled, waiting for heater
    HEATING = "heating"  # heater is drawing current
    READY = "ready"  # heater has stopped; sleep timer is counting down
    SLEEPING = "sleeping"  # plug on but machine has gone into standby


AWAKE_STATES = (MachineState.HEATING, MachineState.READY)


class CoffeeMachine:
    """Tracks the plug + current sensor and works out the machine's state.

    The sleep timer only runs while the machine is READY (heater off). Real
    heating (high current for at least ``min_heating``) cancels it, and it
    starts again from the full timeout when the heater stops.

    Shorter bursts are either thermostat top-ups or the heater recovering
    after you pull a shot or steam. They're told apart by timing: bursts
    within ``activity_window`` of the previous activity are use of the machine,
    and restart the countdown (the machine's own timer counts from last use).
    Isolated bursts are top-ups and are ignored. A sleeping machine also
    tops up now and then, so bursts never wake it; only real heating does.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        cfg = {**entry.data, **entry.options}

        self.name: str = entry.title
        self.switch_entity: str = cfg[CONF_SWITCH]
        self.power_entity: str = cfg[CONF_POWER]
        self.threshold = float(cfg.get(CONF_THRESHOLD, DEFAULT_THRESHOLD))
        self.sleep_timeout = timedelta(
            minutes=float(cfg.get(CONF_SLEEP_TIMEOUT, DEFAULT_SLEEP_TIMEOUT))
        )
        self.wake_off_seconds = float(cfg.get(CONF_WAKE_OFF, DEFAULT_WAKE_OFF))
        self.min_heating = timedelta(
            seconds=float(cfg.get(CONF_MIN_HEATING, DEFAULT_MIN_HEATING))
        )
        self.activity_window = timedelta(
            seconds=float(cfg.get(CONF_ACTIVITY_WINDOW, DEFAULT_ACTIVITY_WINDOW))
        )

        self.state: MachineState = MachineState.OFF
        self.reading: float | None = None
        self.heating_since: datetime | None = None  # start of current heating phase
        self.ready_since: datetime | None = None  # when the heater last stopped
        self.sleep_at: datetime | None = None  # only set while READY

        self._toggling = False
        self._wake_expires: datetime | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._sleep_unsub: CALLBACK_TYPE | None = None
        self._grace_unsub: CALLBACK_TYPE | None = None
        self._burst_start: datetime | None = None  # start of an unconfirmed high run
        self._burst_unsub: CALLBACK_TYPE | None = None
        self._last_activity: datetime | None = None  # end of last heating/use

    # ------------------------------------------------------------------ public

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.name,
            manufacturer="Tim Gibson",
            model="Smart-plug coffee machine",
        )

    @property
    def is_awake(self) -> bool:
        return self.state in AWAKE_STATES

    def add_listener(self, update_callback: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.add(update_callback)
        return lambda: self._listeners.discard(update_callback)

    @callback
    def async_start(self) -> None:
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, [self.switch_entity, self.power_entity], self._handle_event
            )
        )
        self._evaluate(initial=True)

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_timers()

    @property
    def plug_available(self) -> bool:
        return self._switch_on() is not None

    @property
    def plug_on(self) -> bool:
        return bool(self._switch_on())

    async def async_turn_on(self) -> None:
        """Switch the smart plug on (the machine then heats up if its own switch is on)."""
        await self._call_switch("turn_on")

    async def async_turn_off(self) -> None:
        """Switch the smart plug off."""
        await self._call_switch("turn_off")

    async def async_wake(self) -> None:
        """Wake the machine by power-cycling the smart plug."""
        if self._toggling:
            return
        self._toggling = True
        self._enter_waking(dt_util.utcnow())
        self._notify()
        try:
            if self._switch_on():
                await self._call_switch("turn_off")
                await asyncio.sleep(self.wake_off_seconds)
            await self._call_switch("turn_on")
        finally:
            self._toggling = False
        self._evaluate()

    # ---------------------------------------------------------------- helpers

    async def _call_switch(self, service: str) -> None:
        await self.hass.services.async_call(
            "homeassistant", service, {ATTR_ENTITY_ID: self.switch_entity}, blocking=True
        )

    def _switch_on(self) -> bool | None:
        state = self.hass.states.get(self.switch_entity)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        return state.state == STATE_ON

    def _read_power(self) -> float | None:
        state = self.hass.states.get(self.power_entity)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    @callback
    def _handle_event(self, event: Event) -> None:
        self._evaluate()

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ----------------------------------------------------------- state logic

    @callback
    def _evaluate(self, initial: bool = False) -> None:
        """Re-derive the state from the plug and current sensor."""
        if self._toggling:
            # Ignore the plug bouncing off/on while we're waking it.
            return

        now = dt_util.utcnow()
        switch_on = self._switch_on()
        reading = self._read_power()
        if reading is not None:
            self.reading = reading

        if switch_on is False:
            self._go_to_rest(MachineState.OFF)
            self._notify()
            return

        if switch_on is None or reading is None:
            # Plug or sensor unavailable: keep the last known state.
            self._notify()
            return

        # Plug just came on (from the card, an automation, or the plug's button).
        if self.state == MachineState.OFF and not initial:
            self._enter_waking(now)

        if reading >= self.threshold:
            if self.state in (MachineState.OFF, MachineState.WAKING):
                # Plug just came on: this is definitely a heat-up.
                self._start_heating(now)
            elif self.state in (MachineState.READY, MachineState.SLEEPING):
                self._high_while_idle(now)
        elif self._burst_start is not None:
            # A run ended before it counted as heating: it was a top-up.
            self._end_topup(now)
        elif self.state == MachineState.HEATING:
            self._start_ready(now)
        elif self.state == MachineState.READY:
            pass  # timer already running
        elif self.state == MachineState.WAKING:
            if self._wake_expires is None or now >= self._wake_expires:
                self._go_to_rest(MachineState.SLEEPING)
        else:
            # OFF on startup with plug on but no draw, or already SLEEPING.
            self._go_to_rest(MachineState.SLEEPING)

        self._notify()

    @callback
    def _high_while_idle(self, now: datetime) -> None:
        """High current while ready/asleep: heating only if it lasts long enough."""
        if self._burst_start is None:
            self._burst_start = now
            # Fallback in case the sensor stops reporting while the value is steady.
            self._burst_unsub = async_call_later(
                self.hass,
                self.min_heating.total_seconds() + TOPUP_CHECK_GRACE_SECONDS,
                self._burst_check,
            )
        elif now - self._burst_start >= self.min_heating:
            self._confirm_heating()

    @callback
    def _burst_check(self, _now: datetime) -> None:
        self._burst_unsub = None
        if (
            self._burst_start is not None
            and self.reading is not None
            and self.reading >= self.threshold
        ):
            self._confirm_heating()
            self._notify()

    @callback
    def _confirm_heating(self) -> None:
        started = self._burst_start or dt_util.utcnow()
        self._start_heating(started)

    @callback
    def _end_topup(self, now: datetime) -> None:
        started = self._burst_start
        self._clear_burst()
        if self.state != MachineState.READY:
            return  # bursts while asleep are standby top-ups: stay asleep
        if (
            self.activity_window.total_seconds() > 0
            and self._last_activity is not None
            and started is not None
            and started - self._last_activity <= self.activity_window
        ):
            # Follows closely on heating or another shot: you're using it.
            self._start_ready(now)
        elif self.sleep_at and now >= self.sleep_at:
            # The countdown ran out during this top-up.
            self._go_to_rest(MachineState.SLEEPING)
        # Otherwise an isolated top-up leaves the countdown alone.

    @callback
    def _clear_burst(self) -> None:
        self._burst_start = None
        if self._burst_unsub:
            self._burst_unsub()
            self._burst_unsub = None

    @callback
    def _enter_waking(self, now: datetime) -> None:
        self._cancel_timers()
        self.state = MachineState.WAKING
        self.heating_since = None
        self.ready_since = None
        self.sleep_at = None
        self._wake_expires = now + timedelta(seconds=WAKE_GRACE_SECONDS)
        self._grace_unsub = async_call_later(
            self.hass, WAKE_GRACE_SECONDS + 1, self._grace_expired
        )

    @callback
    def _start_heating(self, now: datetime) -> None:
        """Heater came on: cancel any sleep countdown."""
        self._cancel_timers()
        self.state = MachineState.HEATING
        self.heating_since = now
        self.ready_since = None
        self.sleep_at = None
        self._wake_expires = None

    @callback
    def _start_ready(self, now: datetime) -> None:
        """Heater stopped: start (or restart) the full sleep countdown."""
        self._cancel_timers()
        self.state = MachineState.READY
        self.heating_since = None
        self._last_activity = now
        self.ready_since = now
        self.sleep_at = now + self.sleep_timeout
        self._sleep_unsub = async_track_point_in_utc_time(
            self.hass, self._sleep_reached, self.sleep_at
        )

    @callback
    def _go_to_rest(self, state: MachineState) -> None:
        self._cancel_timers()
        self.state = state
        self.heating_since = None
        self.ready_since = None
        self.sleep_at = None
        self._wake_expires = None

    @callback
    def _sleep_reached(self, _now: datetime) -> None:
        self._sleep_unsub = None
        if self._burst_start is not None:
            # Heater is on right now; decide once we know if it's a top-up.
            return
        if self.state == MachineState.READY:
            self._go_to_rest(MachineState.SLEEPING)
            self._notify()

    @callback
    def _grace_expired(self, _now: datetime) -> None:
        self._grace_unsub = None
        self._evaluate()

    @callback
    def _cancel_timers(self) -> None:
        self._clear_burst()
        for attr in ("_sleep_unsub", "_grace_unsub"):
            unsub = getattr(self, attr)
            if unsub:
                unsub()
                setattr(self, attr, None)
