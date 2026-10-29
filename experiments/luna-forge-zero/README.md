# Luna Forge Zero (pesquisa experimental)

Dois modelos **inicializados do zero**, sem importar pesos pretreinados, para o projeto Luna.

- **Game Planner V0**: interpreta prompts de jogos (2 estilos, 6 mecânicas), modelo neural pequeno e próprio. O gerador Canvas utiliza **templates escritos por humanos**, e não código criado pelo modelo.
- **MiniCoder V0**: Transformer causal experimental treinado em miniexemplos sintéticos de JavaScript e GDScript. Sua saída pode ser inválida; não executar sem verificação.
- **Teacher Lab**: gerador procedimental de desafios de teste, não é ainda um modelo professor independente.

O pacote completo de código executável, pesos e relatórios foi entregue ao usuário como arquivo local nesta conversa. Esta branch inicia a trilha de pesquisa dentro do repositório I.A e não altera a IA principal. Nenhuma habilidade de gerar um jogo inteiro é reivindicada.

## Dados de avaliação

O Planner foi treinado em 9.000 prompts sintéticos; 600 de validação e 600 de teste. O desempenho em teste sintético foi aproximadamente 99,7% em correspondência exata, mas a avaliação manual ajustada foi 9/12: isso **não** comprova generalização real. O MiniCoder é avaliado separadamente por perda de previsão de caractere e testes de sintaxe.

## Metas

1. Tornar treináveis e reprodutíveis os pesos de ambos os modelos.
2. Aprender tarefas de código Godot 4 e Web Canvas licenciadas.
3. Executar JavaScript em Chromium e GDScript em Godot headless.
4. Adicionar professor com currículo, verificador, revisão humana, métricas e rollback.
5. Promover uma versão só depois de testes cegos melhores que a baseline.

**Segurança:** não inserir modelos experimentais no chat Brain-SSD sem avaliação e permissão do usuário.

## Auditoria local dos índices KOM

As ferramentas `audit_kom_headers.py` e `audit_kom_index.py` inspecionam somente
cabeçalhos e índices, sem extrair, descriptografar ou executar conteúdo. A versão
0.2 usa o layout legado confirmado, incluindo offsets relativos ao início da
área de dados após o índice; esse parser foi mantido separado. A versão 0.3 usa
um cabeçalho próprio de 72 bytes (`<52sIIIII`) e um manifesto XML limitado a
16 MiB, iniciado no offset 72. O parser confere a assinatura completa, o
marcador, o tamanho do manifesto e do arquivo, Adler-32, soma de `FileTime`,
contagem de entradas, atributos e intervalos comprimidos cumulativos. O XML é
decodificado como UTF-8 em memória; DTDs e declarações de entidades são
rejeitados. Entradas perigosas ou duplicadas e intervalos fora do arquivo não
são validados. O conteúdo comprimido nunca é lido.

`audit_kom_headers.py` é apenas um classificador de cabeçalhos: para V0.3 a
confiança permanece provisória até a auditoria do manifesto com
`audit_kom_index.py`. Versões desconhecidas e formatos não suportados são
reportados sem interpretar os índices. Relatórios incluem contagens agregadas
por versão e extensão (inclusive `.lua`), bytes comprimidos declarados,
manifestos inválidos/excessivos e entradas fora dos limites; nomes internos,
caminhos privados e conteúdos não são exportados.

A varredura recursiva ignora diretórios HShield, backups, nomes contendo
`private`/`privado`/`privada`, `.git` e `.venv`; symlinks e reparse points não
são seguidos. Escolha como raiz somente a pasta exata autorizada dos 247
pacotes, não uma pasta pai que contenha outros dados. O comando abaixo é um
exemplo para execução local explícita; substitua o caminho pela raiz real:

```powershell
$KomRoot = "C:\CAMINHO\AUTORIZADO\DOS-247-PACOTES"
$Report = ".\kom-v02-v03-$((Get-Date).ToString('yyyyMMdd-HHmmss')).json"
python .\audit_kom_index.py $KomRoot --json-out $Report
```

O comando não foi executado contra os pacotes reais nesta implementação. Os
testes usam exclusivamente arquivos sintéticos:
`python -m unittest -v test_audit_kom_index.py`.

As referências externas foram consultadas somente para confirmar a estrutura do
formato; nenhum código delas foi copiado:
[Elsword-file-editor](https://github.com/asuralove/Elsword-file-editor/blob/master/elswordkom/kom.cpp)
e
[uKOM-Extractor](https://github.com/d3v1l401/uKOM-Extractor/blob/master/uKOM%20Extractor/HManager.cpp).

### Baseline de inventário fornecida pelo usuário

`KOM_AUDIT_BASELINE_2026-10-29.json` registra o resultado local informado em
29/10/2026, sem reler os pacotes nesta sessão: 101 V0.2 (17.418 entradas),
144 V0.3 (88.657 entradas), um manifesto V0.3 com checksum divergente (170
entradas declaradas, todas rejeitadas) e um pacote desconhecido. Os 3.993 nomes
com extensão `.lua` são contagens de metadados validados, não extrações. Os
5.880 arquivos Lua visíveis na árvore Elsword são inventário separado e não
foram admitidos no corpus. O checksum de manifesto V0.3 é validado antes que
qualquer entrada desse manifesto seja aceita; falha invalida o manifesto inteiro.

## MiniCoder: estado e geração determinística

O Transformer próprio atual usa caracteres ASCII (vocabulário 128), duas
camadas, dimensão 64 e janela 128. O prompt é condicionado por bytes/caracteres,
sem tokenizer de subpalavras; caracteres fora do vocabulário são mapeados a
`?`. O treino sintético `train_codegen.py` tem oito templates e compartilha
famílias de tarefas entre treino/validação. `github_corpus.py` oferece um
coletor separado para fontes fixadas com evidência MIT, 3 projetos de treino e
1 projeto holdout; a coleta externa não é executada automaticamente. A
verificação agora revalida o checksum do texto normalizado e dos avisos de
licença.

`sample_codegen.py --deterministic` seleciona tokens greedy e reproduz a mesma
saída para pesos e prompt iguais; sem a flag, o modo amostrado legado permanece.
O avaliador `evaluate_github_codegen.py` também usa geração greedy para
reprodutibilidade, e a ponte `brain_ssd_bridge.py` aceita `--deterministic`.
Determinismo e parsing não demonstram comportamento funcional. As métricas
informadas para MiniCoder V2 (loss de treino 72,9614 → 0,96618; três tarefas
inéditas sem funções reconhecíveis) são resultado fornecido, não reproduzido
aqui e registradas em `GAMECODER_BASELINE_2026-10-29.json`. Nenhum checkpoint
V0/V2 está presente nesta cópia do workspace. Portanto não foi treinado/promovido
modelo, criado protótipo alegadamente gerado pela Luna, nem afirmada capacidade
de gerar jogos.