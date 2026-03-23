from pinance.llm.base import LlmProvider


def create_provider(
    provider: str,
    model: str,
    base_url: str,
    api_key: str,
) -> LlmProvider:
    """
    設定値からLLMプロバイダーインスタンスを生成するファクトリ関数。

    Parameters
    ----------
    provider : str
        "ollama" | "claude" | "openai"
    model : str
        モデル名（例: "llama3.2", "claude-sonnet-4-6", "gpt-4o"）
    base_url : str
        APIのベースURL
    api_key : str
        APIキー（Ollamaの場合は空文字可）
    """
    if provider == "ollama":
        from pinance.llm.ollama import OllamaProvider
        return OllamaProvider(model=model, base_url=base_url)

    raise ValueError(f"未対応のLLMプロバイダー: {provider!r}")
