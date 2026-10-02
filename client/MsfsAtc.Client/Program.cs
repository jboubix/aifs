using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Options;
using MsfsAtc.Client;
using MsfsAtc.Client.Audio;
using MsfsAtc.Client.Net;
using MsfsAtc.Client.Sim;

if (args.Contains("--list-devices"))
{
    Console.WriteLine("Audio devices (set Audio:InputDevice / Audio:OutputDevice in appsettings.json):");
    MicCapture.ListDevices(Console.WriteLine);
    return;
}

var builder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
{
    Args = args,
    ContentRootPath = AppContext.BaseDirectory, // find appsettings.json next to the exe
});

builder.Services.Configure<ServerOptions>(builder.Configuration.GetSection("Server"));
builder.Services.Configure<PilotOptions>(builder.Configuration.GetSection("Pilot"));
builder.Services.Configure<SimOptions>(builder.Configuration.GetSection("Sim"));
builder.Services.Configure<AudioOptions>(builder.Configuration.GetSection("Audio"));

builder.Services.AddSingleton<ISimConnection>(sp =>
{
    var mode = sp.GetRequiredService<IOptions<SimOptions>>().Value.Mode;
#if SIMCONNECT_SDK
    if (mode != SimMode.Mock) return ActivatorUtilities.CreateInstance<SimConnectSim>(sp);
#else
    if (mode == SimMode.SimConnect)
        throw new InvalidOperationException(
            "Sim:Mode is SimConnect but this build has no SimConnect support. " +
            "Install the MSFS SDK and rebuild (see client/README.md).");
#endif
    return ActivatorUtilities.CreateInstance<MockSim>(sp);
});

builder.Services.AddSingleton<ServerConnection>();
builder.Services.AddSingleton<MicCapture>();
builder.Services.AddSingleton<RadioPlayer>();
builder.Services.AddHostedService<AtcClientService>();

await builder.Build().RunAsync();
