from config import GEMINI_API_KEY, GEMINI_MODEL
from taskRefinings.LlmTaskRefiner import LlmTaskRefiner


class GeminiTaskRefiner(LlmTaskRefiner):
    """Analyse via l'API Google Gemini (clé : https://aistudio.google.com/app/apikey)"""
    NAME = "Gemini"

    def _call_llm(self, prompt: str) -> str:
        return self.ask(prompt, GEMINI_API_KEY, GEMINI_MODEL)

    @staticmethod
    def ask(prompt: str, api_key: str, model: str = "gemini-flash-latest") -> str:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)  # package google.generativeai déprécié
            import google.generativeai as genai

        if not api_key:
            raise ValueError("Clé API Gemini manquante")
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model or "gemini-flash-latest").generate_content(prompt).text.strip()
