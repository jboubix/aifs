# MSFS client

.NET 8 console app (Windows, x64). It is deliberately thin: sim data in, audio in/out, no AI.

## Run

```powershell
dotnet run --project MsfsAtc.Client              # uses appsettings.json
dotnet run --project MsfsAtc.Client -- --list-devices
```

Settings are in `MsfsAtc.Client/appsettings.json` (server URL/token, callsign, PTT key, audio
devices, `Sim:Mode`). Any setting can be overridden on the command line, e.g.
`-- --Sim:Mode=Mock --Audio:PttKey=CapsLock`.

PTT is a global key poll, so it works while MSFS has focus. Joystick buttons are not wired up yet.

## Real SimConnect

SimConnect binaries come from the MSFS SDK and are not redistributable, so they are not in the
repo. The project builds without them and falls back to a mock sim (aircraft parked at KSFO).

1. In MSFS 2024: Options -> General -> Developers -> enable Developer Mode, then
   Help -> SDK Installer.
2. Build. The csproj finds the SDK via `%MSFS2024_SDK%` / `%MSFS_SDK%`, or from
   `client/libs/simconnect/` (copy `Microsoft.FlightSimulator.SimConnect.dll` from
   `SimConnect SDK\lib\managed\` and `SimConnect.dll` from `SimConnect SDK\lib\`).
   The build prints "SimConnect SDK found" when it works.
3. `Sim:Mode` `Auto` then uses SimConnect. `SimConnectSim.cs` only compiles in this case.

`Sim/SimConnectSim.cs` has not been compiled or run against a live sim yet, because the SDK was
not installed when it was written. Expect to fix small API details on the first build.

## Layout

```
MsfsAtc.Client/
  Program.cs            host + DI
  AtcClientService.cs   wiring: telemetry, PTT, outbound queue, server messages
  Sim/                  ISimConnection, SimConnectSim (SDK), MockSim
  Net/ServerConnection  WebSocket with auto-reconnect
  Audio/                MicCapture (NAudio), RadioPlayer
  Input/PttKey.cs       global push-to-talk key
  Protocol/Messages.cs  wire messages (mirror of server protocol.py)
```
