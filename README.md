# MSFS Plugins

A monorepo for add-ons, external apps and tools for **Microsoft Flight Simulator 2024** (MSFS 2024). Most of it also applies to MSFS 2020.

This README doubles as a reusable **MSFS SDK guideline**. It covers the tools, the ways a program can talk to the sim, the conventions this repo uses, and common pitfalls. Follow it when you start a new plugin or work on an existing one. If you are an AI agent, read [`AGENTS.md`](./AGENTS.md) too.

> Verify version-specific details (exact simvar names, SDK paths, package formats) against the official docs before relying on them. The SDK changes between sim updates.
>
> - MSFS 2024 SDK docs: <https://docs.flightsimulator.com/msfs2024>
> - MSFS 2020 SDK docs: <https://docs.flightsimulator.com/html/index.htm>

---

## Contents

1. [Choosing an integration approach](#1-choosing-an-integration-approach)
2. [Environment setup](#2-environment-setup)
3. [SimConnect essentials](#3-simconnect-essentials)
4. [WASM modules](#4-wasm-modules)
5. [In-sim HTML/JS panels and instruments](#5-in-sim-htmljs-panels-and-instruments)
6. [Packaging, installing and auto-launching](#6-packaging-installing-and-auto-launching)
7. [Language and library options](#7-language-and-library-options)
8. [Repository conventions](#8-repository-conventions)
9. [Architecture patterns](#9-architecture-patterns)
10. [Testing without the sim](#10-testing-without-the-sim)
11. [Common pitfalls](#11-common-pitfalls)
12. [Useful external data sources](#12-useful-external-data-sources)
13. [Resources](#13-resources)
14. [New plugin checklist](#14-new-plugin-checklist)

---

## 1. Choosing an integration approach

MSFS offers a few ways in. Pick the lightest one that does the job.

- **SimConnect (external process)** is the default choice.
  - Use it to read and write simvars, send events, read AI and multiplayer traffic, query airport and navdata facilities, and receive sim system events.
  - It runs out of process on the PC, in any language that can call the native DLL or use a wrapper.
  - It does not run on Xbox.
- **WASM module (C/C++ compiled to WebAssembly)** runs inside the sim.
  - Use it only when SimConnect cannot reach what you need, such as some L-vars, calculator code, or per-frame logic tightly coupled to the sim.
  - It is sandboxed, and it is the only native-code route on Xbox.
- **HTML/JS toolbar panel or instrument** runs inside the sim's UI.
  - Use it for in-sim UI such as panels, transcripts and settings.
  - It usually talks to an external app over a local WebSocket or HTTP endpoint.
- **Aircraft, scenery or livery content packages** are data, not code. Use the Package Builder and the SDK content docs.
- **Third-party layers** such as FSUIPC and the MobiFlight WASM module add convenience or cover gaps. Treat them as optional dependencies, not foundations.

Rule of thumb: start with SimConnect in an external app, add a WASM module only for a specific gap, and add an in-sim panel only if the external UI is not enough.

| Need | Use |
| --- | --- |
| Read or set standard simvars and events | SimConnect |
| Read airports, runways, taxi paths, waypoints | SimConnect Facilities API |
| AI or multiplayer traffic | SimConnect |
| Custom L-vars, calculator code, in-sim logic | WASM module (or a WASM helper) |
| In-sim UI | HTML/JS toolbar panel |
| Runs on Xbox | WASM or JS only |
| Audio, speech, LLMs, network | External app |

---

## 2. Environment setup

1. **MSFS 2024 installed.** Steam and Microsoft Store/Xbox installs use different folder locations, so check which one you have.
2. **Enable Developer Mode** in the sim: *Options > General > Developers > Developer Mode: ON*. This adds the Dev Mode menu bar.
3. **Install the SDK** from the Dev Mode menu (*Help > SDK Installer*). It provides:
   - SimConnect headers and libraries: `SimConnect.h`, `SimConnect.lib`, `SimConnect.dll`.
   - The managed wrapper `Microsoft.FlightSimulator.SimConnect.dll` for .NET, under the SimConnect SDK `lib\managed` folder.
   - The Package Builder, samples, and the WASM headers and toolchain hooks.
4. **Toolchain:**
   - .NET 8 SDK for C# apps.
   - Visual Studio 2022 with *Desktop development with C++* for native and WASM work. WASM builds use the SDK's own build tooling (MSBuild project types or the SDK's clang configuration).
   - Node.js LTS for TypeScript apps and JS panels.
   - Python 3.11 or later for Python tools.
5. **Dev Mode tools worth knowing:**
   - The Console and Behaviors debugger.
   - The SimConnect Inspector, for watching connections and requests.
   - The SDK documentation browser.
   - Menu names change between sim versions, so look under the Dev Mode *Tools* and *Help* menus.

Keep the SDK install and the sim install separate from this repo. Reference the SDK by environment variable, not by committed binaries. Use `MSFS_SDK`, pointing to the SDK root. For MSFS 2020 compatibility use `MSFS2020_SDK`, and for 2024 use `MSFS2024_SDK`. Do not commit `SimConnect.dll` or other SDK files unless the SDK license explicitly allows redistribution and the plugin needs to ship it.

---

## 3. SimConnect essentials

### Connection model

1. Open a connection with `SimConnect_Open`. You can connect before the sim is fully loaded, and the call can fail if the sim is not running yet.
2. Register **data definitions**, **events** and **requests**.
3. Pump messages. Either use a Windows message handle, or call `SimConnect_CallDispatch` or `SimConnect_GetNextDispatch` on a dedicated thread or timer.
4. Handle disconnect and reconnect. The user may start your app before the sim, or quit the sim while your app is running.
5. Close the connection on exit with `SimConnect_Close`.

### Reading simvars

- Register each variable with `SimConnect_AddToDataDefinition`. Give it its exact simvar name, the **units**, and the data type.
- Request data with `SimConnect_RequestDataOnSimObject`. Choose the period deliberately:
  - `SIMCONNECT_PERIOD_ONCE`
  - `SIMCONNECT_PERIOD_SECOND`
  - `SIMCONNECT_PERIOD_VISUAL_FRAME`
  - `SIMCONNECT_PERIOD_SIM_FRAME`
- Use the `CHANGED` request flag to receive data only when values change.
- The simvar list is the source of truth for names and units: *Simulation Variables* in the SDK docs. Indexed variables use `:N` syntax, for example `COM ACTIVE FREQUENCY:1`.

Commonly needed simvars for navigation, radio and ATC-style tools:

- Position and motion: `PLANE LATITUDE`, `PLANE LONGITUDE`, `PLANE ALTITUDE`, `PLANE HEADING DEGREES MAGNETIC`, `GROUND VELOCITY`, `AIRSPEED INDICATED`, `VERTICAL SPEED`, `SIM ON GROUND`.
- Radios and transponder: `COM ACTIVE FREQUENCY:1`, `COM STANDBY FREQUENCY:1`, `COM TRANSMIT:1`, `COM RECEIVE ALL`, `TRANSPONDER CODE:1`.
- Aircraft identity and power: `ATC ID`, `ATC TYPE`, `ELECTRICAL MASTER BATTERY`, `CIRCUIT COM ON:1`.

### Events and inputs

- Send key events with `SimConnect_MapClientEventToSimEvent` and `SimConnect_TransmitClientEvent`. The Event IDs reference lists the valid names.
- Not every aircraft honours every event, especially complex add-on aircraft. Test against the aircraft you target.
- For newer systems, check the *Input Events* (B-vars) APIs, which enumerate and set aircraft-specific inputs.

### Facilities API (airport and navdata)

- `SimConnect_RequestFacilitiesList_EX1` lists facilities near or in the sim's database.
- `SimConnect_AddToFacilityDefinition` with `SimConnect_RequestFacilityData` reads structured data: runways, taxi paths, taxi points, parking, approaches, waypoints and frequencies.
- Data comes from the sim's own scenery and navdata, so it matches what the user sees. Prefer it over external airport databases when matching the sim is important.

### AI and multiplayer traffic

- `SimConnect_RequestDataOnSimObjectType` with `SIMCONNECT_SIMOBJECT_TYPE_AIRCRAFT` returns nearby aircraft in a radius.
- Expect a lot of objects near busy airports. Use radius limits and a moderate period.

### Client data areas and custom channels

- Client data areas let your external app and your WASM module exchange data through SimConnect without inventing another IPC channel.

### Remote connections

- SimConnect can run over TCP to a second PC. Configure `SimConnect.xml` on the sim PC and `SimConnect.cfg` on the client PC. See the SimConnect config docs.

---

## 4. WASM modules

- Write them in C/C++ using the SDK's WASM headers, for example `MSFS/MSFS.h`, `MSFS/MSFS_WindowsTypes.h` and the gauge and module APIs.
- Build with the SDK's MSBuild or clang-based setup, as the SDK samples show.
- Use them to:
  - read or write L-vars with `execute_calculator_code`;
  - run logic at the sim's frame rate;
  - expose data to external apps through client data areas.
- Prefer the simplest thing that works. A WASM module is one more moving part to package, version and debug.
- Modules load from a package in the Community folder. They are restarted with the sim, so expect slower iteration than a normal external app.

---

## 5. In-sim HTML/JS panels and instruments

- **Toolbar panels** are HTML/CSS/JS pages shown in the sim's toolbar. They suit settings, transcripts and status views.
- **Instruments and gauges** use the JS instrument framework. This is a bigger investment and is mainly for aircraft work.
- A panel can talk to your external app over `ws://localhost:<port>` or HTTP. Bind to `127.0.0.1` only.
- Keep panel code small. Put real logic in the external app, where you can debug and test it normally.

---

## 6. Packaging, installing and auto-launching

- **Packages** have a `manifest.json`, a generated `layout.json`, and content folders. Build and validate them with the SDK's Package Builder.
- **Community folder:** the user's add-on folder, for example `...\Packages\Community`. Its location depends on the install type and the `InstalledPackagesPath` setting in `UserCfg.opt`.
- **Auto-launching an external app** with the sim uses an `exe.xml` file. It lives in the sim's roaming-data or local-cache folder, and the location differs between Steam and Store installs, and between MSFS 2020 and 2024. Check the SDK docs for the exact path for your install. Back up the file before editing it.
- **Distribution:**
  - Zip the package or use an installer.
  - Give the package a unique name (vendor prefix) so it does not collide with others.
  - Tell users which sim version and platform (PC or Xbox) are supported.
  - Keep logs in a predictable folder, for example `%LOCALAPPDATA%\<PluginName>\logs`.

Never modify a user's Community folder or `exe.xml` from a build script without an explicit opt-in.

---

## 7. Language and library options

- **C# / .NET 8:**
  - Official managed wrapper `Microsoft.FlightSimulator.SimConnect`.
  - Audio with NAudio.
  - UI with WPF, WinUI or Avalonia.
  - Best default for Windows desktop tools.
- **C++:** native SimConnect and WASM. Needed for WASM modules.
- **Python:**
  - `SimConnect` or `Python-SimConnect` (community wrappers).
  - Great for prototypes and data tools.
  - Packaging for end users is harder.
- **Node / TypeScript:**
  - `node-simconnect`.
  - Works well with Electron or Tauri UIs and with JS panels.
- **Rust:** the `simconnect-sdk` crate.
- **Third-party layers:**
  - FSUIPC, which has .NET and other client libraries.
  - MobiFlight WASM module, for wider event and L-var access.

Community wrappers may lag behind the SDK. Check that the wrapper supports the SimConnect features you need, such as the Facilities API, and pin versions.

---

## 8. Repository conventions

Suggested layout, one folder per plugin, shared code separate:

```text
MSFS-plugins/
  README.md            # this guideline
  AGENTS.md            # instructions for AI agents
  .gitignore
  shared/              # reusable libraries (SimConnect wrapper, audio, utils)
  plugins/
    <plugin-name>/
      README.md        # what it does, how to build, run, package
      src/
      tests/
      package/         # MSFS package source (manifest, content), if any
  docs/                # design notes, protocol docs, decisions
  scripts/             # build, package, install helpers
```

Conventions:

- Each plugin has its own `README.md` with build, run and package steps, and the sim versions it supports.
- Keep simvar and event names in **one place** per plugin, such as a constants file or data definition module, not scattered in code.
- Always state **units** next to simvars in code comments or type names.
- Configuration lives in a config file or environment variables. Secrets, such as API keys, live in environment variables or a local untracked file. Never commit them.
- `.gitignore` should cover at least: build output (`bin/`, `obj/`, `dist/`, `node_modules/`, `__pycache__/`, `.venv/`), logs, `.env`, and any local sim paths.
- Pin dependency versions and commit lockfiles.
- Use clear commit messages that say what changed and why.

---

## 9. Architecture patterns

Separate these layers so each can change or be tested alone:

1. **Sim adapter:** the only code that calls SimConnect. It exposes a small interface, for example `ISimClient`, that raises typed events such as `AircraftStateChanged`, and methods such as `SetComFrequency(...)`.
2. **Domain logic:** pure code with no SimConnect, audio or network calls. It takes state in and returns decisions out, and is easy to unit test.
3. **Services:** audio I/O, speech-to-text, text-to-speech, LLM calls, network data. Each sits behind an interface so you can swap providers or mock them.
4. **UI:** external window, tray app, or JS panel. It talks to the services and never to SimConnect directly.

Practical rules:

- Run the SimConnect message loop on its own thread or task. Never block it with slow work.
- Marshal results to your UI thread explicitly.
- Use a reconnect loop with backoff, and surface connection status in the UI.
- For anything real-time that mixes AI models with game state, keep the **authoritative state in code** and use models for language and intent, not for facts about the sim.
- Log at info level for state changes and at debug level for raw SimConnect traffic. Logs are the main way you will debug a running sim.

---

## 10. Testing without the sim

You cannot run MSFS in CI, so design for testing without it:

- Put the sim behind an interface and write a **fake sim client** that replays recorded or scripted states (a taxi, a takeoff, an approach).
- Unit test domain logic against fake states.
- Record real SimConnect sessions to a file during manual testing and replay them later.
- Keep an optional **manual test checklist** per plugin for sim-only behaviour, such as event handling on specific aircraft.
- Test on both a cold start (app first, then sim) and a warm start (sim first, then app).

---

## 11. Common pitfalls

- **Wrong or missing units** in data definitions. Values may silently come back in unexpected units.
- **Polling too fast.** Use the slowest period that is acceptable, and use `CHANGED` flags.
- **Blocking the dispatch loop,** which causes message backlog and UI freezes.
- **Assuming the sim is running.** Handle open failures, `SIMCONNECT_RECV_ID_QUIT`, and reconnects.
- **Bitness mismatch.** Use x64 builds with the 64-bit SimConnect library.
- **Aircraft differences.** Default aircraft and complex add-ons implement events and simvars differently. A simvar that works in one aircraft can be inert in another.
- **Frequencies and encodings.** Radio frequencies can appear as Hz, MHz or BCD depending on units. Check the units you request.
- **L-vars, B-vars and A-vars are different things.** Use the right API for each.
- **Xbox.** External executables cannot run there. WASM and JS are the only options, and storage and network access are restricted.
- **Changes between sim versions.** Re-test after sim updates. Do not assume 2020-era add-on packages and aircraft behave the same in 2024.
- **Audio device handling.** Headsets and default devices change at runtime. Handle device changes and let the user choose devices.
- **Secrets in client apps.** An API key shipped inside a distributed binary can be extracted. Use a proxy server or ask users to bring their own key.

---

## 12. Useful external data sources

The short list is below. Coverage, URLs, rate limits, and what to use the sim for instead are in [`docs/external-data.md`](./docs/external-data.md). Check each provider's license and terms before using its data in a released plugin.

- **Weather:** aviationweather.gov data API (METAR, TAF, SIGMETs, PIREPs). The sim's own weather is available through simvars, and it will not match a real METAR on a preset or custom theme.
- **Airports and runways:** the sim's Facilities API, OurAirports as a fallback.
- **Navdata and procedures:** the FAA CIFP and NASR for the US, Navigraph (paid, licensed), and X-Plane style data where licensing allows.
- **Flight plans:** SimBrief API (per-user OFP data).
- **Online networks:** the VATSIM data feed and APIs, and PilotEdge where allowed.
- **NOTAMs and TFRs:** FAA feeds (US). Worldwide NOTAMs at briefing quality are a paid navdata product.

---

## 13. Resources

- MSFS 2024 SDK docs: <https://docs.flightsimulator.com/msfs2024>
- MSFS 2020 SDK docs: <https://docs.flightsimulator.com/html/index.htm>
- SimConnect reference: under *Programming Tools > SimConnect SDK* in the SDK docs.
- Simulation Variables and Event IDs: in the same docs.
- SDK samples: installed with the SDK, look under the SimConnect SDK and samples folders.
- MSFS developer forums and the Microsoft Flight Simulator developer community on the official forum.
- Community tooling: MobiFlight WASM module and its event list, FSUIPC documentation.

---

## 14. New plugin checklist

- [ ] Decide the integration approach (section 1) and write the reasoning in the plugin README.
- [ ] Confirm target sim version(s) and platform (PC, Xbox).
- [ ] Create `plugins/<name>/` with a README, source, tests and a `.gitignore` if needed.
- [ ] Put SimConnect behind an interface and add a fake implementation for tests.
- [ ] List every simvar, event and facility query used, with units, in one place.
- [ ] Add reconnect handling and visible connection status.
- [ ] Keep secrets out of the repo and out of logs.
- [ ] Add logging to a known folder.
- [ ] Write the build, run and package steps, and test them from a clean checkout.
- [ ] Test cold start and warm start against the real sim with at least two aircraft.
- [ ] Note any third-party data or library licenses.

---

## Disclaimer

Everything here is for flight simulation only. It is not for real-world navigation, flight planning, or training that substitutes for certified instruction or equipment. This project is unaffiliated with Microsoft, Asobo Studio, or any third-party data or service provider named here.
