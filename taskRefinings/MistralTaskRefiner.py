import json

import requests

from config import MISTRAL_API_KEY, MISTRAL_AGENT_ID, MISTRAL_AGENT_VERSION
from taskRefinings.LlmTaskRefiner import LlmTaskRefiner

MISTRAL_CONVERSATIONS_URL = "https://api.mistral.ai/v1/conversations"


class MistralTaskRefiner(LlmTaskRefiner):
    """Analyse via un agent Mistral (API Conversations)"""
    NAME = "Mistral"

    def _call_llm(self, prompt: str) -> str:
        return self.ask(prompt, MISTRAL_API_KEY, MISTRAL_AGENT_ID, MISTRAL_AGENT_VERSION)

    @staticmethod
    def ask(prompt: str, api_key: str, agent_id: str, agent_version: int = None) -> str:
        if not api_key:
            raise ValueError("Clé API Mistral manquante")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "agent_id": agent_id,
            "inputs": [
                {"role": "user", "content": prompt}
            ]
        }
        if agent_version:
            payload["agent_version"] = int(agent_version)

        response = requests.post(MISTRAL_CONVERSATIONS_URL, headers=headers, json=payload, timeout=300)
        if not response.ok:
            raise RuntimeError(f"Mistral {response.status_code} : {response.text[:300]}")
        data = response.json()

        outputs = data.get("outputs", [])
        for output in outputs:
            if output.get("type") == "message.output":
                content = output.get("content")
                if isinstance(content, list):
                    return "".join(
                        chunk.get("text", "") for chunk in content if isinstance(chunk, dict)
                    ).strip()
                if isinstance(content, str):
                    return content.strip()

        raise ValueError(f"Réponse Mistral inattendue : {json.dumps(data, ensure_ascii=False)[:500]}")
