"""Choix du refiner IA selon TASK_REFINER (.env) : claude, gemini ou mistral."""
from config import TASK_REFINER

REFINERS = ("claude", "gemini", "mistral")


def get_refiner_class(name: str = TASK_REFINER):
    # imports à la demande : seules les dépendances du refiner choisi sont chargées
    if name == "gemini":
        from taskRefinings.GeminiTaskRefiner import GeminiTaskRefiner
        return GeminiTaskRefiner
    if name == "mistral":
        from taskRefinings.MistralTaskRefiner import MistralTaskRefiner
        return MistralTaskRefiner
    from taskRefinings.ClaudeTaskRefiner import ClaudeTaskRefiner
    return ClaudeTaskRefiner
