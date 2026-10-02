#if SIMCONNECT_SDK
using System.Runtime.InteropServices;
using Microsoft.Extensions.Logging;
using Microsoft.FlightSimulator.SimConnect;
using MsfsAtc.Client.Protocol;

namespace MsfsAtc.Client.Sim;

/// <summary>
/// Real MSFS connection through the managed SimConnect wrapper. Uses an event handle instead of a
/// window message pump, so it works from a console or background service.
/// Compiled only when the MSFS SDK DLLs are found (see the csproj).
/// </summary>
public sealed class SimConnectSim(ILogger<SimConnectSim> log) : ISimConnection
{
    private enum Defs : uint { Telemetry }
    private enum Reqs : uint { Telemetry }

    // Field order MUST match the AddToDataDefinition order below.
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi, Pack = 1)]
    private struct TelemetryStruct
    {
        public double Latitude;
        public double Longitude;
        public double AltitudeMslFt;
        public double AltitudeAglFt;
        public double HeadingTrue;
        public double GroundSpeedKt;
        public double IndicatedAirspeedKt;
        public double Com1Mhz;
        public double Com2Mhz;
        public int OnGround;
        public int ComTransmit1;
        public int ComTransmit2;
        public int TransponderCode;
        public int AvionicsOn;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string AtcId;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string Title;
    }

    public string Name => "SimConnect";
    public event Action<TelemetryMessage>? TelemetryReceived;

    public async Task RunAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                await Task.Run(() => RunSession(ct), ct);
            }
            catch (OperationCanceledException) { break; }
            catch (COMException)
            {
                log.LogInformation("MSFS is not running (or SimConnect is unavailable). Retrying in 5 s...");
            }
            catch (Exception ex)
            {
                log.LogError(ex, "SimConnect session failed. Retrying in 5 s...");
            }

            try { await Task.Delay(TimeSpan.FromSeconds(5), ct); }
            catch (OperationCanceledException) { break; }
        }
    }

    private void RunSession(CancellationToken ct)
    {
        using var signal = new AutoResetEvent(false);
        var sc = new SimConnect("MSFS ATC Client", IntPtr.Zero, 0, signal, 0); // throws COMException if MSFS is down
        var quit = false;

        sc.OnRecvOpen += (_, d) => log.LogInformation("Connected to {App} {Ver}", d.szApplicationName, $"{d.dwApplicationVersionMajor}.{d.dwApplicationVersionMinor}");
        sc.OnRecvQuit += (_, _) => { quit = true; log.LogInformation("MSFS closed the connection."); };
        sc.OnRecvException += (_, e) => log.LogWarning("SimConnect exception {Code} (send id {Id}, index {Idx})", (SIMCONNECT_EXCEPTION)e.dwException, e.dwSendID, e.dwIndex);
        sc.OnRecvSimobjectData += OnData;

        void Add(string name, string units, SIMCONNECT_DATATYPE type) =>
            sc.AddToDataDefinition(Defs.Telemetry, name, units, type, 0.0f, SimConnect.SIMCONNECT_UNUSED);

        Add("PLANE LATITUDE", "degrees", SIMCONNECT_DATATYPE.FLOAT64);
        Add("PLANE LONGITUDE", "degrees", SIMCONNECT_DATATYPE.FLOAT64);
        Add("PLANE ALTITUDE", "feet", SIMCONNECT_DATATYPE.FLOAT64);
        Add("PLANE ALT ABOVE GROUND", "feet", SIMCONNECT_DATATYPE.FLOAT64);
        Add("PLANE HEADING DEGREES TRUE", "degrees", SIMCONNECT_DATATYPE.FLOAT64);
        Add("GROUND VELOCITY", "knots", SIMCONNECT_DATATYPE.FLOAT64);
        Add("AIRSPEED INDICATED", "knots", SIMCONNECT_DATATYPE.FLOAT64);
        Add("COM ACTIVE FREQUENCY:1", "MHz", SIMCONNECT_DATATYPE.FLOAT64);
        Add("COM ACTIVE FREQUENCY:2", "MHz", SIMCONNECT_DATATYPE.FLOAT64);
        Add("SIM ON GROUND", "bool", SIMCONNECT_DATATYPE.INT32);
        Add("COM TRANSMIT:1", "bool", SIMCONNECT_DATATYPE.INT32);
        Add("COM TRANSMIT:2", "bool", SIMCONNECT_DATATYPE.INT32);
        Add("TRANSPONDER CODE:1", "Bco16", SIMCONNECT_DATATYPE.INT32); // BCD -> reads as 1200
        Add("AVIONICS MASTER SWITCH", "bool", SIMCONNECT_DATATYPE.INT32);
        Add("ATC ID", null!, SIMCONNECT_DATATYPE.STRING32);
        Add("TITLE", null!, SIMCONNECT_DATATYPE.STRING256);
        sc.RegisterDataDefineStruct<TelemetryStruct>(Defs.Telemetry);

        sc.RequestDataOnSimObject(Reqs.Telemetry, Defs.Telemetry, SimConnect.SIMCONNECT_OBJECT_ID_USER,
            SIMCONNECT_PERIOD.SECOND, SIMCONNECT_DATA_REQUEST_FLAG.DEFAULT, 0, 0, 0);

        WaitHandle[] handles = [signal, ct.WaitHandle];
        try
        {
            while (!quit && !ct.IsCancellationRequested)
            {
                if (WaitHandle.WaitAny(handles, 500) == 0)
                    sc.ReceiveMessage();
            }
        }
        finally
        {
            sc.Dispose();
        }
    }

    /// <summary>The sim returns the squawk as BCD (0x7000 for 7000); turn it into the decimal digits.</summary>
    private static int DecodeBcd16(int v) =>
        ((v >> 12) & 0xF) * 1000 + ((v >> 8) & 0xF) * 100 + ((v >> 4) & 0xF) * 10 + (v & 0xF);

    private void OnData(SimConnect sender, SIMCONNECT_RECV_SIMOBJECT_DATA data)
    {
        if (data.dwRequestID != (uint)Reqs.Telemetry) return;
        var s = (TelemetryStruct)data.dwData[0];

        TelemetryReceived?.Invoke(new TelemetryMessage
        {
            Latitude = s.Latitude,
            Longitude = s.Longitude,
            AltitudeMslFt = s.AltitudeMslFt,
            AltitudeAglFt = s.AltitudeAglFt,
            HeadingTrue = s.HeadingTrue,
            GroundSpeedKt = s.GroundSpeedKt,
            IndicatedAirspeedKt = s.IndicatedAirspeedKt,
            Com1ActiveMhz = s.Com1Mhz,
            Com2ActiveMhz = s.Com2Mhz,
            OnGround = s.OnGround != 0,
            ComTransmit1 = s.ComTransmit1 != 0,
            ComTransmit2 = s.ComTransmit2 != 0,
            TransponderCode = DecodeBcd16(s.TransponderCode),
            AvionicsOn = s.AvionicsOn != 0,
            Callsign = s.AtcId,
            AircraftTitle = s.Title,
        });
    }
}
#endif
