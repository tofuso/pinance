from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ClassificationTarget:
    """分類対象のトランザクション情報"""
    transaction_id: int
    transaction_type: str  # "bank" | "card"
    description: str       # 銀行: description / カード: merchant
    amount: int


@dataclass
class ClassificationSuggestion:
    """LLMによる分類提案"""
    transaction_id: int
    transaction_type: str
    description: str
    suggested_category_name: str | None
    suggested_keyword: str | None
    confidence: float


class LlmProvider(ABC):
    """LLMプロバイダーの抽象基底クラス"""

    @abstractmethod
    def classify(
        self,
        targets: list[ClassificationTarget],
        category_names: list[str],
    ) -> list[ClassificationSuggestion]:
        """
        トランザクションのリストを受け取り、カテゴリ分類の提案を返す。

        Parameters
        ----------
        targets:
            分類対象のトランザクションリスト
        category_names:
            利用可能なカテゴリ名のリスト
        Returns
        -------
        ClassificationSuggestion のリスト（targetsと同じ順・同じ長さ）
        """
        ...
