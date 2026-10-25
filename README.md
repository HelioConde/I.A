<div align="center">
  <h1>🧠 Brain-SSD — Laboratório de IA Local</h1>
  <p><strong>Pesquisa aplicada sobre memória persistente, recuperação de contexto e execução de modelos locais em computadores pessoais.</strong></p>
  <p><img alt="Python" src="https://img.shields.io/badge/Python-Experimentos-3776AB?logo=python&logoColor=white"> <img alt="Windows" src="https://img.shields.io/badge/Windows-Launcher-2563eb"> <img alt="Status" src="https://img.shields.io/badge/status-pesquisa%20experimental-64748b"></p>
</div>

## A pergunta de pesquisa

**É possível manter um grande conjunto de conhecimentos em armazenamento persistente e recuperar apenas o contexto necessário para cada pergunta?**

O Brain-SSD explora componentes de memória, seleção de contexto e integração com modelos locais. A proposta é estudar **eficiência de memória, qualidade da recuperação e custo de execução**, não afirmar que um SSD substitui integralmente RAM ou que a arquitetura reproduz o cérebro humano.

> **Status científico:** hipótese experimental. Não há comprovação geral de superioridade em qualidade, velocidade ou consumo de memória sobre um modelo local convencional. Resultados dependem do hardware, modelo, dados e metodologia.

## O que existe no repositório

| Área | Conteúdo |
| --- | --- |
| `chat/` | Componentes da experiência de conversa local |
| `brain_data/` | Estruturas e dados de laboratório |
| `src/` | Núcleo dos experimentos |
| `launcher/` / `hud/` | Inicialização e interface Windows |
| `benchmarks/` / `results/` | Avaliações e resultados experimentais |
| `tests/` | Testes automatizados |
| `docs/` | Arquitetura, hipóteses e pesquisas |

Há scripts de preparação, diagnóstico e execução para **Windows** na raiz. Eles são meios de experimentar a aplicação, e podem exigir runtime de IA, modelo local e dependências adicionais.

## Começar no Windows

1. Clone o repositório e leia o [guia de configuração](docs/AUTO_SETUP_WINDOWS.md).
2. Use o script `PREPARAR-CHAT-WINDOWS.bat` para iniciar a preparação do ambiente conforme sua configuração.
3. Para experimentar o chat, há entradas como `INICIAR-CHAT-WINDOWS.bat` e `INICIAR-CHAT-MEMORIA-WINDOWS.bat`.
4. Se algo falhar, use o [guia de diagnóstico](docs/LOGS_DIAGNOSTICOS.md) e os scripts de logs/diagnóstico incluídos na raiz.

**Não há garantia de que qualquer máquina consiga executar o modelo escolhido**: memória, CPU, disco, permissões e runtime precisam ser compatíveis. Antes de executar arquivos `.bat`, revise seu conteúdo e mantenha backups de dados de teste.

## Arquitetura em alto nível

```text
Pergunta do usuário
        ↓
Preparação e seleção de contexto
        ↓
Recuperação de conhecimento/memórias relevantes
        ↓
Inferência por modelo local configurado
        ↓
Resposta e métricas de avaliação
```

Memória explícita, cache cognitivo, busca web e organização de fatos aparecem como **módulos e pesquisas** em diferentes estágios. Nem todos devem ser interpretados como funcionalidades prontas ou ativadas por padrão.

## Como avaliar com rigor

- Compare o resultado com uma **linha de base** sem o mecanismo experimental.
- Meça **RAM, latência, uso de disco e qualidade da resposta** sob as mesmas condições.
- Use conjuntos de testes reproduzíveis e registre parâmetros do modelo.
- Distinga recuperação de contexto de **treinamento de pesos**; o projeto não deve sugerir que consultas modificam automaticamente o modelo.
- Documente falhas e exemplos negativos, não apenas demonstrações bem-sucedidas.

## Documentação

[Arquitetura](docs/ARCHITECTURE.md) · [Hipóteses](docs/HYPOTHESIS_REGISTRY.md) · [Benchmarks](docs/BENCHMARKS.md) · [Roadmap](docs/ROADMAP.md) · [Guia de Windows](docs/CHAT_WINDOWS.md) · [Histórico técnico anterior](docs/README_HISTORY_2026-10-25.md)

**Criado por [Hélio Conde](https://github.com/HelioConde).** Projeto de pesquisa independente, sem alegações de equivalência biológica ou validação clínica.
