"""
The Package Deliveries custom component.

Copyright (c) 2024 Javan Rasokat

Licensed under MIT. All rights reserved.

"""

import logging
import voluptuous as vol
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers import config_validation as cv

DOMAIN = "package_deliveries"
_LOGGER = logging.getLogger(__name__)

# Define the schema for the service
UPDATE_DELIVERIES_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
})


async def async_setup(hass, config):
    """Set up the Package Deliveries component."""

    async def handle_update_deliveries(call):
        """Handle the update deliveries service."""
        # Get the name of the sensor from the service call data
        sensor_name = call.data.get("name")
        if not sensor_name:
            _LOGGER.error("Service call missing required 'name' parameter.")
            return

        # Convert the sensor name into its unique ID
        unique_id = sensor_name.lower().replace(" ", "_")

        # Access the entity registry to find the sensor
        registry = async_get_entity_registry(hass)
        entity = registry.async_get(f"sensor.{unique_id}")

        if entity:
            # Retrieve the sensor from hass.data
            sensor = hass.data[DOMAIN].get(unique_id)
            if sensor:
                sensor.schedule_update_ha_state(force_refresh=True)
                _LOGGER.info(f"Updated sensor: {sensor_name}")
            else:
                _LOGGER.warning(f"Sensor '{sensor_name}' not found in hass.data.")
        else:
            _LOGGER.warning(f"Sensor '{sensor_name}' not found in the entity registry.")

    # Register the service with the correct schema
    hass.services.async_register(
        DOMAIN,
        "update_deliveries",
        handle_update_deliveries,
        schema=UPDATE_DELIVERIES_SCHEMA,
    )

    # Store sensor references for later use
    hass.data.setdefault(DOMAIN, {})
    return True