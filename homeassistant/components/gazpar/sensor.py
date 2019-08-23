"""Support for Gazpar."""
from datetime import timedelta
import json
import logging

from pygazpar.client import Client
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL,
    ENERGY_KILO_WATT_HOUR)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval, call_later

_LOGGER = logging.getLogger(__name__)

CONF_WEBDRIVER = "webdriver"
CONF_TMPDIR = "tmpdir"
DEFAULT_SCAN_INTERVAL = timedelta(hours=4)
ICON_GAS = "mdi:fire"
CONSUMPTION = "daily_kWh"
TIME = "time"
INDEX_CURRENT = -1
INDEX_LAST = -2
ATTRIBUTION = "Data provided by GrDF"

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
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    webdriver = config[CONF_WEBDRIVER]
    tmpdir = config[CONF_TMPDIR]
    scan_interval = config[CONF_SCAN_INTERVAL]

    account = GazparAccount(hass, username, password, webdriver, tmpdir, scan_interval)
    add_entities(account.sensors, True)


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
            GazparSensor("Gazpar yesterday", self))

        track_time_interval(hass, self.update_gazpar_data, self._scan_interval)

    def update_gazpar_data(self, event_time):
        """Fetch new state data for the sensor."""
        client = Client(self._username, self.__password, self._webdriver, self._tmpdir)
        try:
            client.update()
            self._data = client.data
            _LOGGER.debug(json.dumps(self._data, indent=2))
            for sensor in self.sensors:
                sensor.async_schedule_update_ha_state(True)
                _LOGGER.debug("update event sent")
        except BaseException as exp:
            _LOGGER.error(exp)

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

    def __init__(self, name, account: GazparAccount):
        """Initialize the sensor."""
        self._name = name
        self.__account = account
        self._username = account.username
        self.__time = None
        self.__consumption = None
        self.__type = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.__consumption

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_GAS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            TIME: self.__time,
            CONF_USERNAME: self._username
        }

    def update(self):
        """Retrieve the new data for the sensor."""
        _LOGGER.debug("Sensor update() invoked")
        if self.__account.data is not None:
            data = self.__account.data[-1]
            self.__consumption = data[CONSUMPTION]
            self.__time = data[TIME]


