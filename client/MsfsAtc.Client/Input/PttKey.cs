using System.Runtime.InteropServices;

namespace MsfsAtc.Client.Input;

/// <summary>Global (works while MSFS has focus) push-to-talk key, polled with GetAsyncKeyState.</summary>
public sealed class PttKey
{
    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);

    private static readonly Dictionary<string, int> Aliases = new(StringComparer.OrdinalIgnoreCase)
    {
        ["LeftShift"] = 0xA0, ["RightShift"] = 0xA1,
        ["LeftCtrl"] = 0xA2, ["RightCtrl"] = 0xA3,
        ["LeftAlt"] = 0xA4, ["RightAlt"] = 0xA5,
        ["CapsLock"] = 0x14, ["Space"] = 0x20, ["Tab"] = 0x09,
        ["Mouse4"] = 0x05, ["Mouse5"] = 0x06, ["MiddleMouse"] = 0x04,
        ["NumPad0"] = 0x60, ["NumPadEnter"] = 0x0D, ["Insert"] = 0x2D,
    };

    public string Name { get; }
    private readonly int _vk;

    public PttKey(string name)
    {
        Name = name;
        _vk = Parse(name);
    }

    public bool IsDown => (GetAsyncKeyState(_vk) & 0x8000) != 0;

    private static int Parse(string name)
    {
        if (name.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            && int.TryParse(name[2..], System.Globalization.NumberStyles.HexNumber, null, out var hex))
            return hex;
        if (Aliases.TryGetValue(name, out var vk)) return vk;
        if (Enum.TryParse<ConsoleKey>(name, ignoreCase: true, out var ck)) return (int)ck;
        throw new ArgumentException($"Unknown PTT key '{name}'. Use a key name (F9, CapsLock, LeftCtrl...) or a hex code like 0x75.");
    }
}
