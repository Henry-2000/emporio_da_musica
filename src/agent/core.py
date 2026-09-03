"""Loop de conversa e chamada de ferramentas (agentic loop) do agente.

Implementado como um loop manual sobre `client.messages.create` (em vez do
`tool_runner` beta do SDK) para deixar explícito, com fins didáticos e de
robustez, exatamente quando o agente decide chamar uma ferramenta e como o
histórico é montado — ver README > "Framework / abordagem do agente".
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import anthropic

from . import config, prompts, tools

_WEEKDAYS_PT = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]


def _current_date_note() -> str:
    """Contexto de data/hora atual, anexado ao system prompt em cada envio.

    Necessário para o modelo raciocinar sobre prazos relativos a uma data
    (ex.: "esse pedido foi entregue há quantos dias? ainda dá para devolver
    dentro do prazo de 7 dias?") — sem isso ele não tem como saber "hoje".
    Recalculado a cada chamada (não fixado no import) para a sessão do CLI
    continuar correta se atravessar a meia-noite.
    """
    now = datetime.now()
    weekday = _WEEKDAYS_PT[now.weekday()]
    return f"\n\n# Data e hora atuais\nHoje é {weekday}, {now.strftime('%d/%m/%Y')}, {now.strftime('%H:%M')}."


class ConversationAgent:
    """Mantém o histórico de uma sessão de chat e conversa com o modelo.

    O histórico é guardado por "turno" (uma mensagem do usuário + tudo que o
    modelo fez para respondê-la, incluindo idas e vindas de ferramenta) para
    que o corte de histórico antigo (`max_history_turns`) nunca quebre um par
    tool_use/tool_result no meio — a API rejeita um `tool_result` sem o
    `tool_use` correspondente na mesma janela de mensagens.
    """

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str = config.MODEL_NAME,
        system: str = prompts.SYSTEM_PROMPT,
        max_history_turns: int = config.MAX_HISTORY_TURNS,
    ) -> None:
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.system = system
        self.max_history_turns = max_history_turns
        self._turns: list[list[dict[str, Any]]] = []

    def _history_messages(self) -> list[dict[str, Any]]:
        recent_turns = self._turns[-self.max_history_turns :] if self.max_history_turns else self._turns
        return [message for turn in recent_turns for message in turn]

    def _run_tool(self, block: Any) -> dict[str, Any]:
        try:
            result = tools.execute_tool(block.name, block.input)
            content = json.dumps(result, ensure_ascii=False, default=str)
            return {"type": "tool_result", "tool_use_id": block.id, "content": content}
        except Exception as exc:  # nunca deixar uma ferramenta com erro travar o loop
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Erro ao executar a ferramenta '{block.name}': {exc}",
                "is_error": True,
            }

    def send(self, user_text: str) -> str:
        """Envia uma mensagem do usuário e devolve a resposta final em texto."""
        turn: list[dict[str, Any]] = [{"role": "user", "content": user_text}]
        response = None

        system_with_date = self.system + _current_date_note()

        for _ in range(config.MAX_TOOL_ITERATIONS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=config.MAX_TOKENS,
                system=system_with_date,
                tools=tools.TOOL_DEFINITIONS,
                messages=self._history_messages() + turn,
            )
            turn.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            tool_results = [self._run_tool(block) for block in tool_use_blocks]
            turn.append({"role": "user", "content": tool_results})
        else:
            # Excedeu MAX_TOOL_ITERATIONS sem terminar — evita loop infinito
            # e ainda assim guarda o turno para não perder o contexto.
            self._turns.append(turn)
            return (
                "Desculpa, tive dificuldade para concluir essa consulta agora. "
                "Pode tentar reformular a pergunta, ou um atendente humano pode te ajudar?"
            )

        self._turns.append(turn)
        assert response is not None
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks).strip()

    def reset(self) -> None:
        """Limpa o histórico da sessão (equivalente a começar uma nova conversa)."""
        self._turns.clear()
