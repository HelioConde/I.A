# Brain-SSD — diagnóstico do bloqueio GitHub Actions

## Evidência obtida em 12 de outubro de 2026

Na branch feat/copilot-local-windows, os workflows Brain-SSD Chat Smoke e Brain-SSD Windows Chat Build passaram a encerrar com conclusão failure, sem etapas retornadas pela API e sem logs de job recuperáveis. Isso ocorreu inclusive em commits que alteraram somente a documentação.

Exemplos de execuções:
- https://github.com/HelioConde/I.A/actions/runs/38199575370
- https://github.com/HelioConde/I.A/actions/runs/38199575222

Um job encerrado sem etapas e com logs indisponíveis **não comprova falha nos testes Python**. Pode ser problema de agendamento, execução, política do repositório, orçamento de Actions ou outra causa. Nenhuma dessas hipóteses foi confirmada.

## Como investigar com acesso à conta

1. Abra uma execução no GitHub Actions e procure banner de erro, anotação ou aviso de política na página do run e na aba Summary.
2. Confira Settings > Actions > General do repositório e permissões para executar os workflows.
3. Confira as configurações de Billing/Usage de GitHub Actions do proprietário do repositório (minutos, gasto e limites), caso aplicável.
4. Verifique se os runners GitHub-hosted estão permitidos para esse repositório.
5. Veja se uma nova execução de workflow simples, sem compilação de Godot ou .NET, consegue iniciar etapas.
6. Somente depois de recuperar logs identifique e corrija eventuais testes que falharem.

Foi adicionada configuração de concorrência aos dois workflows: execuções antigas de push/PR da mesma branch são canceladas quando entram novas execuções, para evitar trabalho redundante. Isso **não comprova** correção de um eventual problema de quota/política.

## Validação local enquanto o CI não estiver disponível

Abra CMD em C:\Users\helio\Documents\I.A, na branch feat/copilot-local-windows:

    py -3 -m compileall -q src\brain_ssd\chat tools\run_chat.py
    py -3 -m unittest discover -s tests -p "test_agent_core.py" -v
    py -3 -m unittest discover -s tests -p "test_godot_diagnostics.py" -v
    py -3 -m unittest discover -s tests -p "test_godot_validation.py" -v
    py -3 -m unittest discover -s tests -p "test_copilot_code_edits.py" -v
    node --check chat\app.js

O Agent Core usa somente leitura. O teste de validador Godot usa mocks; nenhum executável real é iniciado pelos testes novos.

**Critério de liberação:** CI Linux/Windows verde **e** teste real no desktop Windows com permissões limitadas e observação do fluxo. O PR não deve ser tratado como homologado antes disso.
