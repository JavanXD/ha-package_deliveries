import logging
import subprocess
import json
import os
from datetime import timedelta
from homeassistant.helpers.entity import Entity

# Logging konfigurieren
_LOGGER = logging.getLogger(__name__)

MAX_EXECUTION_TIME = 60  # Maximale Ausführungsdauer des Skripts in Sekunden

class PackageDeliveriesSensor(Entity):
    """Sensor für die Verfolgung von Paketlieferungen per E-Mail."""

    def __init__(self, hass, config):
        """Initialisiere den Sensor."""
        self.hass = hass
        self._state = None
        self._attributes = {}
        self.config = config
        self.script_path = hass.config.path(
            "custom_components", "package_deliveries", "custom_scripts", "check_package_deliveries.py"
        )
        self.json_file_path = hass.config.path(
            "custom_components", "package_deliveries", "custom_scripts",
            f"deliveries_{self.config['name'].lower().replace(' ', '_')}.json"
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
        """Gibt den Namen des Sensors zurück."""
        return self._name

    @property
    def unique_id(self):
        """Gibt die eindeutige ID des Sensors zurück."""
        return self._unique_id

    @property
    def state(self):
        """Gibt die Anzahl der Lieferungen zurück."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Gibt zusätzliche Attribute zurück."""
        return self._attributes

    async def async_update(self):
        """Aktualisiert den Sensor asynchron durch Ausführen des Skripts und Laden des JSON-Ergebnisses."""
        await self.hass.async_add_executor_job(self._run_and_update_from_script)

    def _run_and_update_from_script(self):
        """Führt das Skript aus und aktualisiert den Sensor basierend auf der resultierenden JSON-Datei."""
        command = [
            "python3", self.script_path,
            "--email", self.config.get("email"),
            "--password", self.config.get("password"),
            "--imap_server", self.config.get("imap_server", "imap.gmail.com"),
            "--last_days", str(self.config.get("last_days", 10)),
            "--last_emails", str(self.config.get("last_emails", 50)),
            "--imap_folder", self.config.get("imap_folder", "INBOX"),
            "--output_file", self.json_file_path
        ]

        try:
            _LOGGER.info(f"Starting script execution with command: {command}")

            subprocess.run(
                command,
                check=True,
                timeout=MAX_EXECUTION_TIME,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            if os.path.exists(self.json_file_path):
                with open(self.json_file_path, "r") as json_file:
                    deliveries = json.load(json_file)
                    self._state = len(deliveries)
                    self._attributes["deliveries"] = deliveries
                    _LOGGER.info(f"Package deliveries updated: {len(deliveries)} deliveries found.")
            else:
                self._state = "error"
                self._attributes["error"] = f"{self.json_file_path} Datei nicht gefunden"
                _LOGGER.error(f"JSON file not found: {self.json_file_path}")

        except subprocess.TimeoutExpired as e:
            self._state = "unavailable"
            self._attributes["error"] = f"Skript-Zeitüberschreitung: {e}"
            _LOGGER.error(f"Script timed out after {MAX_EXECUTION_TIME} seconds: {e}")

        except subprocess.CalledProcessError as e:
            self._state = "error"
            self._attributes["error"] = f"Skriptfehler: {e}"
            _LOGGER.error(f"Script execution failed: {e}")

        except Exception as e:
            self._state = "error"
            self._attributes["error"] = str(e)
            _LOGGER.error(f"Unexpected error occurred: {e}")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Richtet die Sensorplattform ein."""
    if "name" not in config:
        raise ValueError("Das Feld 'name' ist für den package_deliveries-Sensor erforderlich.")

    sensor = PackageDeliveriesSensor(hass, config)
    async_add_entities([sensor], False)  # Verhindert sofortiges Update beim Setup

    # Optional: Async-Initialisierung im Hintergrund
    hass.loop.create_task(sensor.async_update())

    hass.data.setdefault("package_deliveries", {})
    hass.data["package_deliveries"][sensor.unique_id] = sensor
