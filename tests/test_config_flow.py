"""Config flow, reconfigure flow and the options menu."""

from __future__ import annotations

from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.muslim_prayer_companion.const import (
    CONF_CALC_METHOD,
    CONF_COUNTDOWN_FORMAT,
    CONF_ENABLED_GROUPS,
    CONF_FRIDAY_MOSQUES,
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
    DOMAIN,
    IQAMAH_METHOD_API,
    IQAMAH_METHOD_MOSQUE,
    IQAMAH_METHOD_OFFSET,
    SOURCE_CALCULATED,
    SOURCE_IRELAND,
)

from .conftest import FROZEN_NOW, make_entry, setup_entry


async def _start(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_ireland_flow_creates_entry(hass: HomeAssistant) -> None:
    """User -> ireland -> entry with the mosque's coordinates and seeded options."""
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_TYPE: SOURCE_IRELAND}
    )
    assert result["step_id"] == "ireland"
    assert "nearest" in result["description_placeholders"]
    assert "km" in result["description_placeholders"]["nearest"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MOSQUE: "ie-hicc", CONF_LOCATION_NAME: ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HICC"
    assert result["data"] == {
        CONF_SOURCE_TYPE: SOURCE_IRELAND,
        CONF_CALC_METHOD: "ie-hicc",
        CONF_LOCATION_NAME: "HICC",
        CONF_LATITUDE: 53.394,
        CONF_LONGITUDE: -6.4258,
        CONF_TIMEZONE: "Europe/Dublin",
    }
    assert result["options"][CONF_IQAMAH_METHOD] == IQAMAH_METHOD_MOSQUE
    assert result["options"][CONF_FRIDAY_MOSQUES][0]["source"] == "ie-hicc"
    assert result["result"].unique_id == "ireland:ie-hicc"


async def test_duplicate_mosque_aborts(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """The same mosque cannot be added twice."""
    freezer.move_to(FROZEN_NOW)
    await setup_entry(hass, make_entry(SOURCE_IRELAND, "ie-icci"))
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_TYPE: SOURCE_IRELAND}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MOSQUE: "ie-icci"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_calculated_flow(hass: HomeAssistant) -> None:
    """User -> location -> method -> entry."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_TYPE: SOURCE_CALCULATED}
    )
    assert result["step_id"] == "location"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {CONF_LATITUDE: 51.8985, CONF_LONGITUDE: -8.4756},
            CONF_LOCATION_NAME: "Cork",
        },
    )
    assert result["step_id"] == "method"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CALC_METHOD: "mwl"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cork"
    assert result["data"][CONF_CALC_METHOD] == "mwl"
    assert result["data"][CONF_LATITUDE] == 51.8985
    assert result["options"][CONF_CALC_METHOD] == "mwl"
    assert result["options"][CONF_IQAMAH_METHOD] == IQAMAH_METHOD_OFFSET
    assert result["options"][CONF_FRIDAY_MOSQUES] == []
    assert result["result"].unique_id == "calculated:51.8985,-8.4756"


async def test_reconfigure_to_another_mosque(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Reconfigure swaps the mosque, keeps options and seeds the new Friday mosque."""
    freezer.move_to(FROZEN_NOW)
    entry = make_entry(SOURCE_IRELAND, "ie-icci", options={CONF_HIJRI_ADJUSTMENT: 1})
    await setup_entry(hass, entry)

    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_TYPE: SOURCE_IRELAND}
    )
    assert result["step_id"] == "ireland"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MOSQUE: "ie-mcnd"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CALC_METHOD] == "ie-mcnd"
    assert entry.title == "MCND"
    assert entry.unique_id == "ireland:ie-mcnd"
    assert entry.options[CONF_HIJRI_ADJUSTMENT] == 1
    sources = [item["source"] for item in entry.options[CONF_FRIDAY_MOSQUES]]
    assert sources == ["manual", "ie-mcnd"]


async def test_reconfigure_collision_aborts(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_mosque_sites: object
) -> None:
    """Reconfiguring onto a mosque another entry already uses is refused."""
    freezer.move_to(FROZEN_NOW)
    icci = await setup_entry(hass, make_entry(SOURCE_IRELAND, "ie-icci"))
    await setup_entry(hass, make_entry(SOURCE_IRELAND, "ie-mcnd"))
    result = await icci.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_TYPE: SOURCE_IRELAND}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MOSQUE: "ie-mcnd"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert icci.data[CONF_CALC_METHOD] == "ie-icci"


async def test_reconfigure_ireland_to_calculated(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_mosque_sites: object
) -> None:
    """Switching an Irish entry to calculated moves the method into options."""
    freezer.move_to(FROZEN_NOW)
    entry = await setup_entry(hass, make_entry(SOURCE_IRELAND, "ie-hicc"))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_TYPE: SOURCE_CALCULATED}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {CONF_LATITUDE: 53.3, CONF_LONGITUDE: -6.3}, CONF_LOCATION_NAME: "Home"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CALC_METHOD: "isna"}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SOURCE_TYPE] == SOURCE_CALCULATED
    assert entry.options[CONF_CALC_METHOD] == "isna"
    # 'mosque' iqamah no longer applies without a mosque.
    assert entry.options[CONF_IQAMAH_METHOD] == IQAMAH_METHOD_OFFSET


async def _options(hass: HomeAssistant, entry: MockConfigEntry, step: str) -> dict[str, Any]:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def test_options_menu_entries(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Calculated entries get a method page; Irish ones do not."""
    freezer.move_to(FROZEN_NOW)
    calculated = await setup_entry(hass, make_entry())
    result = await hass.config_entries.options.async_init(calculated.entry_id)
    assert result["menu_options"] == ["method", "iqamah", "friday", "hijri", "display"]
    icci = await setup_entry(hass, make_entry(SOURCE_IRELAND, "ie-icci"))
    result = await hass.config_entries.options.async_init(icci.entry_id)
    assert result["menu_options"] == ["iqamah", "friday", "hijri", "display"]
    assert result["description_placeholders"]["source"] == "Islamic Cultural Centre of Ireland"


async def test_options_method_and_hijri_and_display(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Each simple page saves its fields and leaves the others untouched."""
    freezer.move_to(FROZEN_NOW)
    entry = await setup_entry(hass, make_entry())
    before = dict(entry.options)

    result = await _options(hass, entry, "method")
    assert result["step_id"] == "method"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CALC_METHOD: "mwl"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CALC_METHOD] == "mwl"
    assert entry.runtime_data.coordinator.calc_method == "mwl"  # reloaded

    result = await _options(hass, entry, "hijri")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HIJRI_ADJUSTMENT: 1, CONF_HIJRI_CHANGE_AT_MAGHRIB: True, CONF_IMSAK_MINUTES: 15},
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_HIJRI_ADJUSTMENT] == 1
    assert entry.options[CONF_HIJRI_CHANGE_AT_MAGHRIB] is True
    assert entry.options[CONF_IMSAK_MINUTES] == 15

    result = await _options(hass, entry, "display")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLED_GROUPS: ["hijri", "qibla"],
            CONF_COUNTDOWN_FORMAT: "clock",
            CONF_PRAYER_WINDOW_MINUTES: 10,
        },
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_ENABLED_GROUPS] == ["hijri", "qibla"]
    assert entry.options[CONF_COUNTDOWN_FORMAT] == "clock"
    assert entry.options[CONF_PRAYER_WINDOW_MINUTES] == 10
    # Untouched keys survive every save.
    assert entry.options[CONF_IQAMAH_OFFSETS] == before[CONF_IQAMAH_OFFSETS]
    assert entry.options[CONF_FRIDAY_MOSQUES] == before[CONF_FRIDAY_MOSQUES]


async def test_options_iqamah_page(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """The iqamah page validates the URL and stores offsets from its section."""
    freezer.move_to(FROZEN_NOW)
    entry = await setup_entry(hass, make_entry())
    result = await _options(hass, entry, "iqamah")
    assert result["step_id"] == "iqamah"

    offsets = {"Fajr": 25, "Dhuhr": 10, "Asr": 10, "Maghrib": 5, "Isha": 12}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_IQAMAH_METHOD: IQAMAH_METHOD_API, "offsets": offsets}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_IQAMAH_API_URL: "url_required"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_IQAMAH_METHOD: IQAMAH_METHOD_API,
            CONF_IQAMAH_API_URL: "not a url",
            "offsets": offsets,
        },
    )
    assert result["errors"] == {CONF_IQAMAH_API_URL: "invalid_url"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_IQAMAH_METHOD: IQAMAH_METHOD_API,
            CONF_IQAMAH_API_URL: "https://example.ie/iqamah",
            "offsets": offsets,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_IQAMAH_METHOD] == IQAMAH_METHOD_API
    assert entry.options[CONF_IQAMAH_API_URL] == "https://example.ie/iqamah"
    assert entry.options[CONF_IQAMAH_OFFSETS] == offsets


async def test_options_friday_add_edit_remove(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The Friday sub-menu adds, edits and removes mosques with validation."""
    freezer.move_to(FROZEN_NOW)
    entry = await setup_entry(hass, make_entry())

    result = await _options(hass, entry, "friday")
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["friday_add", "init"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "friday_add"}
    )
    assert result["step_id"] == "friday_add"

    # Manual mosque without a time: error.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Local", "source": "manual"}
    )
    assert result["errors"] == {"jumuah_1": "time_required"}
    # A registry mosque with an empty name gets the mosque's name.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "", "source": "ie-hicc", "jumuah_1": "13:30"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    items = entry.options[CONF_FRIDAY_MOSQUES]
    assert len(items) == 1
    assert items[0]["name"] == "Hansfield Islamic Cultural Centre"
    assert items[0]["slug"] == "hansfield_islamic_cultural_centre"
    assert items[0]["jumuah_1"] == "13:30"

    # Edit: rename, keep the slug.
    result = await _options(hass, entry, "friday")
    assert result["menu_options"] == ["friday_add", "friday_select", "friday_remove", "init"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "friday_select"}
    )
    assert result["step_id"] == "friday_select"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slug": items[0]["slug"]}
    )
    assert result["step_id"] == "friday_edit"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "HICC Hansfield", "source": "ie-hicc", "jumuah_1": "13:45", "jumuah_2": "13:00"},
    )
    assert result["errors"] == {"jumuah_2": "jumuah_order"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "HICC Hansfield",
            "source": "ie-hicc",
            "jumuah_1": "13:45",
            "jumuah_2": "14:45",
            "label_2": "Women",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    items = entry.options[CONF_FRIDAY_MOSQUES]
    assert items[0]["slug"] == "hansfield_islamic_cultural_centre"
    assert items[0]["name"] == "HICC Hansfield"
    assert items[0]["jumuah_2"] == "14:45"
    assert items[0]["label_2"] == "Women"

    # Remove.
    result = await _options(hass, entry, "friday")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "friday_remove"}
    )
    assert result["step_id"] == "friday_remove"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slugs": [items[0]["slug"]]}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_FRIDAY_MOSQUES] == []
