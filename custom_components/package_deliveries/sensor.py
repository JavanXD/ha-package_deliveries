import datetime
from datetime import timedelta
from homeassistant.helpers.entity import Entity


class PackageDeliveriesSensor(Entity):
    """Sensor for tracking package deliveries via email."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self.hass = hass
        self._state = None
        self._attributes = {}
        self.config = config
        self.script_path = hass.config.path(
            "custom_components", "package_deliveries", "custom_scripts", "check_package_deliveries.py"
        )
        self.json_file_path = hass.config.path(
            "custom_components", "package_deliveries", "custom_scripts", f"deliveries_{self.config['name'].lower().replace(' ', '_')}.json"
        )
        scan_interval = config.get("scan_interval", 180)
        if isinstance(scan_interval, timedelta):
            self.scan_interval = scan_interval
        else:
            self.scan_interval = timedelta(seconds=int(scan_interval))

        self._unique_id = config["name"].lower().replace(" ", "_")
        self._name = config["name"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the number of deliveries."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return self._attributes

    def update(self):
        """Call the script, then update the sensor from the JSON file."""
        # Lazy imports to avoid blocking the event loop
        import subprocess
        import json
        import os

        # Build the command dynamically from the config
        command = [
            "python3", self.script_path,
            "--email", self.config.get("email"),
            "--password", self.config.get("password"),
            "--smtp_server", self.config.get("smtp_server", "imap.gmail.com"),
            "--last_days", str(self.config.get("last_days", 10)),
            "--last_emails", str(self.config.get("last_emails", 50)),
            "--imap_folder", self.config.get("imap_folder", "INBOX"),
            "--output_file", self.json_file_path
        ]

        try:
            # Step 1: Call the script
            subprocess.run(command, check=True)

            # Step 2: Read the JSON file to update the sensor state and attributes
            if os.path.exists(self.json_file_path):
                with open(self.json_file_path, "r") as json_file:
                    deliveries = json.load(json_file)
                    self._state = len(deliveries)
                    self._attributes["deliveries"] = deliveries
            else:
                self._state = "Error"
                self._attributes["error"] = f"{self.json_file_path} file not found"

        except subprocess.CalledProcessError as e:
            self._state = "Error"
            self._attributes["error"] = f"Script error: {e}"

        except Exception as e:
            self._state = "Error"
            self._attributes["error"] = str(e)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    # Ensure the "name" field is provided
    if "name" not in config:
        raise ValueError("The 'name' field is required for the package_deliveries sensor.")

    sensor = PackageDeliveriesSensor(hass, config)
    async_add_entities([sensor], True)

    # Store each sensor in `hass.data` for later reference
    hass.data.setdefault("package_deliveries", {})
    hass.data["package_deliveries"][sensor.unique_id] = sensor