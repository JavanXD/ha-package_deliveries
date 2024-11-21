"""
The Package Deliveries custom component.

Copyright (c) 2024 Javan Rasokat

Licensed under MIT. All rights reserved.

"""

import logging

DOMAIN = "package_deliveries"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the Package Deliveries component."""
    async def handle_update_deliveries(call):
        """Handle the service call."""
        # You can trigger your sensor update here
        await hass.helpers.entity_component.async_update_entity("sensor.package_deliveries")

    hass.services.async_register(DOMAIN, "update_deliveries", handle_update_deliveries)

    return True

async def async_setup_entry(hass, config_entry):
    """Set up the Package Deliveries component from a config entry."""
    _LOGGER.info("Setting up Package Deliveries from configuration entry.")
    return True

async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    _LOGGER.info("Unloading Package Deliveries integration.")
    return True