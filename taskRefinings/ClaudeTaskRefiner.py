import json
import shutil
import subprocess

from config import CLAUDE_CLI_PATH, CLAUDE_MODEL
from taskRefinings.LlmTaskRefiner import LlmTaskRefiner

CLAUDE_TIMEOUT_SECONDS = 600


class ClaudeTaskRefiner(LlmTaskRefiner):
    """Analyse via le CLI Claude Code (`claude -p`), sans clé API : utilise la connexion du CLI"""
    NAME = "Claude"

    def _call_llm(self, prompt: str) -> str:
        return self.ask(prompt, CLAUDE_CLI_PATH, CLAUDE_MODEL)

    @staticmethod
    def ask(prompt: str, cli_path: str = "claude", model: str = None, timeout: int = CLAUDE_TIMEOUT_SECONDS) -> str:
        """Appelle Claude Code en ligne de commande (mode non interactif) et retourne le texte genere"""
        if shutil.which(cli_path) is None:
            raise FileNotFoundError(f"CLI Claude introuvable : {cli_path}")

        cmd = [
            cli_path,
            "-p",                          # mode print (non interactif)
            "--output-format", "json",
            "--tools", "",                 # aucun outil : generation de texte uniquement
            "--no-session-persistence",
        ]
        if model:
            cmd += ["--model", model]

        # Le prompt passe par stdin (evite les limites de taille des arguments)
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"Claude CLI a echoue ({proc.returncode}) : {proc.stderr.strip()[:500] or proc.stdout.strip()[:500]}")

        data = json.loads(proc.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"Erreur Claude : {data.get('result')}")
        return (data.get("result") or "").strip()
