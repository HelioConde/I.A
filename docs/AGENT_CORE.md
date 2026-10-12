# Agent Core do Brain-SSD — investigação em etapas

## Funcionamento

O Agent Core combina ferramentas locais de leitura sob um plano revisável. O usuário escolhe uma tarefa, recebe uma lista dos passos, confirma a investigação e recebe evidências obtidas pelas ferramentas. A IA não inventa resultados de comandos.

O plano tem duração máxima de 90 segundos, token de uso único e somente um pedido pendente por sessão. A investigação não executa programas, não digita, não altera arquivos, não usa shell e não executa código do projeto.

## Tipos disponíveis

| Tarefa | Ferramenta real | Resultado |
| --- | --- | --- |
| godot_diagnosis | Inspeção de projeto e referências em erros Godot | Arquivos, linhas e trechos encontrados |
| godot_overview | Scanner limitado de projetos Godot | Contagem de scripts, cenas, recursos e TODO/FIXME |
| code_review | Leitura e análise estática de arquivo | Linhas, tamanho, avisos e TODO |
| pc_report | Consulta de hardware/sistema | Dados reais e recomendações limitadas |

## Exemplos no chat

    /investigar-projeto "C:\Users\helio\Documents\Slime-Harvest"
    /investigar-godot "C:\Users\helio\Documents\Slime-Harvest" :: SCRIPT ERROR: res://scripts/player.gd:42
    /investigar-codigo "C:\Users\helio\Documents\Slime-Harvest\scripts\player.gd"
    /investigar-pc

Cada comando cria apenas um plano. Clique em **Investigar agora (somente leitura)** para usar as ferramentas locais.

O painel **▣ Copiloto > Agent Core — investigação em etapas** oferece a mesma função com seleção de tarefa e botões de preparação e investigação.

## Evidências e limitações

A API devolve status, etapas, fonte dos dados, fatos observados, recomendações, ações realizadas e próximos passos. Resultados incompletos recebem status partial. A correspondência de um caminho citado em um erro não comprova a causa do bug; inspecionar código não testa o jogo.

As permissões de pastas são independentes das de captura, instalação de aplicativos ou execução de Godot. As informações do erro ficam em memória durante a vigência do plano, sem serem incluídas integralmente na prévia. Usar o texto gerado na conversa pode adicioná-lo ao histórico; evite compartilhar segredos.

## Validação

Na pasta do projeto, execute:

    py -3 -m unittest discover -s tests -p "test_agent_core.py" -v
    py -3 -m unittest discover -s tests -p "test_godot_diagnostics.py" -v
    py -3 -m unittest discover -s tests -p "test_godot_validation.py" -v

A CI Linux/Windows segue com falhas em jobs que encerram sem etapas e sem logs acessíveis; é necessário confirmar a causa no GitHub e validar a interface na máquina Windows real.

## Próximo estágio

Permitir que o agente, após reunir evidências, produza um patch revisável e execute testes autorizados. Uma correção só deverá ser declarada após comparação antes/depois. Controle de aplicativos, conversação contínua e visão semântica permanecem projetos futuros.

## Continuação — do diagnóstico à edição reversível

Quando a investigação identifica um arquivo existente, o painel exibe
**Selecionar arquivo encontrado no editor**. Isso apenas transfere o caminho
verificado para o editor. O usuário ainda precisa informar exatamente qual
trecho substituir e confirmar o diff.

Após uma edição aprovada, o Copiloto oferece:
- **Verificar última alteração**: comparar SHA-256 do arquivo em disco com
  o conteúdo realmente aplicado. Não constitui teste do software.
- **Preparar desfazer**: conferir backup, confirmar que o arquivo não mudou e
  mostrar um diff reverso, sem alterar arquivos.
- **Confirmar desfazer**: restaurar o backup por substituição atômica, após
  uma segunda confirmação na interface.

A reversão cobre somente a edição mais recente **na sessão atual**,
durante 30 minutos, e cada proposta de desfazer expira em 90 segundos.
Se outro programa modificar o arquivo, o Copiloto bloqueia o desfazer para
não sobrescrever trabalho novo. O backup permanece no diretório privado
local mesmo após a janela de desfazer; a ferramenta não oferece restauro
automático após reiniciar o servidor.

Essa evolução não gera código autonomamente. Não há comparação funcional
do jogo antes/depois nem execução de Godot integrada ao mesmo plano.
