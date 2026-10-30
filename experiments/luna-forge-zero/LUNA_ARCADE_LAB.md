# Luna Arcade: laboratorio jogavel + construtor Ollama local

## O que existe

- luna-arcade-sandbox/: jogo de plataformas Canvas original e jogavel, com controles
  de teclado e toque, tres estrelas, slime patrulhando, plataformas e portal.
- gameplay.js, engine.js, HTML e CSS: **referencia escrita manualmente**.
- luna_arcade_builder.py: pede a um modelo pretreinado instalado no Ollama
  apenas uma nova funcao updateGame(state,input,dt), verifica sintaxe com
  Node.js, e salva a tentativa numa pasta isolada.
- test_reference_gameplay.cjs: valida **somente a referencia manual**.
- test_luna_arcade_builder.py: testa o construtor com respostas simuladas
  de Ollama, SEM executar codigo gerado.

NENHUMA pontuacao da demo de referencia significa habilidade comprovada da
MiniCoder V3. A nova geracao via Ollama usa pesos pretreinados de terceiros,
nao os pesos treinados do zero da Luna.

## Primeiro: jogar o prototipo de referencia

PowerShell, no Windows, apos atualizar a branch feature/luna-forge-zero:

    $lab = "$env:USERPROFILE\Documents\Luna-Forge-Lab\experiments\luna-forge-zero"
    python -m http.server 8765 --bind 127.0.0.1 --directory "$lab\luna-arcade-sandbox"

Abra http://127.0.0.1:8765/ no navegador. Use A/D ou setas para andar,
espaco para pular e o botao Reiniciar quando necessario. Para parar, Ctrl+C.

A demo nao exige banco de dados, download de assets ou servidores externos.

## Segundo: pedir uma mecanica ao Ollama local

Ollama deve estar rodando em 127.0.0.1:11434, com um modelo instalado.
Exemplo de instalacao do modelo: ollama pull qwen2.5-coder:3b

    $py = "$lab\.venv\Scripts\python.exe"
    & $py "$lab\luna_arcade_builder.py" status
    & $py "$lab\luna_arcade_builder.py" build --model "qwen2.5-coder:3b" --task "Movimento suave, pulo, estrelas, patrulha de slime."

O gerador faz ate duas tentativas, exige uma funcao JavaScript completa com
assinatura updateGame(state,input,dt), executa somente Node --check, e cria
um diretório exclusivo em reports/luna_arcade_runs/run-*. Ele nao substitui
a referencia, nao altera modelos e nao executa o JavaScript gerado.

Leia gameplay.js e manifest.json na pasta retornada pelo gerador. Depois de
revisar conscientemente o codigo, inicie um servidor local apontando para
o diretorio do candidato (substitua pelo caminho completo mostrado em folder):

    $pasta = "CAMINHO_COMPLETO_DA_PASTA_RUN"
    python -m http.server 8765 --bind 127.0.0.1 --directory "$pasta"

Abra http://127.0.0.1:8765/. O prototipo gerado roda somente apos voce
solicitar a visualizacao, num iframe com sandbox allow-scripts, sem
allow-same-origin, e com Content-Security-Policy proibindo conexoes.
Isso e defesa em profundidade, NAO uma garantia de seguranca perfeita.
Nao abra arquivos gerados em uma aba comum, nao retire o isolamento e
nao publique o candidato antes de revisao. Se houver erro de navegador,
nao conclua que houve sucesso funcional.

## Terceiro: testes de referencia e do construtor

No diretorio de experimento:

    Push-Location $lab
    try {
        & $py -B -m unittest -v test_luna_arcade_builder.py
        node --check ".\luna-arcade-sandbox\gameplay.js"
        node --check ".\luna-arcade-sandbox\engine.js"
        node ".\luna-arcade-sandbox\test_reference_gameplay.cjs"
    } finally {
        Pop-Location
    }

Um PASS nos testes de referencia apenas valida a infraestrutura.
Para pontuar uma saida do Ollama como gameplay funcional, sera necessario
um runner de comportamento isolado, com evidencias da origem do codigo.

## Limites e privacidade

- Sem leitura de arquivos de jogos comerciais, KOM, arquivos do usuario ou backups.
- Sem conexao com APIs de nuvem no construtor; Ollama local apenas.
- Sem autoexecucao de codigo gerado; sem auto-commit, auto-deploy ou treino.
- Os candidatos ficam em reports/, ignorado no Git.
- O filtro de codigo do construtor pode falhar e jamais deve ser tratado como
  uma barreira de seguranca completa; a revisao manual permanece obrigatoria.
