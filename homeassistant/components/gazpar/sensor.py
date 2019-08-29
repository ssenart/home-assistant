"""Support for Gazpar."""
from datetime import timedelta
import json
import logging
import traceback

from pygazpar.client import Client
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL,
    ENERGY_KILO_WATT_HOUR, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval, call_later

_LOGGER = logging.getLogger(__name__)

CONF_WEBDRIVER = "webdriver"
CONF_TMPDIR = "tmpdir"
DEFAULT_SCAN_INTERVAL = timedelta(hours=4)
ICON_GAS = "mdi:fire"

HA_VOLUME_M3 = "m³"
HA_CONVERTOR_FACTOR_KWH_M3="kWh/m³"
HA_ATTRIBUTION = "Data provided by GrDF"
HA_TIME = "time"
HA_TIMESTAMP = "timestamp"
HA_TYPE = "type"

GAZPAR_LAST_START_INDEX = "start_index_m3"
GAZPAR_LAST_END_INDEX = "end_index_m3"
GAZPAR_LAST_VOLUME_M3 = "volume_m3"
GAZPAR_LAST_ENERGY_KWH = "energy_kwh"
GAZPAR_LAST_CONVERTER_FACTOR = "converter_factor"
GAZPAR_LAST_TEMPERATURE = "local_temperature"

HA_LAST_START_INDEX = "Gazpar last start index"
HA_LAST_END_INDEX = "Gazpar last end index"
HA_LAST_VOLUME_M3 = "Gazpar last volume"
HA_LAST_ENERGY_KWH = "Gazpar last energy"
HA_LAST_CONVERTER_FACTOR = "Gazpar last converter factor"
HA_LAST_TEMPERATURE = "Gazpar last temperature"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_WEBDRIVER): cv.string,
    vol.Required(CONF_TMPDIR): cv.string,
    vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Configure the platform and add the Gazpar sensor."""

    _LOGGER.debug("Initializing Gazpar platform...")

    try:
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]
        webdriver = config[CONF_WEBDRIVER]
        tmpdir = config[CONF_TMPDIR]
        scan_interval = config[CONF_SCAN_INTERVAL]

        account = GazparAccount(hass, username, password, webdriver, tmpdir, scan_interval)
        add_entities(account.sensors, True)
        _LOGGER.debug("Gazpar platform initialization has completed successfully")
    except BaseException:
        _LOGGER.error("Gazpar platform initialization has failed with exception : %s", traceback.format_exc())

class GazparAccount:
    """Representation of a Gazpar account."""

    def __init__(self, hass, username, password, webdriver, tmpdir, scan_interval):
        """Initialise the Gazpar account."""
        self._username = username
        self.__password = password
        self._webdriver = webdriver
        self._tmpdir = tmpdir
        self._scan_interval = scan_interval
        self._data = None
        self.sensors = []

        call_later(hass, 5, self.update_gazpar_data)

        self.sensors.append(
            GazparSensor(HA_LAST_START_INDEX, GAZPAR_LAST_START_INDEX, HA_VOLUME_M3, self))
        self.sensors.append(
            GazparSensor(HA_LAST_END_INDEX, GAZPAR_LAST_END_INDEX, HA_VOLUME_M3, self))
        self.sensors.append(
            GazparSensor(HA_LAST_VOLUME_M3, GAZPAR_LAST_VOLUME_M3, HA_VOLUME_M3, self))
        self.sensors.append(
            GazparSensor(HA_LAST_ENERGY_KWH, GAZPAR_LAST_ENERGY_KWH, ENERGY_KILO_WATT_HOUR, self))
        self.sensors.append(
            GazparSensor(HA_LAST_CONVERTER_FACTOR, GAZPAR_LAST_CONVERTER_FACTOR, HA_CONVERTOR_FACTOR_KWH_M3, self))
        self.sensors.append(
            GazparSensor(HA_LAST_TEMPERATURE, GAZPAR_LAST_TEMPERATURE, TEMP_CELSIUS, self))

        track_time_interval(hass, self.update_gazpar_data, self._scan_interval)

    def update_gazpar_data(self, event_time):
        """Fetch new state data for the sensor."""

        _LOGGER.debug("Querying PyGazpar library for new data...")

        try:
            client = Client(self._username, self.__password, self._webdriver, 30, self._tmpdir)
            client.update()
            self._data = client.data()
            _LOGGER.debug(json.dumps(self._data, indent=2))
            for sensor in self.sensors:
                sensor.async_schedule_update_ha_state(True)
                _LOGGER.debug("HA notified that new data is available")
            _LOGGER.debug("New data have been retrieved successfully from PyGazpar library")
        except BaseException:
            _LOGGER.error("Failed to query PyGazpar library with exception : %s", traceback.format_exc())

    @property
    def username(self):
        """Return the username."""
        return self._username

    @property
    def webdriver(self):
        """Return the webdriver."""
        return self._webdriver

    @property
    def tmpdir(self):
        """Return the tmpdir."""
        return self._tmpdir

    @property
    def data(self):
        """Return the data."""
        return self._data

class GazparSensor(Entity):
    """Representation of a sensor entity for Linky."""

    def __init__(self, name, identifier, unit, account: GazparAccount):
        """Initialize the sensor."""
        self._name = name
        self._identifier = identifier
        self._unit = unit
        self.__account = account
        self._username = account.username
        self.__time = None
        self.__timestamp = None
        self.__measure = None
        self.__type = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.__measure

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_GAS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: HA_ATTRIBUTION,
            HA_TIME: self.__time,
            HA_TIMESTAMP: self.__timestamp,
            HA_TYPE: self.__type,
            CONF_USERNAME: self._username
        }

    def update(self):
        """Retrieve the new data for the sensor."""

        _LOGGER.debug("HA requests its data to be updated...")
        try:
            if self.__account.data is not None:
                data = self.__account.data[-1]
                self.__measure = data[self._identifier]
                self.__time = data["date"]
                self.__timestamp = data["timestamp"]
                self.__type = data["type"]
                _LOGGER.debug("HA data have been updated successfully")
            else:
                _LOGGER.debug("No data available yet for update")
        except BaseException:
            _LOGGER.error("Failed to update HA data with exception : %s", traceback.format_exc())
