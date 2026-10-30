# Auditoria preliminar dos repositorios de jogos enviados para a Luna

Data: 2026-10-30. Resultado reproduzivel em \`LUNA_GAMECODER_SOURCE_REVIEW.json\`.

**Escopo:** triagem de fontes para o futuro curriculo de programacao de jogos.
Este commit nao coleta codigo de terceiros, nao treina modelos e nao altera
\`github_corpus.py\` nem os conjuntos de avaliacao existentes.

## Fontes mais relevantes com licenca explicitamente verificada

| Repositorio | Licenca observada | Linguagem | Uso proposto |
|---|---|---|---|
| [RafaelForbeck/Godot-2025-Plataforma-2D-YouTube](https://github.com/RafaelForbeck/Godot-2025-Plataforma-2D-YouTube) | MIT, arquivo LICENSE inspecionado | GDScript | Candidato **treino**: estados, plataformas, inimigos |
| [douglasadones/Escudeiro](https://github.com/douglasadones/Escudeiro) | MIT, LICENSE inspecionado | GDScript | Candidato **holdout cego**, proibido para treino/feedback se reservado |
| [arthurBrito1/jogo-pulapula-Javascript](https://github.com/arthurBrito1/jogo-pulapula-Javascript) | MIT | HTML/JS | Consulta; importer atual nao suporta HTML |
| [moises-dias/hunter-adventures](https://github.com/moises-dias/hunter-adventures) | MIT | C++ | Consulta de arquitetura; importer nao suporta C++ |
| [felipeph/pgzero-platformer](https://github.com/felipeph/pgzero-platformer) | Apache-2.0 | Python | Consulta; importer atual limita-se a MIT e JS/GDScript |

Commits e hashes de evidencia de licenca registrados em JSON. Os caminhos
de codigo sugeridos sao pontuais, sem midia, executaveis, pacotes ou arquivos
externos. A licenca geral do repositorio nao garante que toda textura, musica
ou recurso de terceiros esteja coberto por ela.

## Repositorios nao aprovados nesta triagem

Repositorios sem licenca identificada nos metadados GitHub foram colocados em
\`quarantined_no_detected_license\`. Publicidade do repositorio **nao** significa
licenca de reuso. Se o dono apresentar uma licenca explicita, revisar antes
de mudar o status. Projetos de portabilidade, catalogos, emulacao, iGaming,
boloes, sites e redes sociais nao foram considerados fonte principal de
gameplay nesta etapa.

Os dois repositorios GPL-3.0 identificados exigem fluxo de licenciamento
separado; nao foram incorporados ao coletor que atualmente aceita apenas MIT.

## Proxima integracao

1. Revisar e validar caminhos fixados em commit SHA e preservar copyright/LICENSE.
2. Adicionar somente arquivos com extensoes permitidas ao coletor, **depois**
   de decidir a separacao treino/holdout.
3. Manter o holdout reservado fora do corpus de prompts e de autocorrecao.
4. Executar testes offline de integridade do coletor no GitHub Actions.
5. Coletar codigo apenas com opt-in; treinar um novo candidato experimental e
   avaliar em tarefas originais e inéditas, sem pontuar templates como IA.

As fontes foram avaliadas quanto a presenca de licenca e estrutura preliminar,
nao auditadas integralmente quanto a codigo de terceiros embutido.
