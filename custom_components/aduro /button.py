"""Button platform for Aduro Hybrid Stove integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AduroCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aduro button entities."""
    coordinator: AduroCoordinator = hass.data[DOMAIN][entry.entry_id]

    buttons = [
        AduroRefillPelletsButton(coordinator, entry),
        AduroCleanStoveButton(coordinator, entry),
        AduroToggleModeButton(coordinator, entry),
        AduroResumeAfterWoodButton(coordinator, entry),
        AduroForceAugerButton(coordinator, entry),
    ]

    async_add_entities(buttons)


class AduroButtonBase(CoordinatorEntity, ButtonEntity):
    """Base class for Aduro buttons."""

    def __init__(
        self,
        coordinator: AduroCoordinator,
        entry: ConfigEntry,
        button_type: str,
        name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{button_type}"
        self._attr_name = name
        self._button_type = button_type

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


class AduroRefillPelletsButton(AduroButtonBase):
    """Button to mark pellets as refilled."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry, "refill_pellets", "Refill Pellets")
        self._attr_icon = "mdi:reload"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "pellets" not in self.coordinator.data:
            return {}
        
        pellets = self.coordinator.data["pellets"]
        
        return {
            "consumed_before_refill": pellets.get("consumed", 0),
            "refill_counter": pellets.get("refill_counter", 0),
            "capacity": pellets.get("capacity", 0),
        }

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Button: Pellets refilled - resetting consumption counter")
        
        # Get current consumption before reset for logging
        consumed = 0
        if self.coordinator.data and "pellets" in self.coordinator.data:
            consumed = self.coordinator.data["pellets"].get("consumed", 0)
        
        # Reset pellet consumption
        self.coordinator.refill_pellets()
        
        _LOGGER.info(
            "Button: Consumption reset from %.1f kg, refill counter: %d",
            consumed,
            self.coordinator._refill_counter
        )
        
        # Request immediate update
        await self.coordinator.async_request_refresh()


class AduroCleanStoveButton(AduroButtonBase):
    """Button to mark stove as cleaned."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry, "clean_stove", "Clean Stove")
        self._attr_icon = "mdi:broom"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "pellets" not in self.coordinator.data:
            return {}
        
        pellets = self.coordinator.data["pellets"]
        
        return {
            "refills_before_clean": pellets.get("refill_counter", 0),
        }

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Button: Stove cleaned - resetting refill counter")
        
        # Get current counter before reset for logging
        counter = self.coordinator._refill_counter
        
        # Reset refill counter
        self.coordinator.reset_refill_counter()
        
        _LOGGER.info(
            "Button: Refill counter reset from %d to 0 after cleaning",
            counter
        )
        
        # Request immediate update
        await self.coordinator.async_request_refresh()


class AduroToggleModeButton(AduroButtonBase):
    """Button to toggle between heatlevel and temperature modes."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry, "toggle_mode", "Toggle Mode")

    @property
    def icon(self) -> str:
        """Return icon based on current state."""
        if not self.coordinator.data:
            return "mdi:help-circle"
        
        # Check if change is in progress
        if self.coordinator.data.get("calculated", {}).get("change_in_progress", False):
            return "mdi:sync-circle"
        
        # Icon based on current operation mode
        operation_mode = self.coordinator.data.get("status", {}).get("operation_mode", 0)
        
        if operation_mode == 0:
            return "mdi:fire"
        elif operation_mode == 1:
            return "mdi:thermometer"
        elif operation_mode == 2:
            return "mdi:campfire"
        
        return "mdi:help-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        
        operation_mode = self.coordinator.data.get("status", {}).get("operation_mode", 0)
        change_in_progress = self.coordinator.data.get("calculated", {}).get("change_in_progress", False)
        
        mode_names = {0: "Heat Level", 1: "Temperature", 2: "Wood"}
        current_mode = mode_names.get(operation_mode, "Unknown")
        next_mode = mode_names.get(1 if operation_mode == 0 else 0, "Unknown")
        
        return {
            "current_mode": current_mode,
            "will_switch_to": next_mode,
            "change_in_progress": change_in_progress,
        }

    async def async_press(self) -> None:
        """Handle button press."""
        if not self.coordinator.data:
            _LOGGER.error("Button: No data available to toggle mode")
            return
        
        current_mode = self.coordinator.data.get("status", {}).get("operation_mode", 0)
        mode_names = {0: "Heat Level", 1: "Temperature", 2: "Wood"}
        
        _LOGGER.info(
            "Button: Toggling mode from %s to %s",
            mode_names.get(current_mode, current_mode),
            mode_names.get(1 if current_mode == 0 else 0, "other")
        )
        
        success = await self.coordinator.async_toggle_mode()
        
        if success:
            _LOGGER.info("Button: Mode toggle initiated successfully")
            # Request immediate update
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Button: Failed to toggle mode")


class AduroResumeAfterWoodButton(AduroButtonBase):
    """Button to manually resume pellet operation after wood mode."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry, "resume_after_wood", "Resume After Wood Mode")
        self._attr_icon = "mdi:play-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "operating" not in self.coordinator.data:
            return {}
        
        current_state = self.coordinator.data["operating"].get("state", "")
        in_wood_mode = current_state in ["9", "14"]
        
        attrs = {
            "current_state": current_state,
            "in_wood_mode": in_wood_mode,
            "can_resume": in_wood_mode,
        }
        
        # Add saved settings if available
        if self.coordinator._pre_wood_mode_operation_mode is not None:
            mode_names = {0: "Heat Level", 1: "Temperature", 2: "Wood"}
            attrs["will_restore_mode"] = mode_names.get(
                self.coordinator._pre_wood_mode_operation_mode,
                "Unknown"
            )
        
        if self.coordinator._pre_wood_mode_heatlevel is not None:
            attrs["will_restore_heatlevel"] = self.coordinator._pre_wood_mode_heatlevel
        
        if self.coordinator._pre_wood_mode_temperature is not None:
            attrs["will_restore_temperature"] = self.coordinator._pre_wood_mode_temperature
        
        return attrs

    async def async_press(self) -> None:
        """Handle button press."""
        if not self.coordinator.data or "operating" not in self.coordinator.data:
            _LOGGER.error("Button: No data available to resume after wood mode")
            return
        
        current_state = self.coordinator.data["operating"].get("state", "")
        
        if current_state not in ["9", "14"]:
            _LOGGER.warning(
                "Button: Cannot resume - stove not in wood mode (current state: %s)",
                current_state
            )
            return
        
        _LOGGER.info("Button: Manually resuming pellet operation after wood mode")
        
        success = await self.coordinator.async_resume_after_wood_mode()
        
        if success:
            _LOGGER.info("Button: Resume initiated successfully")
            # Request immediate update
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Button: Failed to resume after wood mode")


class AduroForceAugerButton(AduroButtonBase):
    """Button to force the auger to run."""

    def __init__(self, coordinator: AduroCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry, "force_auger", "Force Auger")
        self._attr_icon = "mdi:cog-play"
        self._attr_entity_category = "config"

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Button: Forcing auger to run")
        
        success = await self.coordinator.async_force_auger()
        
        if success:
            _LOGGER.info("Button: Auger forced successfully")
            # Request immediate update
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Button: Failed to force auger")
