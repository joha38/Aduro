"""Switch platform for Aduro Hybrid Stove integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STARTUP_STATES, SHUTDOWN_STATES
from .coordinator import AduroCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aduro switch entities."""
    coordinator: AduroCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = [
        AduroStartStopSwitch(coordinator, entry),
        AduroAutoShutdownSwitch(coordinator, entry),
        AduroAutoResumeAfterWoodSwitch(coordinator, entry),
    ]

    async_add_entities(switches)


class AduroSwitchBase(CoordinatorEntity, SwitchEntity):
    """Base class for Aduro switches."""

    def __init__(
        self,
        coordinator: AduroCoordinator,
        entry: ConfigEntry,
        switch_type: str,
        name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{switch_type}"
        self._attr_name = name
        self._switch_type = switch_type

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": f"Aduro {self.coordinator.stove_model}",
            "manufacturer": "Aduro",
            "model": f"Hybrid {self.coordinator.stove_model}",
            "sw_version": self.coordinator.entry.data.get("version", "Unknown"),
        }


class AduroStartStopSwitch(AduroSwitchBase):
    """Switch to start/stop the stove."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "power", "Power")
        self._attr_icon = "mdi:power"

    @property
    def is_on(self) -> bool:
        """Return true if stove is running."""
        if not self.coordinator.data or "operating" not in self.coordinator.data:
            return False
        
        current_state = self.coordinator.data["operating"].get("state")
        
        # Stove is "on" if in any startup/running state
        is_running = current_state in STARTUP_STATES
        
        # Log warning for unknown states
        if current_state and current_state not in STARTUP_STATES and current_state not in SHUTDOWN_STATES:
            _LOGGER.warning(
                "Unknown stove state %s - Cannot determine if stove is running. Assuming OFF. Please report this to the integration developer.",
                current_state
            )
            return False
        
        return is_running

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self.is_on:
            return "mdi:power-on"
        return "mdi:power-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "operating" not in self.coordinator.data:
            return {}
        
        current_state = self.coordinator.data["operating"].get("state", "unknown")
        
        # Get state description
        from .const import STATE_NAMES, SUBSTATE_NAMES
        
        state_desc = STATE_NAMES.get(current_state, f"State {current_state}")
        substate_desc = SUBSTATE_NAMES.get(current_state, "")
        
        return {
            "state": current_state,
            "state_description": state_desc,
            "substate_description": substate_desc,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the stove."""
        _LOGGER.info("Switch: Turning on stove")
        success = await self.coordinator.async_start_stove()
        
        if success:
            # Request immediate update
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Switch: Failed to turn on stove")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the stove."""
        _LOGGER.info("Switch: Turning off stove")
        success = await self.coordinator.async_stop_stove()
        
        if success:
            # Request immediate update
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Switch: Failed to turn off stove")


class AduroAutoShutdownSwitch(AduroSwitchBase):
    """Switch to enable/disable automatic shutdown at low pellet level."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "auto_shutdown", "Auto Shutdown at Low Pellets")
        self._attr_icon = "mdi:power-settings"

    @property
    def is_on(self) -> bool:
        """Return true if auto-shutdown is enabled."""
        if not self.coordinator.data or "pellets" not in self.coordinator.data:
            return False
        
        return self.coordinator.data["pellets"].get("auto_shutdown_enabled", False)

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self.is_on:
            return "mdi:shield-check"
        return "mdi:shield-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "pellets" not in self.coordinator.data:
            return {}
        
        pellets_data = self.coordinator.data["pellets"]
        
        return {
            "shutdown_level": pellets_data.get("shutdown_level", 5),
            "current_percentage": pellets_data.get("percentage", 0),
            "shutdown_alert": pellets_data.get("shutdown_alert", False),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto-shutdown."""
        _LOGGER.info("Switch: Enabling auto-shutdown at low pellet level")
        self.coordinator.set_auto_shutdown_enabled(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto-shutdown."""
        _LOGGER.info("Switch: Disabling auto-shutdown at low pellet level")
        self.coordinator.set_auto_shutdown_enabled(False)
        await self.coordinator.async_request_refresh()


class AduroAutoResumeAfterWoodSwitch(AduroSwitchBase):
    """Switch to enable/disable automatic resume after wood mode."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "auto_resume_wood", "Auto Resume After Wood Mode")
        self._attr_icon = "mdi:restart"

    @property
    def is_on(self) -> bool:
        """Return true if auto-resume is enabled."""
        # Access internal coordinator state
        return self.coordinator._auto_resume_after_wood

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self.is_on:
            return "mdi:replay"
        return "mdi:pause"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "in_wood_mode": self.coordinator._was_in_wood_mode,
        }
        
        # Add saved settings if available
        if self.coordinator._pre_wood_mode_operation_mode is not None:
            mode_names = {0: "Heat Level", 1: "Temperature", 2: "Wood"}
            attrs["saved_mode"] = mode_names.get(
                self.coordinator._pre_wood_mode_operation_mode, 
                "Unknown"
            )
            
        if self.coordinator._pre_wood_mode_heatlevel is not None:
            attrs["saved_heatlevel"] = self.coordinator._pre_wood_mode_heatlevel
            
        if self.coordinator._pre_wood_mode_temperature is not None:
            attrs["saved_temperature"] = self.coordinator._pre_wood_mode_temperature
        
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto-resume after wood mode."""
        _LOGGER.info("Switch: Enabling auto-resume after wood mode")
        self.coordinator.set_auto_resume_after_wood(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto-resume after wood mode."""
        _LOGGER.info("Switch: Disabling auto-resume after wood mode")
        self.coordinator.set_auto_resume_after_wood(False)
        await self.coordinator.async_request_refresh()
