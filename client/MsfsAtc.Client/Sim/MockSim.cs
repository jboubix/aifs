using Microsoft.Extensions.Logging;
using MsfsAtc.Client.Protocol;

namespace MsfsAtc.Client.Sim;

/// <summary>Stationary aircraft at a KSFO gate, so the whole pipeline can run without MSFS.</summary>
public sealed class MockSim(ILogger<MockSim> log) : ISimConnection
{
    public string Name => "Mock";
    public event Action<TelemetryMessage>? TelemetryReceived;

    public async Task RunAsync(CancellationToken ct)
    {
        log.LogWarning("Using MOCK simulator (aircraft parked at KSFO, COM1 121.900).");
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(1));
        try
        {
            while (await timer.WaitForNextTickAsync(ct))
            {
                TelemetryReceived?.Invoke(new TelemetryMessage
                {
                    Latitude = 37.6160,
                    Longitude = -122.3900,
                    AltitudeMslFt = 13,
                    AltitudeAglFt = 0,
                    HeadingTrue = 280,
                    OnGround = true,
                    Com1ActiveMhz = 121.900,
                    Com2ActiveMhz = 118.850,
                    TransponderCode = 1200,
                    AircraftTitle = "Mock Cessna 172",
                });
            }
        }
        catch (OperationCanceledException) { }
    }
}
