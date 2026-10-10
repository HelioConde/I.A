# Brain-SSD Chat — primeiro objetivo no Windows

## Objetivo

Chat visual em português: caixa de mensagem, Enter para enviar, Shift+Enter
para quebrar linha, indicador de processamento, histórico da sessão,
nova conversa e painel de métricas experimentais.

**As respostas vêm do Qwen3-0.6B local em CPU**, não de respostas falsas ou
de uma API externa. Perguntas não triviais consultam a base de conhecimento
armazenada em SSD usando a recuperação já existente.

A interface de conversa é **experimental** e preserva os benchmarks
congelados das Fases 1–4D, sem reivindicar a validação física 4E.

## Iniciar no Windows

Requisitos: Windows 10/11 x64; Python 3.11+; o projeto completo; runtime
llama.cpp CPU-only e modelo Qwen3-0.6B-Q8_0.gguf locais; corpus/índice Brain-SSD.

1. Dê dois cliques em **INICIAR-CHAT-WINDOWS.bat**, na raiz do projeto.
2. O terminal inicia o servidor em loopback e abre o navegador.
3. Acesse **http://127.0.0.1:8766**. Quando aparecer "Modelo local pronto",
   digite "Olá" e pressione Enter. A resposta virá da IA local.
4. Mantenha o terminal aberto. Ctrl+C encerra a aplicação.

PowerShell: python tools/run_chat.py

Sem abrir automaticamente o navegador: python tools/run_chat.py --no-open-browser

Se faltarem o GGUF, executável llama-completion ou corpus/índice, prepare
o runtime seguindo [WINDOWS_NATIVE_RUNTIME.md](WINDOWS_NATIVE_RUNTIME.md),
incluindo python tools/setup_windows_runtime.py. Nem todos os binários
e dados locais são distribuídos neste repositório.

O código do launcher .NET inclui a opção Chat. Para reconstruir
**dist/windows/BrainSSD.exe** com a nova opção é necessário .NET 8 e executar:
powershell -ExecutionPolicy Bypass -File tools/build_windows_launcher.ps1

**O executável já versionado não é automaticamente atualizado** por mudanças
em Program.cs. Até recompilar, use o arquivo .bat.

## Privacidade e limites

- Frontend e API: apenas 127.0.0.1:8766; POST exige Origin local. Não
  exponha a porta por túnel ou encaminhamento.
- Histórico temporário só na aba; a UI envia até 8 mensagens recentes para
  o processo local. Não há armazenamento de conversas em nuvem.
- O Core executa CPU-only com --device none. RAM e velocidade reais
  dependem da máquina e da pergunta. GPU dedicada não é necessária.
- O modo subprocesso recarrega o modelo por pergunta (mais lento).
  --core-mode persistent é experimental e depende de llama-server local.
- Medidas de working set não comprovam leitura física do SSD.
- Se o runtime estiver ausente, a tela informa a falha; não simula respostas.
- O MVP ainda não tem streaming de tokens, cancelamento no meio da geração,
  persistência de conversas nem instalador autônomo.

## Arquivos e teste

- tools/run_chat.py: inicialização Windows.
- src/brain_ssd/chat/server.py: API e adaptação do Core / SSD.
- chat/: HTML, CSS e JavaScript offline.
- tests/test_chat_windows.py: testes sem GPU ou modelo.

Execute: python -m unittest discover -s tests -p "test_chat_windows.py" -v

## Próximo marco

Validar no Windows real uma conversa com "Olá", aferir tempo, RAM e qualidade,
e comparar o modo persistente com o modo de processo por consulta.
