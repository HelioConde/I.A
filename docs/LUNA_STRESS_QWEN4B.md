# Luna — teste pesado controlado do Qwen3-4B Q8_0

## Objetivo e escopo

Este experimento valida **a confiabilidade da inferência textual real** do Qwen3-4B Q8_0 no Windows, com turnos consecutivos, histórico limitado, medição de tempo e interrupção por limite de recursos. Não modifica nem treina o modelo, nem é um benchmark de carregamento de pesos Brain-SSD.

O modelo grande **não** é substituído por uma versão mais leve. O GGUF Q8_0 existente é verificado por cabeçalho, tamanho e SHA-256 antes do teste real.

## Um comando para testar no PowerShell

```powershell
Set-Location "C:\Users\helio\Documents\I.A"
git pull --ff-only origin feat/ssd-weight-streaming-lab
.\TESTAR-LUNA-4B-PESADO.bat
```

**Feche qualquer sessão da Luna antes** para liberar RAM. A bateria pode levar dezenas de minutos ou mais de uma hora, dependendo da CPU e do modo escolhido.

O atalho executa: testes Python do estresse, testes de seleção do modelo, **1.000 turnos simulados**, testes de estados do modo ligação por Node.js se instalado, preflight do GGUF/RAM e **24 turnos reais** do Qwen3-4B via runtime do chat, um por vez.

Para executar separadamente:

```powershell
py -3 tools\stress_luna_qwen4b.py --simulate --turns 1000 --tokens 48
py -3 tools\stress_luna_qwen4b.py --check
py -3 tools\stress_luna_qwen4b.py --real --turns 24 --tokens 96 --core-mode auto --max-minutes 90 --per-turn-seconds 360
node --test tests\test_luna_call_state.cjs
```

Para uma bateria menor de inferência real, use `--real --turns 5 --tokens 48`.

Para voltar a abrir a Luna com o novo modelo **sem download**:

```powershell
.\USAR-QWEN4B-LUNA.bat
```

Se ainda não houver GGUF 4B, instale uma única vez com `.\INSTALAR-QWEN4B-LUNA.bat` (baixará ~4,28 GB explicitamente).

## Regras de segurança

- O modo `--simulate` **não executa Qwen** e escreve `status: simulated`, sem métricas falsas.
- O modo `--real` exige Windows, Qwen3-4B Q8_0 oficial já presente e **6 GiB de RAM física livre** antes da partida.
- Se cair abaixo de **1,5 GiB de RAM livre**, o supervisor tenta encerrar a árvore de processos do ensaio. O limite não é garantia absoluta contra OOM.
- Timeout padrão: até **360 segundos por turno** e **90 minutos** na execução. O trabalhador é um processo separado, sem mexer no chat em uso.
- Sem navegador, microfone, STT, TTS, pesquisa web, ferramentas do Copiloto, alteração do `LUNA.ini` ou download de pesos.
- As respostas vêm de prompts sintéticos predefinidos, com até seis mensagens de histórico. O sistema exige evidência de inferência real, não de uma resposta por regra local.
- O relatório e o log JSONL dos turnos ficam apenas em `results/model_comparison/` (ignorado pelo Git). Nomes com carimbo de data preservam execuções anteriores.

## Relatórios e interpretação

O JSON final contém `status`, número de turnos, tempo total, tempo por pergunta, status de completude, tamanho/hash e trecho das respostas, SHA-256 verificado do modelo, RAM livre inicial e mínima amostrada durante o teste.

**Memória atribuída:** se o Python do teste tiver `psutil`, é informado o maior RSS observado da árvore de processos (supervisor, worker e descendentes). Se não tiver, `peak_process_tree_rss_sampled_bytes` permanece **null**, não zero. Instalação opcional: `py -3 -m pip install psutil`. Não instala nada automaticamente.

A RAM livre mínima é do **Windows inteiro**; não pode ser atribuída apenas ao Qwen. O sistema operacional pode manter pesos em page cache. O teste não mede leitura física do SSD, VRAM, qualidade humana, TTFT de voz, latência de STT/TTS nem chamadas full-duplex.

**Voz:** os testes Node usam microfone, reconhecimento e TTS **simulados** para validar turnos/estados e cancelamentos. Uma ligação real exige teste físico do Chrome/Edge e pacote offline pt-BR instalado, com microfone autorizado pelo usuário.

Condição de sucesso da bateria real: todos os 24 turnos respondem, nenhuma resposta vazia/roteada por ferramenta, nenhum watchdog/limite de RAM é acionado e o trabalhador sai normalmente. Isso testa estabilidade funcional, não prova que as respostas sejam corretas ou que o Qwen ocupe menos RAM.

## Diagnóstico

Se o GGUF não estiver instalado ou falhar o SHA-256, use `py -3 tools\usar_qwen4b_luna.py --status` e consulte `docs/LUNA_QWEN_MODEL_AB.md`. Se o teste demorar, veja os eventos em `results/model_comparison/*stress*.events.jsonl` e pressione `Ctrl+C` para encerrar no terminal.

Se um teste falhar, envie a saída do PowerShell e o resumo JSON (revise eventuais trechos de respostas antes de compartilhar). Não publique artefatos locais de memória/conversa no GitHub.
