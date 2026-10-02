using MsfsAtc.Client.Protocol;

namespace MsfsAtc.Client.Sim;

/// <summary>Source of simulator state. Real (SimConnect) or mock.</summary>
public interface ISimConnection
{
    string Name { get; }

    /// <summary>Raised on the most recent data from the sim (about once per second).</summary>
    event Action<TelemetryMessage>? TelemetryReceived;

    /// <summary>Runs until cancelled, reconnecting as needed.</summary>
    Task RunAsync(CancellationToken ct);
}
