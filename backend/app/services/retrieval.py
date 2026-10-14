"""T2/T9 共用的检索内核：词项化 + BM25 式词频评分。

方舟 embedding 模型未开通（/embeddings 404），检索端采用本地 BM25 式
词频匹配——与 Elasticsearch 默认排序同族的成熟方案。所有分数与证据
均来自真实文本计算，可追溯、可解释。
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

# 中文字符（单个字 + 双字组合）与英文/数字单词
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """中文按单字 + 相邻双字 bigram，英文按小写单词。"""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        if raw.isdigit() or not any("\u4e00" <= ch <= "\u9fff" for ch in raw):
            tokens.append(raw.lower())
        else:
            tokens.append(raw)
    # 中文 bigram：仅在原文本中真正相邻的汉字之间
    han_positions = [m.start() for m in re.finditer(r"[\u4e00-\u9fff]", text)]
    for prev_pos, cur_pos in zip(han_positions, han_positions[1:]):
        if cur_pos - prev_pos == 1:
            tokens.append(text[prev_pos] + text[cur_pos])
    return tokens


@dataclass
class ScoredHit:
    key: int
    score: float


class BM25Index:
    """轻量 BM25（k1=1.5, b=0.75）。构建一次，多次查询。"""

    def __init__(self, docs: dict[int, str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._doc_tokens: dict[int, Counter[str]] = {}
        self._doc_len: dict[int, int] = {}
        self._df: Counter[str] = Counter()
        for key, text in docs.items():
            tokens = tokenize(text)
            counter = Counter(tokens)
            self._doc_tokens[key] = counter
            self._doc_len[key] = len(tokens)
            for term in counter:
                self._df[term] += 1
        self._avg_len = (
            sum(self._doc_len.values()) / len(self._doc_len) if self._doc_len else 0.0
        )
        self._n = len(docs)

    def search(self, query: str, top_k: int = 5) -> list[ScoredHit]:
        if self._n == 0 or self._avg_len == 0:
            return []
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return []
        scores: dict[int, float] = {}
        for key, counter in self._doc_tokens.items():
            score = 0.0
            dl = self._doc_len[key]
            for term, qtf in query_terms.items():
                tf = counter.get(term, 0)
                if tf == 0:
                    continue
                df = self._df.get(term, 0)
                idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1.0)
                tf_norm = (
                    tf * (self.k1 + 1)
                    / (tf + self.k1 * (1 - self.b + self.b * dl / self._avg_len))
                )
                score += idf * tf_norm * min(qtf, 3)
            if score > 0:
                scores[key] = score
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [ScoredHit(key=key, score=round(score, 4)) for key, score in ranked[:top_k]]
