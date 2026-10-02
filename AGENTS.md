# AGENTS.md

Instructions for AI agents working in this repository (MSFS 2024 plugins, add-ons and tools). Read [`README.md`](./README.md) first. It is the project's SDK guideline and the source of conventions. This file lists what you must do differently as an agent.

## Environment

- Platform is Windows with PowerShell. Use PowerShell syntax, `\` paths when writing Windows commands, and `;` rather than `&&` if the PowerShell version does not support it.
- Microsoft Flight Simulator is usually **not running** while you work, and CI cannot run it. You can build and unit test, but you cannot verify sim behaviour yourself. Say so when it matters.
- The MSFS SDK is installed outside this repo. Find it through environment variables (`MSFS_SDK`, `MSFS2024_SDK`, `MSFS2020_SDK`). Do not assume a path, and do not copy SDK binaries into the repo.

## Golden rules

1. **Do not invent SDK facts.** Simvar names, event names, SimConnect functions, units, package formats and file paths must come from the official docs, the SDK samples, or existing code in this repo.
   - If you are unsure, say so, and mark the assumption in code with a `TODO(verify)` comment and in your reply.
   - Docs: <https://docs.flightsimulator.com/msfs2024>
2. **Prefer the lightest integration.** Use SimConnect in an external app first. Add a WASM module or in-sim panel only for a specific gap, and explain why (README section 1).
3. **Always specify units** when defining simvars, and note them in a comment or name.
4. **Keep SimConnect behind an interface.** Domain logic must not call SimConnect, audio, or network APIs directly. This keeps it testable without the sim.
5. **Never block the SimConnect dispatch loop** with slow work such as network calls, LLM calls or file I/O.
6. **Handle absence of the sim.** Code must cope with the sim not running at start, quitting mid-session, and reconnecting.
7. **No secrets in the repo.** API keys, tokens and credentials go in environment variables or untracked local files. Never print them to logs. Do not hard-code them in examples. Use placeholders.
8. **Do not touch the user's sim installation or data** without explicit instruction. That includes the Community folder, `exe.xml`, `UserCfg.opt`, and installed packages. Scripts that modify them must be opt-in and back up the original first.
9. **Ask before adding dependencies,** especially native libraries, paid or licensed data (for example Navigraph), or anything with licensing implications. Pin versions and commit lockfiles.
10. **Keep changes small and scoped.** Do not refactor unrelated code or reformat whole files.

## Repository layout

Follow the layout in README section 8:

- `shared/` holds reusable libraries.
- `plugins/<name>/` holds one plugin per folder, each with its own `README.md`, `src/`, `tests/` and `package/` if it ships an MSFS package.
- `docs/` holds design notes and decisions.
- `scripts/` holds build, package and install helpers.

If a needed folder does not exist yet, create it. Git does not track empty folders, so add a real file.

## Default stack

Unless the user or the plugin README says otherwise:

- **C# on .NET 8** for desktop or external apps, using the official `Microsoft.FlightSimulator.SimConnect` managed wrapper and NAudio for audio.
- **C/C++** for WASM modules only.
- **TypeScript / JS** for in-sim panels, or for Electron or Tauri UIs.
- **Python** for prototypes and data tools only.

Match the language and style already used in the plugin you are editing.

## Working on a new plugin

1. Read README section 14 (new plugin checklist) and follow it.
2. Create `plugins/<name>/README.md` first. State the goal, the integration approach and reasoning, the target sim versions and platform, and the build and run steps.
3. Define the `ISimClient`-style interface and a **fake** implementation before writing real SimConnect code.
4. Keep every simvar, event and facility query in one place with units.
5. Add logging to a known folder, and do not log secrets.

## Working on existing code

- Read the plugin's README and the surrounding code before editing.
- Reuse existing shared code instead of duplicating it.
- Keep the public interfaces stable. If you must break one, update every caller and the docs.
- Add or update tests for domain logic when you change it.

## Build, test and verify

- Build and test commands live in each plugin's README. Run them before saying a task is done. If you cannot run them, say so.
- For C#: `dotnet build` and `dotnet test` from the plugin or solution folder.
- For Node: use the lockfile's package manager (`npm ci`, `pnpm install --frozen-lockfile`, or `yarn install --frozen-lockfile`).
- For WASM or native builds: use the SDK's documented toolchain. Do not substitute another compiler setup without asking.
- Clearly separate in your report what you verified (built, unit tests passed) from what needs a **manual test in the sim**. Give the user a short manual test list when sim verification is needed.

## Packaging and distribution

- Use the SDK's Package Builder flow. Do not hand-edit `layout.json`, which is generated.
- Packages need a unique, vendor-prefixed name to avoid collisions in the Community folder.
- State supported sim version(s) and platform (PC or Xbox) in the plugin README.
- Xbox cannot run external executables. If the plugin must run on Xbox, only WASM and JS are options.

## Security and privacy

- Bind any local server (WebSocket or HTTP for panel-to-app traffic) to `127.0.0.1` and, if practical, require a token.
- Do not ship API keys inside distributed binaries. Use a proxy or bring-your-own-key.
- Be careful with microphone audio. Say clearly in the plugin README and UI when audio leaves the machine (for example cloud speech-to-text), and make it opt-in.
- Do not log raw audio or full transcripts by default.

## AI and voice features (ATC-style plugins)

- Keep the **authoritative state** (clearances, runways, squawk, sequence, frequency) in deterministic code. Use LLMs for intent parsing and phrasing, not for facts about the sim or airspace.
- Put STT, TTS and LLM providers behind interfaces so they can be swapped, mocked, or run locally.
- Stream where possible and design for a latency budget of roughly 2 seconds from key-up to a spoken reply.
- Validate LLM output against a schema before acting on it. Never pass raw model output straight into sim events.
- Treat data sources (weather, navdata, NOTAMs, VATSIM) as unreliable. Use timeouts, caching, and sensible fallbacks.

## Communication

- Be explicit about assumptions, especially SDK details you could not confirm from docs or samples.
- When a task needs the real sim to verify, say so and list the steps.
- If a request conflicts with these rules, for example committing a secret or editing the user's Community folder, stop and ask.
- Keep answers concise. Link to files and docs rather than pasting large blocks.

## Out of scope unless asked

- Redistributing SDK files, Microsoft or Asobo assets, or third-party data.
- Bypassing licensing or anti-tamper measures.
- Anything aimed at real-world aviation use. This project is for simulation only.
