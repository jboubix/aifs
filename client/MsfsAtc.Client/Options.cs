namespace MsfsAtc.Client;

public sealed class ServerOptions
{
    public string Url { get; set; } = "ws://localhost:8000/ws";
    public string Token { get; set; } = "";
}

public sealed class PilotOptions
{
    public string Callsign { get; set; } = "";
}

public enum SimMode
{
    /// <summary>SimConnect if compiled in, otherwise the mock simulator.</summary>
    Auto,
    SimConnect,
    Mock,
}

public sealed class SimOptions
{
    public SimMode Mode { get; set; } = SimMode.Auto;
    public int TelemetryIntervalMs { get; set; } = 1000;
}

public sealed class AudioOptions
{
    /// <summary>Key name (F9, CapsLock, LeftCtrl, ...) or hex virtual-key code (0x75).</summary>
    public string PttKey { get; set; } = "F9";

    /// <summary>NAudio device index, -1 for the system default. Ignored when <see cref="InputDeviceName"/> matches a device.</summary>
    public int InputDevice { get; set; } = -1;

    /// <summary>Case-insensitive substring of the input device name, e.g. "NexiGo". Empty uses <see cref="InputDevice"/>.</summary>
    public string InputDeviceName { get; set; } = "";

    public int OutputDevice { get; set; } = -1;
}
