from __future__ import annotations

from brain_ssd.observability.events import BrainEvent


class EventNarrator:
    """Deterministic human-language translation. No LLM is used."""

    _MESSAGES = {
        "QUERY_RECEIVED": "Recebi a pergunta e vou decidir quais partes do cérebro precisam trabalhar.",
        "REFLEX_STARTED": "Estou verificando se existe um caminho rápido para esta tarefa.",
        "REFLEX_SKIPPED": "O caminho rápido não se aplica; vou consultar o cérebro maior.",
        "REFLEX_COMPLETED": "O caminho rápido concluiu a tarefa.",
        "ROUTER_STARTED": "Estou descobrindo quais áreas do conhecimento podem responder à pergunta.",
        "ROUTER_CANDIDATES": "Encontrei áreas candidatas e estou avaliando sua relevância.",
        "ROUTER_COMPLETED": "As áreas mais promissoras foram identificadas.",
        "SEMANTIC_RESCUE_STARTED": "A busca direta não foi suficiente; estou tentando uma comparação semântica barata.",
        "SEMANTIC_RESCUE_COMPLETED": "A busca semântica terminou.",
        "GATE_STARTED": "Estou decidindo quais áreas realmente podem acordar.",
        "PAGE_ACTIVATED": "Uma região de conhecimento foi ativada porque pode contribuir para a resposta.",
        "PAGE_INHIBITED": "Uma região candidata foi bloqueada porque a evidência atual indica baixa utilidade.",
        "GATE_COMPLETED": "O conjunto de conhecimento ativo foi limitado ao necessário.",
        "STORAGE_READ_STARTED": "Estou acessando as páginas de conhecimento selecionadas.",
        "STORAGE_READ_COMPLETED": "O acesso ao conhecimento terminou.",
        "KNOWLEDGE_RECORD_SELECTED": "Um trecho de conhecimento relevante foi selecionado.",
        "CONTEXT_BUILD_STARTED": "Estou organizando o conhecimento antes de entregá-lo ao Core.",
        "CONTEXT_BUILD_COMPLETED": "O contexto do Core está pronto.",
        "CORE_STARTED": "O Core foi iniciado em modo CPU-only.",
        "CORE_PROMPT_PROCESSING": "O modelo está lendo a pergunta e o conhecimento selecionado.",
        "CORE_GENERATING": "O modelo está gerando a resposta.",
        "CORE_COMPLETED": "O Core terminou o processamento.",
        "ANSWER_READY": "A resposta está pronta.",
        "PRESSURE_CHANGED": "O estado de pressão de memória mudou.",
        "WARNING": "A execução continua, mas existe um aviso que merece atenção.",
        "ERROR": "A execução encontrou um erro.",
    }

    _COMPONENTS = {
        "REFLEX": "Tenta resolver tarefas triviais sem acordar o pipeline completo.",
        "ROUTER": "Escolhe quais áreas de conhecimento podem ser úteis.",
        "SEMANTIC_RESCUE": "Procura relações semânticas quando a busca direta não basta.",
        "GATE": "Decide quais áreas realmente podem acordar e quais ficam bloqueadas.",
        "BRAIN": "Representa páginas de conhecimento ativas, candidatas ou inibidas.",
        "STORAGE": "Lê as páginas selecionadas usando o armazenamento do Brain-SSD.",
        "CONTEXT": "Seleciona e organiza os trechos entregues ao Core.",
        "CORE": "Modelo pequeno que interpreta o contexto e produz a resposta.",
        "RESOURCES": "Observa CPU, RAM, I/O e pressão sem alterar o raciocínio.",
    }

    def narrate(self, event: BrainEvent) -> str:
        message = self._MESSAGES.get(event.event_type)
        if message:
            return message
        return f"O componente {event.component.title()} registrou o evento {event.event_type}."

    def describe_component(self, component: str) -> str:
        return self._COMPONENTS.get(component.upper(), "Componente observado pelo Brain-SSD Visual HUD.")
