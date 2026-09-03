#!/usr/bin/env python
"""Interface de linha de comando (chat) para o agente da Empório da Música.

Uso:
    python cli.py

Comandos especiais dentro do chat:
    /sair, /exit    encerra a conversa
    /novo           reinicia o histórico (nova conversa, mesma sessão)
    /salvar         salva a conversa atual em conversations/<timestamp>.md

A conversa também é salva automaticamente em conversations/ ao sair
normalmente (Ctrl+C ou /sair), para servir de log/transcript da sessão.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agent import config  # noqa: E402
from agent.core import ConversationAgent  # noqa: E402

BANNER = """\
============================================================
  Empório da Música — Atendimento (protótipo)
  "Sua música começa aqui."
============================================================
Oi! Manda sua pergunta (produtos, preços, pedidos, políticas
da loja...). Digite /sair para encerrar.
"""

CONVERSATIONS_DIR = Path(__file__).resolve().parent / "conversations"


def _check_api_key() -> None:
    if not config.ANTHROPIC_API_KEY:
        print(
            "AVISO: variável de ambiente ANTHROPIC_API_KEY não encontrada.\n"
            "Configure-a (por exemplo em um arquivo .env na raiz do projeto — "
            "veja .env.example) antes de rodar o agente.",
            file=sys.stderr,
        )
        sys.exit(1)


def _save_transcript(history: list[tuple[str, str]]) -> Path | None:
    if not history:
        return None
    CONVERSATIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = CONVERSATIONS_DIR / f"{timestamp}.md"
    lines = [f"# Conversa — {timestamp}", ""]
    for role, text in history:
        speaker = "Cliente" if role == "user" else "Empório da Música"
        lines.append(f"**{speaker}:** {text}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    _check_api_key()
    agent = ConversationAgent()
    history: list[tuple[str, str]] = []

    print(BANNER)
    try:
        while True:
            try:
                user_text = input("Você: ").strip()
            except EOFError:
                break

            if not user_text:
                continue
            if user_text.lower() in {"/sair", "/exit", "/quit"}:
                break
            if user_text.lower() == "/novo":
                agent.reset()
                history.clear()
                print("(histórico reiniciado)\n")
                continue
            if user_text.lower() == "/salvar":
                path = _save_transcript(history)
                print(f"(conversa salva em {path})\n" if path else "(nada para salvar ainda)\n")
                continue

            history.append(("user", user_text))
            try:
                reply = agent.send(user_text)
            except Exception as exc:  # erro de rede/API — não derruba a sessão
                reply = f"Desculpa, tive um problema técnico para responder agora ({exc})."
            history.append(("assistant", reply))
            print(f"\nEmpório da Música: {reply}\n")
    except KeyboardInterrupt:
        print()
    finally:
        path = _save_transcript(history)
        if path:
            print(f"\nConversa salva em {path}")
        print("Até a próxima! 🎵")


if __name__ == "__main__":
    main()
