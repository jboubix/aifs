using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NAudio.Wave;

namespace MsfsAtc.Client.Audio;

/// <summary>Plays streamed PCM16 mono audio from the server. A new transmission replaces the previous one.</summary>
public sealed class RadioPlayer(IOptions<AudioOptions> options, ILogger<RadioPlayer> log) : IDisposable
{
    private readonly object _gate = new();
    private BufferedWaveProvider? _buffer;
    private WaveOutEvent? _out;

    public void Begin(int sampleRate)
    {
        lock (_gate)
        {
            StopLocked();
            try
            {
                _buffer = new BufferedWaveProvider(new WaveFormat(sampleRate, 16, 1))
                {
                    BufferDuration = TimeSpan.FromSeconds(30),
                    DiscardOnBufferOverflow = true,
                };
                _out = new WaveOutEvent { DeviceNumber = options.Value.OutputDevice };
                _out.Init(_buffer);
                // Play() on an empty buffer makes WaveOut read zero bytes and stop.
                // The first Append starts playback once samples exist.
            }
            catch (Exception ex)
            {
                log.LogError(ex, "Could not open audio output device.");
                StopLocked();
            }
        }
    }

    public void Append(byte[] pcm)
    {
        lock (_gate)
        {
            if (_buffer is null || _out is null || pcm.Length == 0) return;
            _buffer.AddSamples(pcm, 0, pcm.Length);
            if (_out.PlaybackState != PlaybackState.Playing)
                _out.Play();
        }
    }

    /// <summary>No more data is coming; already-buffered audio finishes playing.</summary>
    public void End() { }

    private void StopLocked()
    {
        _out?.Dispose();
        _out = null;
        _buffer = null;
    }

    public void Dispose()
    {
        lock (_gate) StopLocked();
    }
}
