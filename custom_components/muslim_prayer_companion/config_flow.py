"""Config flow for Muslim Prayer Companion integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CALC_METHODS,
    CONF_CALC_METHOD,
    CONF_ENABLE_COUNTDOWN,
    CONF_ENABLE_HIJRI,
    CONF_IQAMAH_METHOD,
    CONF_IQAMAH_OFFSETS,
    CONF_LOCATION_NAME,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    CONFIG_VERSION,
    DEFAULT_CALC_METHOD,
    DEFAULT_ENABLE_COUNTDOWN,
    DEFAULT_ENABLE_HIJRI,
    DEFAULT_IQAMAH_METHOD,
    DEFAULT_IQAMAH_OFFSETS,
    DEFAULT_LOCATION_NAME,
    DOMAIN,
    IRELAND_CALC_METHODS,
    LOGGER,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
    STANDARD_CALC_METHODS,
)

# Source type options for step 1
SOURCE_TYPE_OPTIONS = {
    "calculated": "Calculate from coordinates",
    "ireland": "Ireland Mosque (ICCI, MCND, HICC, SDIC)",
}

# Location options for step 2
LOCATION_OPTIONS = {
    "home": "Use Home Assistant location",
    "custom": "Enter custom coordinates",
}


class MuslimPrayerCompanionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Muslim Prayer Companion.

    Supports multi-step configuration:
    1. Source type selection (calculated vs Ireland mosque)
    2. Location configuration
    3. Calculation method selection
    """

    VERSION = CONFIG_VERSION

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._source_type: str = SOURCE_CALCULATED

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 1: Source type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._source_type = user_input.get("source_type", SOURCE_CALCULATED)
            self._data[CONF_SOURCE_TYPE] = self._source_type

            if self._source_type == SOURCE_IRELAND:
                return await self.async_step_ireland()
            else:
                return await self.async_step_location()

        # Build form for source type selection
        schema = vol.Schema(
            {
                vol.Required(
                    "source_type", default=SOURCE_CALCULATED
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value="calculated", label="Calculate from coordinates"
                            ),
                            selector.SelectOptionDict(
                                value="ireland", label="Ireland Mosque API"
                            ),
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"description": "Choose how to get prayer times"},
        )

    async def async_step_ireland(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Ireland mosque selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            calc_method = user_input.get(CONF_CALC_METHOD)
            location_name = user_input.get(CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME)

            # Get coordinates from HA config (Ireland APIs don't need specific coords)
            self._data.update(
                {
                    CONF_CALC_METHOD: calc_method,
                    CONF_LOCATION_NAME: location_name,
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_TIMEZONE: str(self.hass.config.time_zone),
                    CONF_SOURCE_TYPE: SOURCE_IRELAND,
                }
            )

            return await self._create_entry()

        # Build Ireland mosque selection form
        ireland_options = [
            selector.SelectOptionDict(value=value, label=label)
            for label, value in IRELAND_CALC_METHODS.items()
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CALC_METHOD, default="ie-icci"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=ireland_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_LOCATION_NAME, default="Ireland Mosque"
                ): selector.TextSelector(),
            }
        )

        return self.async_show_form(
            step_id="ireland",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 2: Location configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            use_ha_location = user_input.get("use_ha_location", True)

            if use_ha_location:
                self._data[CONF_LATITUDE] = self.hass.config.latitude
                self._data[CONF_LONGITUDE] = self.hass.config.longitude
                self._data[CONF_LOCATION_NAME] = DEFAULT_LOCATION_NAME
            else:
                self._data[CONF_LATITUDE] = user_input.get(CONF_LATITUDE)
                self._data[CONF_LONGITUDE] = user_input.get(CONF_LONGITUDE)
                self._data[CONF_LOCATION_NAME] = user_input.get(
                    CONF_LOCATION_NAME, "Custom Location"
                )

            self._data[CONF_TIMEZONE] = str(self.hass.config.time_zone)

            return await self.async_step_method()

        # Build location form
        schema = vol.Schema(
            {
                vol.Required(
                    "use_ha_location", default=True
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-90,
                        max=90,
                        step=0.0001,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-180,
                        max=180,
                        step=0.0001,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_LOCATION_NAME, default=DEFAULT_LOCATION_NAME
                ): selector.TextSelector(),
            }
        )

        return self.async_show_form(
            step_id="location",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_method(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step 3: Calculation method selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data[CONF_CALC_METHOD] = user_input.get(
                CONF_CALC_METHOD, DEFAULT_CALC_METHOD
            )
            return await self._create_entry()

        # Build calculation method form
        method_options = [
            selector.SelectOptionDict(value=value, label=label)
            for label, value in STANDARD_CALC_METHODS.items()
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_CALC_METHOD, default="isna"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=method_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="method",
            data_schema=schema,
            errors=errors,
        )

    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        location_name = self._data.get(CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME)

        LOGGER.debug("Creating entry with data: %s", self._data)

        return self.async_create_entry(
            title=f"Muslim Prayer Companion - {location_name}",
            data=self._data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MuslimPrayerCompanionOptionsFlow:
        """Get the options flow for this handler."""
        return MuslimPrayerCompanionOptionsFlow(config_entry)


class MuslimPrayerCompanionOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Muslim Prayer Companion."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        source_type = self.config_entry.data.get(CONF_SOURCE_TYPE, SOURCE_CALCULATED)

        # Build options schema based on source type
        if source_type == SOURCE_IRELAND:
            method_options = [
                selector.SelectOptionDict(value=value, label=label)
                for label, value in IRELAND_CALC_METHODS.items()
            ]
        else:
            method_options = [
                selector.SelectOptionDict(value=value, label=label)
                for label, value in STANDARD_CALC_METHODS.items()
            ]

        current_method = self.config_entry.options.get(
            CONF_CALC_METHOD,
            self.config_entry.data.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD),
        )

        current_iqamah_method = self.config_entry.options.get(
            CONF_IQAMAH_METHOD, DEFAULT_IQAMAH_METHOD
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CALC_METHOD, default=current_method
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=method_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_IQAMAH_METHOD, default=current_iqamah_method
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value="offset", label="Use time offsets"
                            ),
                            selector.SelectOptionDict(
                                value="disabled", label="Disabled"
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_ENABLE_HIJRI,
                    default=self.config_entry.options.get(
                        CONF_ENABLE_HIJRI, DEFAULT_ENABLE_HIJRI
                    ),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_COUNTDOWN,
                    default=self.config_entry.options.get(
                        CONF_ENABLE_COUNTDOWN, DEFAULT_ENABLE_COUNTDOWN
                    ),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
