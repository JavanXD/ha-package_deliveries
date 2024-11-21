"""
The Package Deliveries custom component.

Copyright (c) 2024 Javan Rasokat

Licensed under MIT. All rights reserved.

"""

import logging
from homeassistant.helpers.entity_registry import async_get_registry

DOMAIN = "package_deliveries"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the Package Deliveries component."""

    async def handle_update_deliveries(call):
        """Handle the update deliveries service."""
        # Use the entity registry to retrieve the entity
        entity_registry = await async_get_registry(hass)
        entity = entity_registry.async_get("sensor.package_deliveries")
        
        if entity:
            sensor = hass.data[DOMAIN]["sensor_package_deliveries"]
            if sensor:
                await sensor.async_update_ha_state(force_refresh=True)
        else:
            _LOGGER.warning("Sensor 'sensor.package_deliveries' not found.")

    # Register the service
    hass.services.async_register(DOMAIN, "update_deliveries", handle_update_deliveries)

    # Store sensor reference for later use in the service
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass, config_entry):
    """Set up the Package Deliveries component from a config entry."""
    _LOGGER.info("Setting up Package Deliveries from configuration entry.")
    return True

async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    _LOGGER.info("Unloading Package Deliveries integration.")
    return True