"""Config, reconfigure and options flows for Muslim Prayer Companion."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv, selector
import voluptuous as vol

from .const import (
    CONF_CALC_METHOD,
    CONF_COUNTDOWN_FORMAT,
    CONF_ENABLED_GROUPS,
    CONF_FRIDAY_JUMUAH_1,
    CONF_FRIDAY_JUMUAH_2,
    CONF_FRIDAY_LABEL_1,
    CONF_FRIDAY_LABEL_2,
    CONF_FRIDAY_MOSQUES,
    CONF_FRIDAY_NAME,
    CONF_FRIDAY_SLUG,
    CONF_FRIDAY_SOURCE,
    CONF_HIJRI_ADJUSTMENT,
    CONF_HIJRI_CHANGE_AT_MAGHRIB,
    CONF_IMSAK_MINUTES,
    CONF_IQAMAH_API_URL,
    CONF_IQAMAH_METHOD,
    CONF_IQAMAH_OFFSETS,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_MOSQUE,
    CONF_PRAYER_WINDOW_MINUTES,
    CONF_SOURCE_TYPE,
    CONF_TIMEZONE,
    CONFIG_VERSION,
    COUNTDOWN_FORMATS,
    DEFAULT_CALC_METHOD,
    DEFAULT_LOCATION_NAME,
    DOMAIN,
    FRIDAY_SOURCE_MANUAL,
    IQAMAH_METHOD_API,
    IQAMAH_METHOD_DISABLED,
    IQAMAH_METHOD_MOSQUE,
    IQAMAH_METHOD_OFFSET,
    MAX_HIJRI_ADJUSTMENT,
    MAX_IMSAK_MINUTES,
    MAX_IQAMAH_OFFSET_MINUTES,
    MAX_PRAYER_WINDOW_MINUTES,
    MIN_HIJRI_ADJUSTMENT,
    PRAYERS,
    SENSOR_GROUPS,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
    SOURCE_TYPES,
    STANDARD_CALC_METHODS,
)
from .helpers.friday import (
    friday_item_from_input,
    seed_friday_mosques,
    validate_friday_item,
)
from .helpers.registry import MOSQUE_KEYS, MOSQUES, get_mosque, mosques_by_distance
from .helpers.settings import (
    Settings,
    default_iqamah_method,
    default_options,
    entry_unique_id,
)

STEP_USER = "user"
STEP_RECONFIGURE = "reconfigure"
STEP_IRELAND = "ireland"
STEP_LOCATION = "location"
STEP_METHOD = "method"

ERROR_INVALID_URL = "invalid_url"
ERROR_URL_REQUIRED = "url_required"
NEAREST_SHOWN = 3


def _select(options: list[str], translation_key: str, *, multiple: bool = False) -> Any:
    """Return a translated dropdown/list selector over fixed option values."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            mode=selector.SelectSelectorMode.LIST
            if multiple
            else selector.SelectSelectorMode.DROPDOWN,
            multiple=multiple,
            translation_key=translation_key,
        )
    )


def _number(minimum: float, maximum: float, step: float = 1, unit: str | None = None) -> Any:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


SOURCE_SCHEMA = vol.Schema(
    {vol.Required(CONF_SOURCE_TYPE): _select(list(SOURCE_TYPES), "source_type")}
)
METHOD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALC_METHOD, default=DEFAULT_CALC_METHOD): _select(
            STANDARD_CALC_METHODS, "calculation_method"
        )
    }
)


def _nearest_text(latitude: float, longitude: float) -> str:
    """Describe the nearest mosques for the form description."""
    nearest = mosques_by_distance(latitude, longitude)[:NEAREST_SHOWN]
    return ", ".join(f"{m.short_name} ({km:.1f} km)" for m, km in nearest)


class MuslimPrayerCompanionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup and reconfigure flows."""

    VERSION = CONFIG_VERSION

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}
        self._reconfigure = False

    # --- Step 1: source type ----------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose between calculated times and an Irish mosque."""
        if user_input is not None:
            return await self._async_route(user_input[CONF_SOURCE_TYPE])
        return self.async_show_form(
            step_id=STEP_USER,
            data_schema=self.add_suggested_values_to_schema(
                SOURCE_SCHEMA, {CONF_SOURCE_TYPE: SOURCE_CALCULATED}
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the source, mosque, location or method of an existing entry."""
        entry = self._get_reconfigure_entry()
        self._reconfigure = True
        if user_input is not None:
            return await self._async_route(user_input[CONF_SOURCE_TYPE])
        return self.async_show_form(
            step_id=STEP_RECONFIGURE,
            data_schema=self.add_suggested_values_to_schema(
                SOURCE_SCHEMA,
                {CONF_SOURCE_TYPE: entry.data.get(CONF_SOURCE_TYPE, SOURCE_CALCULATED)},
            ),
            description_placeholders={"location": entry.title},
        )

    async def _async_route(self, source_type: str) -> ConfigFlowResult:
        self._data = {CONF_SOURCE_TYPE: source_type}
        if source_type == SOURCE_IRELAND:
            return await self.async_step_ireland()
        return await self.async_step_location()

    # --- Irish mosque -----------------------------------------------------------

    async def async_step_ireland(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a mosque from the registry (nearest first)."""
        if user_input is not None:
            mosque = get_mosque(user_input[CONF_MOSQUE])
            name = (user_input.get(CONF_LOCATION_NAME) or "").strip() or mosque.short_name
            self._data.update(
                {
                    CONF_CALC_METHOD: mosque.key,
                    CONF_LOCATION_NAME: name,
                    CONF_LATITUDE: mosque.latitude,
                    CONF_LONGITUDE: mosque.longitude,
                    CONF_TIMEZONE: mosque.timezone,
                }
            )
            return await self._async_finish()

        home_lat, home_lon = self.hass.config.latitude, self.hass.config.longitude
        ordered = [m.key for m, _ in mosques_by_distance(home_lat, home_lon)]
        suggested_key = ordered[0]
        suggested_name: str | None = None
        if self._reconfigure:
            entry = self._get_reconfigure_entry()
            if entry.data.get(CONF_CALC_METHOD) in MOSQUES:
                suggested_key = entry.data[CONF_CALC_METHOD]
            suggested_name = entry.data.get(CONF_LOCATION_NAME)

        schema = vol.Schema(
            {
                vol.Required(CONF_MOSQUE): _select(ordered, "ireland_mosque"),
                vol.Optional(CONF_LOCATION_NAME): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id=STEP_IRELAND,
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_MOSQUE: suggested_key, CONF_LOCATION_NAME: suggested_name}
            ),
            description_placeholders={"nearest": _nearest_text(home_lat, home_lon)},
        )

    # --- Calculated: location then method --------------------------------------

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick coordinates and a name."""
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            self._data.update(
                {
                    CONF_LATITUDE: float(location[CONF_LATITUDE]),
                    CONF_LONGITUDE: float(location[CONF_LONGITUDE]),
                    CONF_LOCATION_NAME: (user_input.get(CONF_LOCATION_NAME) or "").strip()
                    or DEFAULT_LOCATION_NAME,
                    CONF_TIMEZONE: str(self.hass.config.time_zone),
                }
            )
            return await self.async_step_method()

        suggested = {
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            },
            CONF_LOCATION_NAME: DEFAULT_LOCATION_NAME,
        }
        if self._reconfigure:
            entry = self._get_reconfigure_entry()
            if entry.data.get(CONF_SOURCE_TYPE) == SOURCE_CALCULATED:
                suggested = {
                    CONF_LOCATION: {
                        CONF_LATITUDE: entry.data.get(CONF_LATITUDE, self.hass.config.latitude),
                        CONF_LONGITUDE: entry.data.get(CONF_LONGITUDE, self.hass.config.longitude),
                    },
                    CONF_LOCATION_NAME: entry.data.get(CONF_LOCATION_NAME, DEFAULT_LOCATION_NAME),
                }
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION): selector.LocationSelector(
                    selector.LocationSelectorConfig(radius=False)
                ),
                vol.Optional(CONF_LOCATION_NAME): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id=STEP_LOCATION,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    async def async_step_method(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the calculation method."""
        if user_input is not None:
            self._data[CONF_CALC_METHOD] = user_input[CONF_CALC_METHOD]
            return await self._async_finish()

        current = DEFAULT_CALC_METHOD
        if self._reconfigure:
            current = Settings.from_entry(self._get_reconfigure_entry()).calc_method
            if current not in STANDARD_CALC_METHODS:
                current = DEFAULT_CALC_METHOD
        return self.async_show_form(
            step_id=STEP_METHOD,
            data_schema=self.add_suggested_values_to_schema(
                METHOD_SCHEMA, {CONF_CALC_METHOD: current}
            ),
        )

    # --- Finish -------------------------------------------------------------------

    async def _async_finish(self) -> ConfigFlowResult:
        data = self._data
        source_type = data[CONF_SOURCE_TYPE]
        method = data[CONF_CALC_METHOD]
        unique_id = entry_unique_id(source_type, method, data[CONF_LATITUDE], data[CONF_LONGITUDE])

        if self._reconfigure:
            entry = self._get_reconfigure_entry()
            existing = await self.async_set_unique_id(unique_id)
            if existing is not None and existing.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")
            options = _options_after_reconfigure(entry, source_type, method)
            return self.async_update_reload_and_abort(
                entry,
                data=data,
                options=options,
                unique_id=unique_id,
                title=data[CONF_LOCATION_NAME],
            )

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=data[CONF_LOCATION_NAME],
            data=data,
            options=default_options(source_type, method),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,  # noqa: ARG004 - Home Assistant's signature
    ) -> MuslimPrayerCompanionOptionsFlow:
        """Return the options flow handler."""
        return MuslimPrayerCompanionOptionsFlow()


def _options_after_reconfigure(entry: ConfigEntry, source_type: str, method: str) -> dict[str, Any]:
    """Carry the entry's options over to a new source/mosque/method."""
    options = copy.deepcopy(dict(entry.options))
    if source_type == SOURCE_IRELAND:
        options.pop(CONF_CALC_METHOD, None)
        mosque_key: str | None = method
    else:
        options[CONF_CALC_METHOD] = method
        mosque_key = None

    if (
        options.get(CONF_IQAMAH_METHOD) == IQAMAH_METHOD_MOSQUE
        and default_iqamah_method(mosque_key) != IQAMAH_METHOD_MOSQUE
    ):
        options[CONF_IQAMAH_METHOD] = IQAMAH_METHOD_OFFSET

    seed = seed_friday_mosques(mosque_key)
    if seed:
        existing = options.get(CONF_FRIDAY_MOSQUES) or []
        known_sources = {item.get(CONF_FRIDAY_SOURCE) for item in existing}
        known_names = {str(item.get(CONF_FRIDAY_NAME, "")).casefold() for item in existing}
        for item in seed:
            if (
                item[CONF_FRIDAY_SOURCE] not in known_sources
                and item[CONF_FRIDAY_NAME].casefold() not in known_names
            ):
                existing = [*existing, item]
        options[CONF_FRIDAY_MOSQUES] = existing
    return options


class MuslimPrayerCompanionOptionsFlow(OptionsFlow):
    """Options menu: method, iqamah, Friday prayers, Hijri, display."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._friday_slug: str | None = None

    # --- Helpers ------------------------------------------------------------------

    @property
    def _settings(self) -> Settings:
        return Settings.from_entry(self.config_entry)

    def _options(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.config_entry.options))

    def _friday_items(self) -> list[dict[str, Any]]:
        return list(self.config_entry.options.get(CONF_FRIDAY_MOSQUES) or [])

    @callback
    def _async_save(self, new_options: dict[str, Any]) -> ConfigFlowResult:
        """Store the options and reload the entry once if anything changed."""
        entry = self.config_entry
        if dict(entry.options) != new_options:
            self.hass.config_entries.async_update_entry(entry, options=new_options)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(title="", data=new_options)

    # --- Menu ---------------------------------------------------------------------

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - menu steps take no input
    ) -> ConfigFlowResult:
        """Show the settings menu."""
        settings = self._settings
        menu = [] if settings.is_ireland else [STEP_METHOD]
        menu += ["iqamah", "friday", "hijri", "display"]
        source = (
            get_mosque(settings.mosque_key).name
            if settings.is_ireland and settings.mosque_key
            else settings.calc_method.upper()
        )
        return self.async_show_menu(
            step_id="init",
            menu_options=menu,
            description_placeholders={
                "location": self.config_entry.title,
                "source": source,
            },
        )

    # --- Calculation method -------------------------------------------------------

    async def async_step_method(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the calculation method of a calculated entry."""
        if user_input is not None:
            options = self._options()
            options[CONF_CALC_METHOD] = user_input[CONF_CALC_METHOD]
            return self._async_save(options)
        return self.async_show_form(
            step_id=STEP_METHOD,
            data_schema=self.add_suggested_values_to_schema(
                METHOD_SCHEMA, {CONF_CALC_METHOD: self._settings.calc_method}
            ),
        )

    # --- Iqamah ---------------------------------------------------------------------

    async def async_step_iqamah(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure how iqamah times are obtained."""
        settings = self._settings
        errors: dict[str, str] = {}
        if user_input is not None:
            method = user_input[CONF_IQAMAH_METHOD]
            url = (user_input.get(CONF_IQAMAH_API_URL) or "").strip() or None
            if url is not None:
                try:
                    cv.url(url)
                except vol.Invalid:
                    errors[CONF_IQAMAH_API_URL] = ERROR_INVALID_URL
            if method == IQAMAH_METHOD_API and url is None:
                errors[CONF_IQAMAH_API_URL] = ERROR_URL_REQUIRED
            if not errors:
                options = self._options()
                options[CONF_IQAMAH_METHOD] = method
                options[CONF_IQAMAH_API_URL] = url
                options[CONF_IQAMAH_OFFSETS] = {
                    prayer: int(user_input["offsets"][prayer]) for prayer in PRAYERS
                }
                return self._async_save(options)

        methods = [IQAMAH_METHOD_OFFSET]
        if settings.mosque_key and get_mosque(settings.mosque_key).supports_iqamah:
            methods.append(IQAMAH_METHOD_MOSQUE)
        methods += [IQAMAH_METHOD_API, IQAMAH_METHOD_DISABLED]
        offsets_schema = vol.Schema(
            {
                vol.Required(prayer): _number(0, MAX_IQAMAH_OFFSET_MINUTES, unit="min")
                for prayer in PRAYERS
            }
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_IQAMAH_METHOD): _select(methods, "iqamah_method"),
                vol.Optional(CONF_IQAMAH_API_URL): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                ),
                vol.Required("offsets"): section(offsets_schema, {"collapsed": False}),
            }
        )
        suggested = {
            CONF_IQAMAH_METHOD: settings.iqamah_method
            if settings.iqamah_method in methods
            else IQAMAH_METHOD_OFFSET,
            CONF_IQAMAH_API_URL: settings.iqamah_api_url,
            "offsets": dict(settings.iqamah_offsets),
        }
        if user_input is not None:
            suggested.update(user_input)
        return self.async_show_form(
            step_id="iqamah",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    # --- Hijri ----------------------------------------------------------------------

    async def async_step_hijri(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure the Hijri date and Imsak."""
        settings = self._settings
        if user_input is not None:
            options = self._options()
            options[CONF_HIJRI_ADJUSTMENT] = int(user_input[CONF_HIJRI_ADJUSTMENT])
            options[CONF_HIJRI_CHANGE_AT_MAGHRIB] = bool(user_input[CONF_HIJRI_CHANGE_AT_MAGHRIB])
            options[CONF_IMSAK_MINUTES] = int(user_input[CONF_IMSAK_MINUTES])
            return self._async_save(options)
        schema = vol.Schema(
            {
                vol.Required(CONF_HIJRI_ADJUSTMENT): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_HIJRI_ADJUSTMENT,
                        max=MAX_HIJRI_ADJUSTMENT,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="d",
                    )
                ),
                vol.Required(CONF_HIJRI_CHANGE_AT_MAGHRIB): selector.BooleanSelector(),
                vol.Required(CONF_IMSAK_MINUTES): _number(0, MAX_IMSAK_MINUTES, unit="min"),
            }
        )
        return self.async_show_form(
            step_id="hijri",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_HIJRI_ADJUSTMENT: settings.hijri_adjustment,
                    CONF_HIJRI_CHANGE_AT_MAGHRIB: settings.hijri_change_at_maghrib,
                    CONF_IMSAK_MINUTES: settings.imsak_minutes,
                },
            ),
        )

    # --- Display --------------------------------------------------------------------

    async def async_step_display(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose sensor groups, countdown format and the prayer window."""
        settings = self._settings
        if user_input is not None:
            options = self._options()
            options[CONF_ENABLED_GROUPS] = [
                group for group in SENSOR_GROUPS if group in user_input[CONF_ENABLED_GROUPS]
            ]
            options[CONF_COUNTDOWN_FORMAT] = user_input[CONF_COUNTDOWN_FORMAT]
            options[CONF_PRAYER_WINDOW_MINUTES] = int(user_input[CONF_PRAYER_WINDOW_MINUTES])
            return self._async_save(options)
        schema = vol.Schema(
            {
                vol.Required(CONF_ENABLED_GROUPS): _select(
                    list(SENSOR_GROUPS), "sensor_groups", multiple=True
                ),
                vol.Required(CONF_COUNTDOWN_FORMAT): _select(
                    list(COUNTDOWN_FORMATS), "countdown_format"
                ),
                vol.Required(CONF_PRAYER_WINDOW_MINUTES): _number(
                    0, MAX_PRAYER_WINDOW_MINUTES, step=5, unit="min"
                ),
            }
        )
        return self.async_show_form(
            step_id="display",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_ENABLED_GROUPS: sorted(settings.enabled_groups, key=SENSOR_GROUPS.index),
                    CONF_COUNTDOWN_FORMAT: settings.countdown_format,
                    CONF_PRAYER_WINDOW_MINUTES: settings.prayer_window_minutes,
                },
            ),
        )

    # --- Friday prayers -------------------------------------------------------------

    async def async_step_friday(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - menu steps take no input
    ) -> ConfigFlowResult:
        """Show the Friday prayers sub-menu."""
        menu = ["friday_add"]
        if self._friday_items():
            menu += ["friday_select", "friday_remove"]
        menu.append("init")
        names = ", ".join(str(item.get(CONF_FRIDAY_NAME, "")) for item in self._friday_items())
        return self.async_show_menu(
            step_id="friday",
            menu_options=menu,
            description_placeholders={"mosques": names or "-"},
        )

    def _friday_schema(self) -> vol.Schema:
        sources = [FRIDAY_SOURCE_MANUAL, *MOSQUE_KEYS]
        return vol.Schema(
            {
                vol.Optional(CONF_FRIDAY_NAME): selector.TextSelector(),
                vol.Required(CONF_FRIDAY_SOURCE, default=FRIDAY_SOURCE_MANUAL): _select(
                    sources, "friday_source"
                ),
                vol.Optional(CONF_FRIDAY_JUMUAH_1): selector.TextSelector(),
                vol.Optional(CONF_FRIDAY_JUMUAH_2): selector.TextSelector(),
                vol.Optional(CONF_FRIDAY_LABEL_1): selector.TextSelector(),
                vol.Optional(CONF_FRIDAY_LABEL_2): selector.TextSelector(),
            }
        )

    @staticmethod
    def _complete_friday_input(user_input: dict[str, Any]) -> dict[str, Any]:
        """Default the name to the mosque's name when a registered mosque is chosen."""
        completed = dict(user_input)
        source = completed.get(CONF_FRIDAY_SOURCE) or FRIDAY_SOURCE_MANUAL
        if not (completed.get(CONF_FRIDAY_NAME) or "").strip() and source in MOSQUES:
            completed[CONF_FRIDAY_NAME] = get_mosque(source).name
        return completed

    async def async_step_friday_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a mosque to the Friday prayers list."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._complete_friday_input(user_input)
            errors = validate_friday_item(user_input, self._friday_items())
            if not errors:
                options = self._options()
                options[CONF_FRIDAY_MOSQUES] = [
                    *self._friday_items(),
                    friday_item_from_input(user_input),
                ]
                return self._async_save(options)
        return self.async_show_form(
            step_id="friday_add",
            data_schema=self.add_suggested_values_to_schema(
                self._friday_schema(), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_friday_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which Friday mosque to edit."""
        if user_input is not None:
            self._friday_slug = user_input[CONF_FRIDAY_SLUG]
            return await self.async_step_friday_edit()
        schema = vol.Schema(
            {
                vol.Required(CONF_FRIDAY_SLUG): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=str(item[CONF_FRIDAY_SLUG]),
                                label=str(item.get(CONF_FRIDAY_NAME, item[CONF_FRIDAY_SLUG])),
                            )
                            for item in self._friday_items()
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="friday_select", data_schema=schema)

    async def async_step_friday_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit one Friday mosque (its slug, and therefore its entities, stay)."""
        items = self._friday_items()
        current = next(
            (item for item in items if item.get(CONF_FRIDAY_SLUG) == self._friday_slug), None
        )
        if current is None:
            return await self.async_step_friday()

        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._complete_friday_input(user_input)
            errors = validate_friday_item(user_input, items, editing_slug=self._friday_slug)
            if not errors:
                updated = friday_item_from_input(user_input, slug=self._friday_slug)
                options = self._options()
                options[CONF_FRIDAY_MOSQUES] = [
                    updated if item.get(CONF_FRIDAY_SLUG) == self._friday_slug else item
                    for item in items
                ]
                return self._async_save(options)

        suggested = {key: value for key, value in current.items() if key != CONF_FRIDAY_SLUG}
        if user_input is not None:
            suggested.update(user_input)
        return self.async_show_form(
            step_id="friday_edit",
            data_schema=self.add_suggested_values_to_schema(self._friday_schema(), suggested),
            errors=errors,
            description_placeholders={"mosque": str(current.get(CONF_FRIDAY_NAME, ""))},
        )

    async def async_step_friday_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove mosques from the Friday prayers list."""
        items = self._friday_items()
        if user_input is not None:
            remove = set(user_input.get("slugs", []))
            options = self._options()
            options[CONF_FRIDAY_MOSQUES] = [
                item for item in items if item.get(CONF_FRIDAY_SLUG) not in remove
            ]
            return self._async_save(options)
        schema = vol.Schema(
            {
                vol.Required("slugs", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=str(item[CONF_FRIDAY_SLUG]),
                                label=str(item.get(CONF_FRIDAY_NAME, item[CONF_FRIDAY_SLUG])),
                            )
                            for item in items
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                        multiple=True,
                    )
                )
            }
        )
        return self.async_show_form(step_id="friday_remove", data_schema=schema)
