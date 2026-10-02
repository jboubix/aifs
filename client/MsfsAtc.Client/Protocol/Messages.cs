using System.Text.Json;

namespace MsfsAtc.Client.Protocol;

// Wire protocol, mirrored by server/src/atc_server/gateway/protocol.py.
// JSON uses snake_case; audio travels in binary frames (PCM16 LE mono).

public static class Json
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    public static string Serialize(object message) =>
        JsonSerializer.Serialize(message, message.GetType(), Options);
}

public sealed record HelloMessage(string ClientVersion, string Callsign)
{
    public string Type => "hello";
}

public sealed record TelemetryMessage
{
    public string Type => "telemetry";
    public double Latitude { get; init; }
    public double Longitude { get; init; }
    public double AltitudeMslFt { get; init; }
    public double AltitudeAglFt { get; init; }
    public double HeadingTrue { get; init; }
    public double GroundSpeedKt { get; init; }
    public double IndicatedAirspeedKt { get; init; }
    public bool OnGround { get; init; }
    public double Com1ActiveMhz { get; init; }
    public double Com2ActiveMhz { get; init; }
    public bool ComTransmit1 { get; init; } = true;
    public bool ComTransmit2 { get; init; }
    public int TransponderCode { get; init; } = 1200;
    public bool AvionicsOn { get; init; } = true;
    public string Callsign { get; init; } = "";
    public string AircraftTitle { get; init; } = "";

    /// <summary>The radio (1 or 2) a PTT press should transmit on.</summary>
    public (int Radio, double FrequencyMhz) TransmitRadio() =>
        ComTransmit2 && !ComTransmit1 ? (2, Com2ActiveMhz) : (1, Com1ActiveMhz);
}

public sealed record PttStartMessage(int Radio, double FrequencyMhz)
{
    public string Type => "ptt_start";
}

public sealed record PttEndMessage
{
    public string Type => "ptt_end";
}
