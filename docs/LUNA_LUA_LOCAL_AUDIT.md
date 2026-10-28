# Lua local — auditoria de formatos, sem treinar ou enviar

Baseado no inventário privado executado pelo usuário em 28/10/2026:

- 7.435 arquivos; 168 subdiretórios; 7.784.955.407 bytes.
- **5.902 arquivos terminados em `.lua`** — extensão não comprova ser texto Lua válido.
- 15 outros arquivos com extensões `.cpp`/`.h`; total agrupado como código possível = 5.917 arquivos (873.464.476 bytes).
- 14 backups de bancos de dados (**não abrir, carregar ou publicar**).
- Arquivos do cliente comercial, executáveis, KOM, áudio, imagens e compactados permanecem excluídos.
- O primeiro inventário **não leu conteúdo**, não transmitiu dados nem treinou a GameCoder.

## Nova opção 6 — análise local de cabeçalhos Lua

`experiments/luna-forge-zero/analyze_local_lua.py` abre, no máximo, 4.096 bytes de cada arquivo `.lua` regular, apenas para classificação de formato. Rejeita links simbólicos e junctions, não lê outras extensões, não executa ou extrai arquivos e salva exclusivamente contagens/somas em JSON. Não salva caminhos, nomes individuais, bytes, texto-fonte, hashes de arquivos nem dados pessoais.

Categorias possíveis:
- `utf8_text_candidate` — texto UTF-8 que **pode** conter código;
- `utf16_text_candidate` — texto Unicode possível;
- `compiled_lua_or_kl` — assinatura de bytecode, sem desmontagem/descompilação;
- `binary_or_obfuscated`, `binary_or_undetermined_utf16`;
- `non_utf8_or_binary_unknown`, `undetermined_encoding`;
- `empty`, `whitespace_only`.

Essas categorias indicam **formato**, não validade sintática, licença nem adequação ao aprendizado. `utf8_text_candidate` pode ser documentação, código inválido ou conteúdo protegido.

## No Windows, depois de atualizar a branch

```powershell
$repo = "$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C "$repo" pull --ff-only
$lab = Join-Path $repo "experiments\luna-forge-zero"
& "$lab\.venv\Scripts\python.exe" "$lab\analyze_local_lua.py" "$env:USERPROFILE\Documents\grand chase files"
```

**Se a instalação estiver em `Luna-Forge-Local-2`, ajuste `$repo`.** Para usar o menu interativo, execute `ABRIR-LUNA-FORGE.cmd` e selecione opção **6**.

O relatório ficará em `reports/lua_format_audit.json` na pasta experimental e será ignorado pelo Git. Se já existir, use outro nome com `--out`; não há sobrescrita silenciosa. **Compartilhe somente as contagens da saída**, não textos-fonte de jogos, backups nem dados privados.

## Próxima etapa (ainda não implementada)

Confirmar o formato e a proveniência dos scripts. Só material sobre o qual haja autorização de uso e treinamento pode entrar no conjunto de aprendizado. Priorizar novos exemplos originais e testes de movimento, combate e animações escritos pela Luna, avaliando funções e comportamento em Godot/JS. O treinador `train_github.py` NÃO lê estes arquivos nem o relatório; apenas projetos externos licenciados e currículo original.


## Resultado da auditoria de 28/10/2026

Relatorio fornecido pelo usuario, baseado em 5.902 arquivos `.lua` (873.402.247 bytes):

| Classificacao de formato | Arquivos |
|---|---:|
| Candidatos a texto UTF-8 | 5.789 |
| Codificacao nao UTF-8 ou formato binario desconhecido | 94 |
| Bytecode Lua ou KL | 18 |
| Somente espacos em branco | 1 |

Conclusao: cerca de **98,1%** dos arquivos `.lua` parecem ser texto UTF-8 nos primeiros 4096 bytes. Isso nao significa codigo sintaticamente valido, licencia aberta, origem propria ou direito de treinar a IA. Nenhum script foi exportado ou usado para treino.

## Nova opcao 7 — perfil estrutural, ainda sem treinamento

`profile_local_lua.py` amostra ate 64 KiB de cada arquivo Lua e conta apenas ocorrencias agregadas de palavras-chave (`function`, `if`, `for`, `while`, `return`) e classes estruturais. Comentarios e strings comuns sao ignorados na contagem. A analise nao e parser; pode errar em Lua complexo, especialmente em comentarios longos e arquivos amostrados parcialmente.

```powershell
$repo = "$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
$lab = Join-Path $repo "experiments\luna-forge-zero"
$saida = Join-Path $lab "reports\lua_structure_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
& "$lab\.venv\Scripts\python.exe" "$lab\profile_local_lua.py" "$env:USERPROFILE\Documents\grand chase files" --out "$saida"
```

O resultado inclui SOMENTE contagens e agregados, nenhum nome ou texto de arquivo. A pasta `reports` nao e versionada. Este script **nao** copia codigo, nao roda `luac`/scripts, nao extrai KOM/RAR, nao executa nada nem muda pesos. O professor Core devera usar futuras tarefas **originais** e codigo com permissao confirmada.
