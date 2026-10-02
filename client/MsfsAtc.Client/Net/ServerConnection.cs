using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using MsfsAtc.Client.Protocol;

namespace MsfsAtc.Client.Net;

/// <summary>WebSocket link to the ATC server with automatic reconnect.</summary>
public sealed class ServerConnection(IOptions<ServerOptions> options, ILogger<ServerConnection> log)
{
    private readonly ServerOptions _opt = options.Value;
    private readonly SemaphoreSlim _sendLock = new(1, 1);
    private volatile ClientWebSocket? _ws;

    public bool IsConnected => _ws?.State == WebSocketState.Open;

    /// <summary>Raised after every (re)connect.</summary>
    public event Func<Task>? Connected;

    /// <summary>A JSON text frame: (type, full document).</summary>
    public event Action<string, JsonElement>? TextReceived;

    /// <summary>A binary (audio) frame.</summary>
    public event Action<byte[]>? BinaryReceived;

    public async Task RunAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            using var ws = new ClientWebSocket();
            try
            {
                var uri = BuildUri();
                log.LogInformation("Connecting to {Url} ...", _opt.Url);
                await ws.ConnectAsync(uri, ct);
                _ws = ws;
                log.LogInformation("Connected to server.");
                if (Connected is { } handler) await handler();
                await ReceiveLoopAsync(ws, ct);
            }
            catch (OperationCanceledException) { break; }
            catch (Exception ex)
            {
                log.LogWarning("Server connection lost: {Msg}", ex.Message);
            }
            finally
            {
                _ws = null;
            }

            try { await Task.Delay(TimeSpan.FromSeconds(3), ct); }
            catch (OperationCanceledException) { break; }
        }
    }

    private Uri BuildUri()
    {
        var b = new UriBuilder(_opt.Url);
        if (!string.IsNullOrEmpty(_opt.Token))
            b.Query = "token=" + Uri.EscapeDataString(_opt.Token);
        return b.Uri;
    }

    private async Task ReceiveLoopAsync(ClientWebSocket ws, CancellationToken ct)
    {
        var buffer = new byte[16 * 1024];
        using var message = new MemoryStream();

        while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
        {
            message.SetLength(0);
            WebSocketReceiveResult result;
            do
            {
                result = await ws.ReceiveAsync(buffer, ct);
                if (result.MessageType == WebSocketMessageType.Close)
                {
                    log.LogInformation("Server closed the connection ({Status}).", result.CloseStatus);
                    return;
                }
                message.Write(buffer, 0, result.Count);
            } while (!result.EndOfMessage);

            if (result.MessageType == WebSocketMessageType.Binary)
            {
                BinaryReceived?.Invoke(message.ToArray());
            }
            else
            {
                try
                {
                    using var doc = JsonDocument.Parse(message.ToArray());
                    var type = doc.RootElement.TryGetProperty("type", out var t) ? t.GetString() ?? "" : "";
                    TextReceived?.Invoke(type, doc.RootElement.Clone());
                }
                catch (JsonException ex)
                {
                    log.LogWarning("Ignoring malformed server message: {Msg}", ex.Message);
                }
            }
        }
    }

    public Task<bool> SendAsync(object message, CancellationToken ct = default) =>
        SendAsync(Encoding.UTF8.GetBytes(Json.Serialize(message)), WebSocketMessageType.Text, ct);

    public Task<bool> SendAudioAsync(ReadOnlyMemory<byte> pcm, CancellationToken ct = default) =>
        SendAsync(pcm, WebSocketMessageType.Binary, ct);

    private async Task<bool> SendAsync(ReadOnlyMemory<byte> data, WebSocketMessageType type, CancellationToken ct)
    {
        var ws = _ws;
        if (ws is not { State: WebSocketState.Open }) return false;

        await _sendLock.WaitAsync(ct);
        try
        {
            await ws.SendAsync(data, type, endOfMessage: true, ct);
            return true;
        }
        catch (Exception ex) when (ex is WebSocketException or ObjectDisposedException or InvalidOperationException)
        {
            return false; // the receive loop will notice and reconnect
        }
        finally
        {
            _sendLock.Release();
        }
    }
}
