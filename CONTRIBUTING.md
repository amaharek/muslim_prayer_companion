# Contributing

Thank you for helping the community that uses this integration. Bug reports, mosque additions and code are all welcome.

## Development setup

```bash
git clone https://github.com/amaharek/muslim_prayer_companion.git
cd muslim_prayer_companion
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

`scripts/setup` does the same. Then:

```bash
pytest -q --cov                                   # the test suite (network is blocked)
ruff check . && ruff format .                     # lint and format
pre-commit run --all-files                        # every hook
python -I scripts/build_icci_timetable.py --check # bundled ICCI timetable
python scripts/check_mosques.py                   # fetch and parse every mosque source
```

Tests use the Home Assistant test harness (`hass` fixture, `MockConfigEntry`) with Home Assistant set to Dublin. Mosque APIs are served from `tests/fixtures/` through `aioclient_mock`; captured payloads are from 20 October 2026.

## Add your mosque

Mosques live in `custom_components/muslim_prayer_companion/data/mosques.json`. If your mosque publishes its times with the **Daily Prayer Time** WordPress plugin (the `/wp-json/dpt/v1/prayertime?filter=today` endpoint), adding it needs no Python at all.

1. **Ask the mosque.** Make sure they are happy for their published times to be read by this integration, and agree on the credit line.
2. **Add one record** to `mosques.json`:

   ```json
   {
     "key": "ie-example",
     "name": "Example Islamic Centre",
     "short_name": "EIC",
     "address": "1 Example Road",
     "city": "Dublin 1",
     "country": "Ireland",
     "latitude": 53.35,
     "longitude": -6.26,
     "timezone": "Europe/Dublin",
     "website": "https://example.ie",
     "source": {
       "type": "dpt",
       "url": "https://example.ie/wp-json/dpt/v1/prayertime?filter=today"
     },
     "source_id": "example-api",
     "jumuah": "auto",
     "credit": "Daily Prayer Time WordPress plugin API published by Example Islamic Centre."
   }
   ```

   | Field                        | Meaning                                                                                              |
   | ---------------------------- | ---------------------------------------------------------------------------------------------------- |
   | `key`                        | Stable identifier, `<country code>-<slug>`; it is stored in config entries and must never change     |
   | `name`, `short_name`         | Full name and the short name used as the default entry name                                          |
   | `address`, `city`, `country` | Shown in diagnostics and mosque info                                                                 |
   | `latitude`, `longitude`      | Used for the nearest-mosque ordering, the Qibla and the calculated fallback                          |
   | `timezone`                   | IANA zone of the mosque; its times are interpreted in it                                             |
   | `website`                    | Public website (`https://`)                                                                          |
   | `source.type`                | `dpt` (Daily Prayer Time plugin), `icci_timetable` (bundled table) or `mai_html` (maionline.ie page) |
   | `source.url`                 | The endpoint for `dpt` and `mai_html`                                                                |
   | `source_id`                  | Value of the sensors' `source` attribute, e.g. `example-api`                                         |
   | `jumuah`                     | `auto` when the source publishes Jumu'ah times (only `dpt` can), else `manual`                       |
   | `credit`                     | One sentence crediting the mosque                                                                    |

3. **Add the labels** in `custom_components/muslim_prayer_companion/translations/en.json` and `ar.json` under `selector.ireland_mosque.options` and `selector.friday_source.options`, then copy `en.json` over `strings.json` (the two must stay identical; a test checks it).
4. **Capture a fixture** if you add or change a parser: save the endpoint's response under `tests/fixtures/` and test the parser with it.
5. **Run** `python scripts/check_mosques.py` to fetch and parse the new source, then the test suite.

A source in a format the integration cannot read yet (a different plugin, a PDF, an HTML page) needs a parser module under `api_providers/` with pure functions, a branch in `IrelandProvider.async_fetch`, a new `source.type` accepted by `helpers/registry.py`, and tests with a captured fixture. Open an issue first so we can agree on the approach.

## Pull request checklist

- [ ] `pytest -q` passes and new behaviour has tests
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pre-commit run --all-files` passes
- [ ] `CHANGELOG.md` has an entry under `Unreleased` (or the next version)
- [ ] For a new mosque: registry record, English and Arabic labels, `strings.json` updated, `scripts/check_mosques.py` green, and the mosque is credited
