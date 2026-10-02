using System.Text.Json;
using System.Threading.Channels;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using MsfsAtc.Client.Audio;
using MsfsAtc.Client.Input;
using MsfsAtc.Client.Net;
using MsfsAtc.Client.Protocol;
using MsfsAtc.Client.Sim;

namespace MsfsAtc.Client;

/// <summary>
/// Glue: sim telemetry -> server, PTT + microphone -> server, server audio -> speakers.
/// All outbound traffic goes through one queue so ptt_start, audio and ptt_end stay in order.
/// </summary>
public sealed class AtcClientService(
    ISimConnection sim,
    ServerConnection server,
    MicCapture mic,
    RadioPlayer player,
    IOptions<AudioOptions> audioOptions,
    IOptions<SimOptions> simOptions,
    IOptions<PilotOptions> pilotOptions,
    ILogger<AtcClientService> log) : BackgroundService
{
    private const string ClientVersion = "0.1.0";

    private readonly Channel<object> _outbound = Channel.CreateUnbounded<object>(
        new UnboundedChannelOptions { SingleReader = true });

    private volatile TelemetryMessage? _latest;
    private long _lastTelemetrySentTicks;
    private long _lastStatusLogTicks;
    private volatile bool _pttActive;
    private int _pttPeak;
    private int _pttBytes;

    private void NoteLevel(byte[] pcm)
    {
        var peak = 0;
        for (var i = 0; i + 1 < pcm.Length; i += 2)
        {
            var sample = Math.Abs(BitConverter.ToInt16(pcm, i));
            if (sample > peak) peak = sample;
        }
        int current;
        while (peak > (current = _pttPeak) && Interlocked.CompareExchange(ref _pttPeak, peak, current) != current) { }
        Interlocked.Add(ref _pttBytes, pcm.Length);
    }

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        var ptt = new PttKey(audioOptions.Value.PttKey);
        log.LogInformation("Sim source: {Sim}. Hold [{Key}] to transmit.", sim.Name, ptt.Name);

        sim.TelemetryReceived += OnTelemetry;
        server.Connected += OnConnected;
        server.TextReceived += OnServerText;
        server.BinaryReceived += player.Append;
        mic.DataAvailable += pcm =>
        {
            if (!_pttActive) return;
            NoteLevel(pcm);
            _outbound.Writer.TryWrite(pcm);
        };
        mic.Start();

        await Task.WhenAll(
            sim.RunAsync(ct),
            server.RunAsync(ct),
            SendLoopAsync(ct),
            PttLoopAsync(ptt, ct));
    }

    // ---- sim -> server -----------------------------------------------------------------------

    private void OnTelemetry(TelemetryMessage t)
    {
        var callsign = string.IsNullOrWhiteSpace(pilotOptions.Value.Callsign)
            ? t.Callsign
            : pilotOptions.Value.Callsign;
        t = t with { Callsign = callsign };
        var first = _latest is null;
        _latest = t;

        var now = Environment.TickCount64;
        if (first || now - _lastStatusLogTicks >= 10_000)
        {
            _lastStatusLogTicks = now;
            log.LogInformation(
                "SIM: {Aircraft} | {Lat:F4},{Lon:F4} | {Alt:F0} ft | {State} | COM1 {C1:F3} COM2 {C2:F3} (TX COM{Tx}) | XPDR {Xpdr:D4} | avionics {Av}",
                string.IsNullOrEmpty(t.AircraftTitle) ? "?" : t.AircraftTitle, t.Latitude, t.Longitude,
                t.AltitudeMslFt, t.OnGround ? "ground" : "airborne", t.Com1ActiveMhz, t.Com2ActiveMhz,
                t.TransmitRadio().Radio, t.TransponderCode, t.AvionicsOn ? "on" : "off");
        }

        if (now - Interlocked.Read(ref _lastTelemetrySentTicks) >= simOptions.Value.TelemetryIntervalMs)
        {
            Interlocked.Exchange(ref _lastTelemetrySentTicks, now);
            _outbound.Writer.TryWrite(t);
        }
    }

    private Task OnConnected()
    {
        _outbound.Writer.TryWrite(new HelloMessage(ClientVersion, pilotOptions.Value.Callsign));
        if (_latest is { } t) _outbound.Writer.TryWrite(t);
        return Task.CompletedTask;
    }

    // ---- push to talk ------------------------------------------------------------------------

    private async Task PttLoopAsync(PttKey key, CancellationToken ct)
    {
        var ignoringUntilRelease = false;
        using var timer = new PeriodicTimer(TimeSpan.FromMilliseconds(15));
        try
        {
            while (await timer.WaitForNextTickAsync(ct))
            {
                var down = key.IsDown;
                if (!down) ignoringUntilRelease = false;

                if (down && !_pttActive && !ignoringUntilRelease)
                {
                    var t = _latest;
                    if (!server.IsConnected)
                    {
                        log.LogWarning("PTT ignored: not connected to the server.");
                        ignoringUntilRelease = true;
                    }
                    else if (t is { AvionicsOn: false })
                    {
                        log.LogWarning("PTT ignored: avionics are off.");
                        ignoringUntilRelease = true;
                    }
                    else
                    {
                        var (radio, freq) = t?.TransmitRadio() ?? (1, 0.0);
                        _outbound.Writer.TryWrite(new PttStartMessage(radio, freq));
                        _pttActive = true; // set after ptt_start is queued so audio can't overtake it
                        log.LogInformation("TX COM{Radio} {Freq:F3} ...", radio, freq);
                    }
                }
                else if (!down && _pttActive)
                {
                    _pttActive = false;
                    _outbound.Writer.TryWrite(new PttEndMessage());
                    var peak = Interlocked.Exchange(ref _pttPeak, 0);
                    var bytes = Interlocked.Exchange(ref _pttBytes, 0);
                    log.LogInformation(
                        "TX end: {Seconds:F1}s captured, peak {Peak:P0}",
                        bytes / 2.0 / MicCapture.SampleRate, peak / 32768.0);
                }
            }
        }
        catch (OperationCanceledException) { }
    }

    // ---- outbound queue ----------------------------------------------------------------------

    private async Task SendLoopAsync(CancellationToken ct)
    {
        try
        {
            await foreach (var item in _outbound.Reader.ReadAllAsync(ct))
            {
                if (!server.IsConnected) continue; // drop while offline
                if (item is byte[] pcm) await server.SendAudioAsync(pcm, ct);
                else await server.SendAsync(item, ct);
            }
        }
        catch (OperationCanceledException) { }
    }

    // ---- server -> client --------------------------------------------------------------------

    private void OnServerText(string type, JsonElement msg)
    {
        switch (type)
        {
            case "welcome":
                log.LogInformation("Session {Id} ready.", msg.GetProperty("session_id").GetString());
                break;
            case "transcript":
                var speaker = msg.GetProperty("speaker").GetString();
                var text = msg.GetProperty("text").GetString();
                var freq = msg.TryGetProperty("frequency_mhz", out var f) ? f.GetDouble() : 0;
                if (speaker == "pilot") log.LogInformation("PILOT: {Text}", text);
                else log.LogInformation("ATC [{Freq:F3}]: {Text}", freq, text);
                break;
            case "audio_start":
                player.Begin(msg.GetProperty("sample_rate").GetInt32());
                break;
            case "audio_end":
                player.End();
                break;
            case "error":
                log.LogWarning("Server error: {Msg}", msg.GetProperty("message").GetString());
                break;
            default:
                log.LogDebug("Unhandled server message type '{Type}'.", type);
                break;
        }
    }
}
