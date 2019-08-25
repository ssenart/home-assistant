"""Support for VeoliaIDF."""
from datetime import timedelta
import json
import logging
import traceback

from pyveoliaidf.client import Client
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL,
    VOLUME_LITERS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval, call_later

_LOGGER = logging.getLogger(__name__)

CONF_WEBDRIVER = "webdriver"
CONF_TMPDIR = "tmpdir"
DEFAULT_SCAN_INTERVAL = timedelta(hours=4)
ICON_WATER = "mdi:water"
DAILY_LITER_CONSUMPTION = "daily_liter"
TOTAL_LITER_CONSUMPTION = "total_liter"
TIME = "time"
TYPE = "type"
ATTRIBUTION = "Data provided by VeoliaIDF"

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
    """Configure the platform and add the Linky sensor."""

    _LOGGER.debug("Initializing VeoliaIDF platform...")

    try:
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]
        webdriver = config[CONF_WEBDRIVER]
        tmpdir = config[CONF_TMPDIR]
        scan_interval = config[CONF_SCAN_INTERVAL]

        account = VeoliaIDFAccount(hass, username, password, webdriver, tmpdir, scan_interval)
        add_entities(account.sensors, True)
        _LOGGER.debug("VeoliaIDF platform initialization has completed successfully")
    except BaseException:
        _LOGGER.error("VeoliaIDF platform initialization has failed with exception : %s", traceback.format_exc())

class VeoliaIDFAccount:
    """Representation of a VeoliaIDF account."""

    def __init__(self, hass, username, password, webdriver, tmpdir, scan_interval):
        """Initialise the VeoliaIDF account."""
        self._username = username
        self.__password = password
        self._webdriver = webdriver
        self._tmpdir = tmpdir
        self._scan_interval = scan_interval
        self._data = None
        self.sensors = []

        call_later(hass, 5, self.update_veolia_data)

        self.sensors.append(
            VeoliaIDFSensor("Veolia yesterday liter", DAILY_LITER_CONSUMPTION, VOLUME_LITERS, self))
        self.sensors.append(
            VeoliaIDFSensor("Veolia total liter", TOTAL_LITER_CONSUMPTION, VOLUME_LITERS, self))

        track_time_interval(hass, self.update_veolia_data, self._scan_interval)

    def update_veolia_data(self, event_time):
        """Fetch new state data for the sensor."""

        _LOGGER.debug("Querying PyVeoliaIDF library for new data...")

        try:
            client = Client(self._username, self.__password, self._webdriver, self._tmpdir)
            client.update()
            self._data = client.data
            _LOGGER.debug(json.dumps(self._data, indent=2))
            for sensor in self.sensors:
                sensor.async_schedule_update_ha_state(True)
                _LOGGER.debug("HA notified that new data is available")
            _LOGGER.debug("New data have been retrieved successfully from PyVeoliaIDF library")
        except BaseException:
            _LOGGER.error("Failed to query PyVeoliaIDF library with exception : %s", traceback.format_exc())

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


class VeoliaIDFSensor(Entity):
    """Representation of a sensor entity for Linky."""

    def __init__(self, name, identifier, unit, account: VeoliaIDFAccount):
        """Initialize the sensor."""
        self._name = name
        self._identifier = identifier
        self._unit = unit
        self.__account = account
        self._username = account.username
        self.__time = None
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
        return ICON_WATER

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            TIME: self.__time,
            CONF_USERNAME: self._username,
            TYPE: self.__type
        }

    def update(self):
        """Retrieve the new data for the sensor."""

        _LOGGER.debug("HA requests its data to be updated...")
        try:
            if self.__account.data is not None:
                data = self.__account.data[-1]
                self.__measure = data[self._identifier]
                self.__time = data[TIME]
                self.__type = data[TYPE]
                _LOGGER.debug("HA data have been updated successfully")
            else:
                _LOGGER.debug("No data available yet for update")
        except BaseException:
            _LOGGER.error("Failed to update HA data with exception : %s", traceback.format_exc())

