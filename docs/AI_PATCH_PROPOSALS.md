# Brain-SSD — propostas de código com IA local

## Novo fluxo de programação assistida

A IA pode gerar **uma proposta de substituição** de código baseada em trecho real de arquivo. O modelo não pode abrir arquivos adicionais, executar comandos ou alterar o projeto nesse processo.

1. Inicie INICIAR-COPILOTO-WINDOWS.bat e autorize uma pasta de projeto e a permissão de edição de código.
2. No painel Copiloto, selecione um arquivo .gd, .py, .json ou outro formato permitido pelo editor.
3. Abra **IA local: gerar proposta de correção**. Escreva o problema em até 380 caracteres e indique uma linha de foco, se souber.
4. Clique **Gerar proposta com IA local**. O Brain-SSD envia ao Qwen local até 900 caracteres de código do arquivo autorizado, sem ativar pesquisa web ou anexar histórico de chat.
5. O modelo deve devolver um JSON estrito contendo trechos before, after e reason. O backend rejeita candidatos inválidos, trechos que não correspondam exatamente ao arquivo e propostas ambíguas.
6. Para Python, a proposta deve passar por ast.parse; para JSON, pelo parser JSON. Para GDScript, CSS e demais formatos o editor **não afirma ter validado a sintaxe**.
7. Se a proposta passar nesses filtros, o editor mostra o diff. Nenhuma alteração ocorre até clicar **Confirmar edição no disco** e aprovar a confirmação.
8. Depois da aplicação, utilize **Verificar última alteração**, **Preparar desfazer** e **Confirmar desfazer**, conforme necessário. O desfazer depende do conteúdo do disco não ter sido alterado após a edição.

No Agent Core, ao diagnosticar um erro Godot e localizar um arquivo, o botão **Selecionar arquivo encontrado no editor** preenche o caminho, a linha de foco (se existir) e ajuda a abrir a seção de proposta. Esse botão não executa IA, testes ou mudanças: é uma transferência de contexto.

## Segurança e limitações

- Somente o modelo local é usado nessa ação; o request para geração define pesquisa web e memória de pesquisa como desabilitadas. A ferramenta não envia arquivos para provedores externos.
- A IA pequena pode falhar ao devolver JSON ou sugerir uma modificação inválida. Nesse caso, o sistema deve recusar a proposta e permitir que o usuário use a substituição manual.
- A mudança é **um trecho de um arquivo**, não um patch multi-arquivo nem refatoração geral.
- Um diff sintaticamente válido não garante que o comportamento do jogo foi corrigido.
- O Brain-SSD deve ser iniciado com pastas limitadas. Evite abrir arquivos com credenciais; o conteúdo selecionado será processado localmente pelo modelo e possivelmente por diagnósticos locais.
- Uma resposta produzida pelo modelo jamais é interpretada como autorização para executar shell, abrir programas ou alterar arquivos.
- Os tokens de aplicação têm prazo e uso único; a aplicação exige SHA-256 correspondente ao arquivo do momento da prévia.
- Mesmo com todas as proteções, esta versão é experimental e ainda precisa ser validada no PC Windows real.

## Testes específicos (nenhuma IA real é executada)

    py -3 -m unittest discover -s tests -p "test_model_patch_draft.py" -v
    py -3 -m unittest discover -s tests -p "test_copilot_code_edits.py" -v
    py -3 -m unittest discover -s tests -p "test_agent_core.py" -v

Os testes do gerador usam saída fictícia de modelo para simular erros e respostas corretas, além de conferir o controle da API HTTP. Não comprovam a qualidade das correções sugeridas pelo Qwen instalado.

## Próximo passo

Avaliar sugestões reais do Qwen local com exemplos de erros do Godot, medir acerto de JSON e qualidade dos diffs. Em seguida, integrar testes separados e autorizados antes/depois e um rollback governado por resultado, preservando confirmação humana.
