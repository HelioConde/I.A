using System.Diagnostics;
using System.Net.Http;
using System.Text;

Console.OutputEncoding = Encoding.UTF8;
Console.Title = "Brain-SSD V0";

var projectRoot = FindProjectRoot();
if (projectRoot is null)
{
    Fail("Não encontrei o projeto Brain-SSD. Mantenha o executável dentro da pasta do projeto.");
    return 2;
}

if (args.Length > 0) return RunMode(args[0].TrimStart('-').ToLowerInvariant(), projectRoot);

while (true)
{
    TryClear();
    Header(projectRoot);
    Console.WriteLine("  [1] Conversar com IA no CHAT VISUAL (Windows)");
    Console.WriteLine("  [2] Executar Brain-SSD local com HUD real");
    Console.WriteLine("  [3] Executar Brain-SSD local no terminal");
    Console.WriteLine("  [4] Testar o HUD com DEMO DATA");
    Console.WriteLine("  [5] Reproduzir resultado real da Fase 4D");
    Console.WriteLine("  [6] Abrir HUD live (aguardando eventos)");
    Console.WriteLine("  [7] Abrir a pasta do projeto para editar");
    Console.WriteLine("  [8] Diagnosticar instalacao do chat (CPU / GGUF / SSD)");
    Console.WriteLine("  [0] Sair");
    Console.Write("\nEscolha: ");
    switch (Console.ReadLine()?.Trim())
    {
        case "1": return RunMode("chat", projectRoot);
        case "2": return RunMode("brain", projectRoot);
        case "3": return RunMode("brain-terminal", projectRoot);
        case "4": return RunMode("demo", projectRoot);
        case "5": return RunMode("replay", projectRoot);
        case "6": return RunMode("live", projectRoot);
        case "8": return RunMode("doctor", projectRoot);
        case "7":
            Process.Start(new ProcessStartInfo("explorer.exe", projectRoot) { UseShellExecute = true });
            Console.WriteLine("Pasta aberta. Pressione qualquer tecla para voltar.");
            Console.ReadKey(true);
            break;
        case "0": return 0;
        default:
            Console.WriteLine("Opção inválida. Pressione qualquer tecla.");
            Console.ReadKey(true);
            break;
    }
}

static int RunMode(string mode, string root)
{
    var python = FindPython(root);
    if (python is null)
    {
        Fail("Python 3.11+ não foi encontrado. Instale Python e marque 'Add Python to PATH'.");
        return 3;
    }
    var functional = mode is "brain" or "brain-terminal";
    var chat = mode is "chat" or "conversa";
    var doctor = mode is "doctor";
    var scriptName = doctor ? "doctor_chat.py" : chat ? "run_chat.py" : functional ? "run_local_brain_ssd.py" : mode == "replay" ? "replay_hud.py" : "run_hud.py";
    var start = new ProcessStartInfo(python.Value.Command) { WorkingDirectory = root, UseShellExecute = false };
    foreach (var prefix in python.Value.PrefixArgs) start.ArgumentList.Add(prefix);
    start.ArgumentList.Add(Path.Combine(root, "tools", scriptName));
    if (mode == "brain") start.ArgumentList.Add("--hud");
    if (chat || doctor) { start.ArgumentList.Add("--profile"); start.ArgumentList.Add("economia"); }
    if (mode == "demo") start.ArgumentList.Add("--demo");
    if (!functional && !chat && !doctor)
    {
        start.ArgumentList.Add("--host"); start.ArgumentList.Add("127.0.0.1");
        start.ArgumentList.Add("--port"); start.ArgumentList.Add("8765");
    }
    TryClear(); Header(root);
    Console.WriteLine($"Modo: {mode.ToUpperInvariant()}");
    Console.WriteLine(doctor ? "Verificando requisitos. Nenhum modelo sera executado." : chat ? "O chat abrirá em http://127.0.0.1:8766" : mode == "brain" ? "O HUD abrirá em http://127.0.0.1:8765" : functional ? "Use /help para ver os comandos." : "O navegador abrirá em http://127.0.0.1:8765");
    Console.WriteLine("Feche esta janela ou pressione Ctrl+C para encerrar.\n");
    try
    {
        using var child = Process.Start(start);
        if (child is null) throw new InvalidOperationException("O processo Python não iniciou.");
        if (!functional && !chat && !doctor) _ = OpenBrowserWhenReady();
        child.WaitForExit();
        return child.ExitCode;
    }
    catch (Exception error)
    {
        Fail($"Falha ao iniciar: {error.Message}");
        return 4;
    }
}

static async Task OpenBrowserWhenReady()
{
    using var client = new HttpClient { Timeout = TimeSpan.FromMilliseconds(600) };
    for (var attempt = 0; attempt < 40; attempt++)
    {
        try
        {
            using var response = await client.GetAsync("http://127.0.0.1:8765/api/health");
            if (response.IsSuccessStatusCode)
            {
                Process.Start(new ProcessStartInfo("http://127.0.0.1:8765") { UseShellExecute = true });
                return;
            }
        }
        catch (HttpRequestException) { }
        catch (TaskCanceledException) { }
        await Task.Delay(250);
    }
}

static (string Command, string[] PrefixArgs)? FindPython(string root)
{
    var candidates = new[]
    {
        (Command: Path.Combine(root, ".venv", "Scripts", "python.exe"), PrefixArgs: Array.Empty<string>()),
        (Command: "py.exe", PrefixArgs: new[] { "-3.11" }),
        (Command: "python.exe", PrefixArgs: Array.Empty<string>()),
        (Command: "python3.exe", PrefixArgs: Array.Empty<string>()),
    };
    foreach (var candidate in candidates)
    {
        try
        {
            var check = new ProcessStartInfo(candidate.Command) { UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true };
            foreach (var prefix in candidate.PrefixArgs) check.ArgumentList.Add(prefix);
            check.ArgumentList.Add("-c");
            check.ArgumentList.Add("import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)");
            using var process = Process.Start(check);
            process?.WaitForExit(4000);
            if (process?.ExitCode == 0) return candidate;
        }
        catch { }
    }
    return null;
}

static string? FindProjectRoot()
{
    foreach (var start in new[] { AppContext.BaseDirectory, Environment.CurrentDirectory })
    {
        var directory = new DirectoryInfo(start);
        for (var level = 0; directory is not null && level < 6; level++, directory = directory.Parent)
            if (File.Exists(Path.Combine(directory.FullName, "tools", "run_local_brain_ssd.py")) && Directory.Exists(Path.Combine(directory.FullName, "hud"))) return directory.FullName;
    }
    return null;
}

static void Header(string root)
{
    Console.ForegroundColor = ConsoleColor.Cyan;
    Console.WriteLine("BRAIN-SSD V0 · WINDOWS NATIVE FUNCTIONAL");
    Console.ResetColor();
    Console.WriteLine("Launcher local · CPU-only · código permanece editável\n");
    Console.ForegroundColor = ConsoleColor.DarkGray;
    Console.WriteLine($"Projeto: {root}\n");
    Console.ResetColor();
}

static void TryClear() { try { Console.Clear(); } catch (IOException) { } }

static void Fail(string message)
{
    Console.ForegroundColor = ConsoleColor.Red;
    Console.Error.WriteLine(message);
    Console.ResetColor();
    Console.Error.WriteLine("Pressione qualquer tecla para fechar.");
    try { Console.ReadKey(true); } catch (InvalidOperationException) { } catch (IOException) { }
}
