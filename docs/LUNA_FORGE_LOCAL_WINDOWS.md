# Luna Forge Zero + Brain-SSD — Windows 11, instalação local

Esta é uma **instalação separada**, não substitui o chat existente da Luna nem as fases experimentais congeladas do Brain-SSD.

## Requisitos

- Windows 11 x64, Python 3.10–3.14 (3.12 preferível), Git e internet apenas para instalar dependências/obter projetos públicos MIT.
- CPU x64, cerca de 16 GB de RAM; execução e treino em CPU. O SSD abriga pesos, páginas de conhecimento e feedback; não substitui RAM.
- Instalação em `%USERPROFILE%\Documents\Luna-Forge-Lab` ou outra pasta sem mexer na atual `%USERPROFILE%\Documents\I.A`.

## Clonar a branch experimental de modo independente

Abra PowerShell:

```powershell
git clone --depth 1 --single-branch --branch feature/luna-forge-zero https://github.com/HelioConde/I.A.git "$env:USERPROFILE\Documents\Luna-Forge-Lab"
cd "$env:USERPROFILE\Documents\Luna-Forge-Lab\experiments\luna-forge-zero"
.\INSTALAR-LUNA-FORGE.cmd
```


> **Pacote do instalador:** os arquivos .cmd, .ps1 e luna_local.py sao distribuídos no arquivo ZIP entregue na conversa do ChatGPT. Depois de clonar esta branch, extraia esse ZIP em `experiments/luna-forge-zero/`, antes de executar `INSTALAR-LUNA-FORGE.cmd`. Eles ainda nao estao incluidos neste checkout do GitHub.

O instalador cria `.venv`, instala PyTorch CPU e psutil nela, treina o Planner e o MiniCoder **desde pesos aleatórios** se os checkpoints não existirem, cria as páginas Brain-SSD de conhecimento e imprime status. Não requer direitos de administrador e não modifica as instalações globais de Python.

Depois, dê dois cliques em **ABRIR-LUNA-FORGE.cmd** na mesma pasta para abrir o menu local. Opção 4 solicita confirmação explícita para coletar código dos projetos MIT públicos e treinar um novo **candidato isolado**.

## Usar somente o instalador, sem treinar

```powershell
.\INSTALAR-LUNA-FORGE.cmd -SkipInitialTraining
```

## Executar um novo treinamento opcional com GitHub

```powershell
.\INSTALAR-LUNA-FORGE.cmd -TrainGithub
```

O modo `-TrainGithub` usa os projetos externos **somente de código com licença MIT** já aprovados, bem como os exercícios originais de combate. Os nove repositórios de Grand Chase fornecidos pelo usuário ficam catalogados como referência, mas seu código/arquivos não entram no treinamento automaticamente.

## Diretórios

- `.venv/`: ambiente Python isolado; pode ser removido/recriado sem afetar o Brain-SSD principal.
- `checkpoints/`: os dois primeiros modelos treinados localmente (não publicar os pesos sem revisão).
- `knowledge_pages/`: páginas com SHA-256 para o armazenamento experimental Brain-SSD.
- `external_data/`: exemplos de código de terceiros permitidos, avisos de licença e checkpoints candidatos.
- `state/`: futuro histórico local de feedback em SQLite.

**Privacidade:** os arquivos em `C:\Users\helio\Documents\grand chase files\` não são lidos, extraídos, enviados ou modificados por esse instalador. Não insira arquivos comerciais em um dataset de treinamento sem autorização de uso.

## Advertências

O modelo de geração de código ainda não passou nos testes de sintaxe avaliados anteriormente. A instalação não o torna capaz de criar jogos completos. Avalie cuidadosamente quaisquer outputs gerados e não execute código não verificado. O instalador usa `powershell -ExecutionPolicy Bypass` **somente no processo que executa o script**, sem alterar a política de execução global do Windows. O limite de 64 MiB dos checkpoints no adaptador é apenas um limite de arquivo, não uma garantia do consumo total de RAM.