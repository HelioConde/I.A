# Brain-SSD Windows: instalação automática e troca de modelos

Use o arquivo **INICIAR-BRAIN-SSD.bat** como iniciador principal no Windows 10/11 x64.

## Início rápido

1. Atualize o projeto executando **git pull --ff-only**.
2. Abra **INICIAR-BRAIN-SSD.bat** com dois cliques.
3. Escolha **1** (Qwen3 0.6B), **2** (Qwen3 1.7B) ou **3** (Qwen3 4B).
4. Escolha se quer habilitar a opção de pesquisa na Wikipédia; cada pergunta continua exigindo autorização na interface.
5. O instalador verifica e baixa somente os arquivos ausentes, valida o SHA-256, executa o diagnóstico e inicia o chat.

| Seleção | Modelo | Download aproximado | RAM sugerida |
| --- | --- | --- | --- |
| 1 | Qwen3-0.6B-Q8_0.gguf | 639 MB | 4 GB |
| 2 | Qwen3-1.7B-Q4_K_M.gguf | 1,28 GB | 8 GB |
| 3 | Qwen3-4B-Q4_K_M.gguf | 2,5 GB | 8 GB ou mais |

A quantidade de RAM é apenas orientação; o espaço real ocupado depende da CPU, Windows e contexto. Os modelos maiores podem responder mais lentamente. Nenhum modelo garante respostas corretas em todos os casos.

## Como o instalador funciona

- Verifica Python 3.11+; se faltar e winget estiver disponível, oferece instalar Python 3.11 mediante confirmação.
- Reutiliza o instalador seguro de llama.cpp CPU-only, com versão e SHA-256 já fixados.
- Instala modelos GGUF na pasta **models**; arquivos existentes com o hash correto são reutilizados.
- Baixa apenas modelos de uma lista de fontes confiáveis com SHA-256 conhecido: Qwen3 0.6B oficial, Qwen3 1.7B ggml-org em revisão fixa e Qwen3 4B oficial Qwen.
- Escreve o download em arquivo temporário e publica o modelo somente depois de verificar o hash.
- Se um arquivo instalado tiver hash divergente, interrompe e preserva o arquivo para verificação manual.
- Executa o diagnóstico com o GGUF selecionado antes de iniciar a inferência.
- Não remove nem altera histórico SQLite, memórias episódicas ou os dados SSD.

Escolher uma opção no menu autoriza o download caso os componentes daquele modelo ainda não estejam instalados. Os downloads podem usar vários gigabytes de disco e internet.

## Comandos opcionais

Instalar e validar apenas o Qwen3 1.7B sem iniciar o navegador:

    py -3 .\tools\auto_setup_chat_windows.py --model 1.7b --prepare-only

Preparar e iniciar o Qwen3 4B com opção de pesquisa web:

    py -3 .\tools\auto_setup_chat_windows.py --model 4b --profile equilibrado --web

Testar o instalador sem baixar nenhum arquivo:

    py -3 -m unittest discover -s tests -p "test_auto_setup_chat_windows.py" -v
    py -3 -m unittest discover -s tests -p "test_windows_launchers.py" -v

## Limitações

Os testes automáticos usam arquivos e runtime simulados. O download, o probe e a geração de texto com um modelo real ainda devem ser testados no computador Windows. Os componentes nativos podem depender do Visual C++ Runtime e de permissões do antivírus. O instalador não altera os benchmarks congelados do Brain-SSD.
