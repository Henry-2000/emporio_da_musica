"""Loop de conversa e chamada de ferramentas (agentic loop) do agente.

Implementado como um loop manual sobre `client.models.generate_content` (com
a chamada automática de função do SDK desligada via
`automatic_function_calling.disable=True`) para deixar explícito, com fins
didáticos e de robustez, exatamente quando o agente decide chamar uma
ferramenta e como o histórico é montado — ver README > "Framework /
abordagem do agente". A estrutura do loop é a mesma independente do provedor
de LLM (só a "forma" das mensagens/ferramentas muda) — ver histórico do git
para a versão original sobre a API da Anthropic, antes da troca de provedor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from google import genai
from google.genai import types

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
    function_call/function_response no meio — a API espera a resposta de uma
    chamada de função logo após o turno do modelo que a pediu.
    """

    def __init__(
        self,
        client: genai.Client | None = None,
        model: str = config.MODEL_NAME,
        system: str = prompts.SYSTEM_PROMPT,
        max_history_turns: int = config.MAX_HISTORY_TURNS,
    ) -> None:
        self.client = client or genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = model
        self.system = system
        self.max_history_turns = max_history_turns
        self._turns: list[list[types.Content]] = []

    def _history_contents(self) -> list[types.Content]:
        recent_turns = self._turns[-self.max_history_turns :] if self.max_history_turns else self._turns
        return [content for turn in recent_turns for content in turn]

    def _run_tool(self, function_call: types.FunctionCall) -> types.Part:
        try:
            result = tools.execute_tool(function_call.name, function_call.args or {})
            response_payload: dict[str, Any] = {"result": result}
        except Exception as exc:  # nunca deixar uma ferramenta com erro travar o loop
            response_payload = {"error": f"Erro ao executar a ferramenta '{function_call.name}': {exc}"}
        return types.Part.from_function_response(name=function_call.name, response=response_payload)

    def send(self, user_text: str) -> str:
        """Envia uma mensagem do usuário e devolve a resposta final em texto."""
        turn: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=user_text)])]
        response = None

        generate_config = types.GenerateContentConfig(
            system_instruction=self.system + _current_date_note(),
            tools=[tools.GEMINI_TOOL],
            max_output_tokens=config.MAX_TOKENS,
            # Ferramentas são despachadas na mão (tools.execute_tool), não por
            # funções Python passadas direto ao SDK — desliga a chamada
            # automática de função para não competir com esse loop manual.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        for _ in range(config.MAX_TOOL_ITERATIONS):
            response = self.client.models.generate_content(
                model=self.model,
                contents=self._history_contents() + turn,
                config=generate_config,
            )
            model_content = response.candidates[0].content
            turn.append(model_content)

            function_calls = response.function_calls
            if not function_calls:
                break

            result_parts = [self._run_tool(fc) for fc in function_calls]
            turn.append(types.Content(role="user", parts=result_parts))
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
        return (response.text or "").strip()

    def reset(self) -> None:
        """Limpa o histórico da sessão (equivalente a começar uma nova conversa)."""
        self._turns.clear()
