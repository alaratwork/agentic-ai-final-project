# file:     harness/models.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  build a langchain chat model by short name, with fixed decoding settings
# updated:  2026-11-22

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

# decoding - held fixed across every condition and model (fp2 4.2)
DECODING = {"temperature": 0.5, "top_p": 1.0}

# models - short name -> backend settings; openrouter models arrive in phase 11
# phi4-mini runs as phi4-mini-tools: same weights, corrected tool template
# (see configs/ollama/phi4-mini-tools.Modelfile for why and how to build it)
MODELS = {
    "phi4-mini": {"backend": "ollama", "model": "phi4-mini-tools:latest", "num_ctx": 8192,
                  "build": "ollama create phi4-mini-tools -f configs/ollama/phi4-mini-tools.Modelfile"},
}


def model_info(name: str) -> dict:
    # describe - what the log records about a model; for ollama also the
    # exact digest and quantization of the local build
    spec = MODELS[name]
    info = {"model": name, "provider": spec["backend"], "backend_model": spec["model"],
            "settings": {**DECODING, "num_ctx": spec.get("num_ctx")}}
    if spec["backend"] == "ollama":
        import ollama  # import - only for local models
        local = {m.model: m for m in ollama.list().models}
        if spec["model"] in local:
            entry = local[spec["model"]]
            info["settings"] |= {"digest": entry.digest,
                                 "quantization": entry.details.quantization_level}
    return info


def get_chat_model(name: str, seed: int = 0) -> BaseChatModel:
    # look up - fail loudly on a name we have not configured
    if name not in MODELS:
        raise ValueError(f"unknown model '{name}'; known: {sorted(MODELS)}")
    spec = MODELS[name]
    if spec["backend"] == "ollama":
        # build - seed makes a rerun of the same episode repeatable;
        # num_ctx is set so ollama's default context size cannot drift
        try:
            return ChatOllama(model=spec["model"], seed=seed, num_ctx=spec["num_ctx"],
                              validate_model_on_init=True, **DECODING)
        except Exception as exc:
            # explain - a missing local model is a setup step, not a bug
            raise RuntimeError(f"ollama model '{spec['model']}' is not available ({exc}). "
                               f"is ollama running? build it with: {spec['build']}") from exc
    raise ValueError(f"unsupported backend '{spec['backend']}' for '{name}'")
