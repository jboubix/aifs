# External aviation data

Free sources for weather and other aviation metadata a plugin can use beside the sim. This is for the simulator only. It is not for real-world navigation or briefing.

Check each provider's license and terms before a released plugin. Cache responses, time out, and fall back: these feeds drop out. Do not ship an API key inside a distributed binary. Prefer a source that needs no key, or a proxy / bring-your-own-key.

There is no single free API that covers every kind of global aviation data at the quality of a paid navdata product. Use the sim first, NOAA for weather, and a narrower free feed or a paid license for the rest.

## Weather

Two different "weathers" matter:

- **Reported airport weather** (METAR, TAF) is what ATC phraseology and a briefing should quote.
- **The weather the aircraft is flying in** is the sim's own weather, read through SimConnect simvars. Those disagree whenever the user is on a preset, historic, or custom theme.

### aviationweather.gov (start here)

The [NOAA Aviation Weather Center Data API](https://aviationweather.gov/data/api/) is the free source. No API key. Worldwide METARs and TAFs, plus SIGMETs. PIREPs and AIREPs are mostly the US and the North Atlantic. The same API also has station, airport, navaid, fix, and obstacle lookups. History is roughly the last 15–30 days.

The public docs (checked October 2026) describe about 100 requests per minute, a custom User-Agent, and a cap around 400 entries per response. Re-check the live page; the site was overhauled in October 2023 and the API in September 2025. The old ADDS Text Data Server is gone.

```text
https://aviationweather.gov/api/data/metar?ids=EGLL&format=json
https://aviationweather.gov/api/data/taf?ids=EGLL&format=json
```

`ids` is one or more ICAO identifiers. `format` can be raw text, JSON, GeoJSON, and others listed on that page. The same docs list bulk cache files for all current METARs if you would rather fetch once than query per airport.

The ATC server does not hard-code this URL. Ingest stays off until `ATC_WEATHER_INGEST`, `ATC_WEATHER_METAR_URL`, and `ATC_WEATHER_ICAOS` are set. See [architecture.md](./architecture.md).

### Decoded wrappers

These sit on NOAA (and similar) data and return parsed JSON. Useful if you want spoken summaries without writing a METAR parser. Both need a key, so they are a worse default than calling NOAA directly.

| Service | Free tier | Notes |
| --- | --- | --- |
| [AVWX](https://avwx.rest/) | Parsed METAR and TAF | NOTAMs and some extras are paid |
| [CheckWX](https://www.checkwxapi.com/) | Decoded METAR and TAF | Check the current quota before depending on it |

## Airports and runways

Use the sim's **Facilities API** first (airports, runways, taxi paths). [OurAirports](https://ourairports.com/data/) is the free fallback: a daily CSV dump, not a live REST API.

## Other feeds

| Need | Free source | Limit |
| --- | --- | --- |
| Online ATC and traffic | [VATSIM data feed](https://data.vatsim.net/) | VATSIM only |
| Live traffic | [OpenSky Network](https://openskynetwork.github.io/opensky-api/) | Anonymous use is throttled. Not flight plans or weather |
| US procedures and navdata | [FAA CIFP and NASR](https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/) | US only, bulk files |
| US NOTAMs and TFRs | FAA feeds | US only; registration |
| The user's own flight plan | [SimBrief API](https://www.simbrief.com/api/) | Per-user operational flight plan, not a global database |

Procedures, airways, and worldwide NOTAMs at briefing quality are what **Navigraph** (or a similar licensed product) is for. Do not treat a scraped or unofficial copy of that data as free. X-Plane-style data is only acceptable where its license allows the use you have in mind.

PilotEdge is an option for online ATC only where their terms allow it.
