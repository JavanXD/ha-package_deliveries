"""
The Package Deliveries custom component.

Copyright (c) 2024 Javan Rasokat

Licensed under MIT. All rights reserved.

"""

"""The Package Deliveries custom component."""

import logging

DOMAIN = "package_deliveries"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the Package Deliveries component."""

    async def handle_update_deliveries(call):
        """Handle the update deliveries service."""
        # Use Home Assistant's entity registry to find the sensor
        registry = await hass.helpers.entity_registry.async_get(hass)
        entity = registry.async_get("sensor.package_deliveries")

        if entity:
            # Retrieve the sensor from hass.data
            sensor = hass.data[DOMAIN].get("sensor_package_deliveries")
            if sensor:
                sensor.schedule_update_ha_state(force_refresh=True)
        else:
            _LOGGER.warning("Sensor 'sensor.package_deliveries' not found.")

    # Register the service
    hass.services.async_register(DOMAIN, "update_deliveries", handle_update_deliveries)

    # Store sensor references for later use
    hass.data.setdefault(DOMAIN, {})
    return True