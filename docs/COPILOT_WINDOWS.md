# Copiloto Windows — primeira etapa (experimental)

O Brain-SSD continua usando o modelo de texto local e a memória no SSD.
Esta etapa adiciona ferramentas de **leitura**, nunca de edição ou controle
remoto do PC. O servidor permanece restrito a 127.0.0.1.

## Como iniciar

1. Atualize o repositório e prepare o modelo GGUF e o llama.cpp pelo
   `INICIAR-BRAIN-SSD.bat`, se ainda faltarem componentes.
2. No Windows, instale dependências opcionais (na mesma instalação Python
   utilizada pelo launcher): `py -3 -m pip install mss Pillow`.
3. Abra `INICIAR-COPILOTO-WINDOWS.bat` e autorize uma pasta e/ou a captura da
   tela. Sem autorização, o recurso fica desativado.
4. No chat, clique no ícone **▣** da barra superior. Digite o caminho completo
   de um arquivo dentro da pasta autorizada, clique em **Ler texto**, **Listar
   pasta** ou **Ver imagem**, ou use **Capturar agora**.
5. **Atualizar a cada 3 s** mostra novas imagens do monitor selecionado
   enquanto o painel estiver aberto. Desmarcar ou fechar interrompe as
   capturas. Monitor `1` é o primeiro; `0` reúne todos os monitores.

Comando equivalente para testar apenas um projeto:

```powershell
py -3 .\tools\run_chat.py --profile economia --web-search --web-provider auto --copilot-root "C:\Caminho\MeuProjeto" --copilot-screen
```

É possível repetir `--copilot-root` para autorizar mais pastas.

## Pesquisa Google + Wikipedia

O modo `auto` preserva Wikipédia e feeds de notícias sem chave. Para
buscar resultados gerais indexados pelo Google, o Brain-SSD usa **Serper**,
um provedor externo que consulta resultados do Google. **Não é uma API
oficial do Google** e requer conta e chave própria do Serper.

No mesmo PowerShell em que vai iniciar o programa:

```powershell
$env:SERPER_API_KEY = "SUA_CHAVE"
py -3 .\tools\run_chat.py --web-search --web-provider auto
```

Para exigir pesquisa geral e não usar Wikipédia como fallback, troque
`auto` por `google`. Na interface, ainda é necessário marcar **Pesquisar
na web** para cada pergunta. Apenas a pergunta autorizada e a chave
necessária são enviadas ao provedor; nenhuma captura, arquivo ou memória
é enviada automaticamente. O modo de notícias do Brasil com `auto`
continua usando as fontes RSS existentes.

Evite projetos novos baseados na API JSON legada do Google Custom Search:
ela não aceita novas inscrições desde 2026. Consulte a [orientação
oficial](https://developers.google.com/custom-search/v1/overview).

## Limitações atuais

- **Captura não é visão computacional:** o Qwen3-0.6B existente é um
  modelo de texto. Ele não interpreta pixels nesta etapa. A interface
  pode mostrar screenshots e imagens, mas não afirmar o que elas contêm.
- **Tempo real é amostragem:** o painel atualiza a cada 3 segundos, não
  transmite vídeo contínuo. Capturas ficam na memória e não são gravadas.
- **Pastas limitadas:** só caminhos sob raízes explicitamente autorizadas;
  symlinks fora delas, diretórios de credenciais, arquivos binários e
  textos acima de 128 KB são bloqueados.
- **Sem execução:** não move o mouse, não edita arquivos nem abre programas.
- Ao clicar **Usar texto no chat**, até 1.500 caracteres são inseridos
  manualmente no campo de mensagem. Se forem enviados, o conteúdo passa
  a fazer parte do histórico local da conversa. Revise antes de enviar.
- Nem sempre uma captura de aplicativos protegidos ou de jogos aparecerá
  corretamente; depende das permissões do Windows e do mecanismo gráfico.

## Próxima etapa — percepção real

Integrar um modelo multimodal local compatível com o hardware e o
runtime, separado do Qwen de texto. Validar perguntas sobre imagens,
OCR local, comparação de duas capturas, seleção de janela e indicação
clara de quando a interpretação falhar. Somente depois considerar
ações reversíveis e autorizadas (edição de código, abrir programas etc.).

## Testes locais

```powershell
py -3 -m unittest discover -s tests -p "test_copilot.py" -v
```

Este teste não requer GGUF nem pesquisa real: verifica confinamento
de arquivos, permissões, origem HTTP e normalização das fontes Google.
Valide também o painel manualmente no Windows com monitor 1 e 2.
