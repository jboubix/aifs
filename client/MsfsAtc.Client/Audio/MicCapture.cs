using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NAudio.Wave;

namespace MsfsAtc.Client.Audio;

/// <summary>Continuously captures 16 kHz mono PCM16 from the microphone. Consumers decide what to keep.</summary>
public sealed class MicCapture(IOptions<AudioOptions> options, ILogger<MicCapture> log) : IDisposable
{
    public const int SampleRate = 16000;

    private WaveInEvent? _wave;

    /// <summary>Raised on a NAudio thread with a chunk of PCM16 (about 50 ms).</summary>
    public event Action<byte[]>? DataAvailable;

    public bool Start()
    {
        if (WaveInEvent.DeviceCount == 0)
        {
            log.LogError("No audio input device found. Push-to-talk is disabled.");
            return false;
        }

        var deviceNumber = ResolveInputDevice(options.Value.InputDevice, options.Value.InputDeviceName, log);
        _wave = new WaveInEvent
        {
            DeviceNumber = deviceNumber, // -1 = Windows default (wave mapper)
            WaveFormat = new WaveFormat(SampleRate, 16, 1),
            BufferMilliseconds = 50,
        };
        _wave.DataAvailable += (_, e) =>
        {
            var copy = new byte[e.BytesRecorded];
            Buffer.BlockCopy(e.Buffer, 0, copy, 0, e.BytesRecorded);
            DataAvailable?.Invoke(copy);
        };
        _wave.RecordingStopped += (_, e) =>
        {
            if (e.Exception is not null) log.LogError(e.Exception, "Microphone stopped unexpectedly.");
        };
        _wave.StartRecording();
        log.LogInformation("Microphone: {Name}", WaveInEvent.GetCapabilities(_wave.DeviceNumber).ProductName);
        return true;
    }

    public void Dispose()
    {
        _wave?.Dispose();
        _wave = null;
    }

    /// <summary>Name match wins over the numeric index, so a webcam stays selected if Windows reorders devices.</summary>
    public static int ResolveInputDevice(int configured, string name, ILogger? log = null)
    {
        if (string.IsNullOrWhiteSpace(name)) return configured;

        for (var i = 0; i < WaveInEvent.DeviceCount; i++)
        {
            var product = WaveInEvent.GetCapabilities(i).ProductName;
            if (product.Contains(name, StringComparison.OrdinalIgnoreCase))
            {
                log?.LogInformation("Input device '{Name}' matched index {Index}: {Product}", name, i, product);
                return i;
            }
        }

        log?.LogError("No input device matching '{Name}'. Falling back to device {Index}.", name, configured);
        return configured;
    }

    public static void ListDevices(Action<string> write)
    {
        for (var i = 0; i < WaveInEvent.DeviceCount; i++)
            write($"  input  {i}: {WaveInEvent.GetCapabilities(i).ProductName}");
        for (var i = 0; i < WaveOut.DeviceCount; i++)
            write($"  output {i}: {WaveOut.GetCapabilities(i).ProductName}");
    }
}
