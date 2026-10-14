"""T4：固定评测集结构校验与评测指标计算。"""

import json
from pathlib import Path

from eval.run_eval import EVALSET_PATH, aggregate, evaluate_question_case, evaluate_scoring_case
from tests.conftest import VALID_SCORING, FakeArkClient


def test_evalset_structure():
    evalset = json.loads(EVALSET_PATH.read_text(encoding="utf-8"))
    assert evalset["name"].startswith("aurel-evalset")
    scoring_ids = [case["id"] for case in evalset["scoring_cases"]]
    question_ids = [case["id"] for case in evalset["question_cases"]]
    assert len(scoring_ids) == len(set(scoring_ids))
    assert len(question_ids) == len(set(question_ids))
    for case in evalset["scoring_cases"]:
        assert case["answer"].strip()
        assert case["question"].strip()
        assert 0 <= case["reference"]["overall_score"] <= 10
        assert case["difficulty"] in ("basic", "intermediate", "advanced")
    for case in evalset["question_cases"]:
        assert 1 <= case["question_count"] <= 10


def test_evaluate_scoring_case_success():
    case = {
        "id": "scoring-test",
        "position": "前端工程师",
        "difficulty": "intermediate",
        "language": "zh",
        "question": "问题",
        "answer": "回答",
        "reference": {"overall_score": 6.8, "must_cover": ["React", "Webpack"]},
    }
    fake = FakeArkClient([VALID_SCORING])
    result = evaluate_scoring_case(fake, case)
    assert result["ok"] is True
    # VALID_SCORING 四维平均 6.75，后端按一位小数取整为 6.8
    assert result["overall_score"] == 6.8
    assert result["score_deviation"] == 0.0
    assert result["evidence_complete"] is True
    assert result["dimensions_covered"] is True
    assert result["keywords_covered"] == ["React"]  # VALID_SCORING 证据里有 React
    assert result["keywords_missing"] == ["Webpack"]  # 未提及 Webpack


def test_evaluate_scoring_case_model_failure():
    from app.services.ark_client import ArkError

    class FailingClient(FakeArkClient):
        def chat_json(self, system, user, *, temperature=0.3, service="unattributed"):
            raise ArkError("模型不可用")

    case = {
        "id": "scoring-fail",
        "position": "后端",
        "difficulty": "basic",
        "language": "zh",
        "question": "问题",
        "answer": "回答",
        "reference": {"overall_score": 5.0, "must_cover": []},
    }
    result = evaluate_scoring_case(FailingClient(), case)
    assert result["ok"] is False
    assert "模型不可用" in result["error"]


def test_evaluate_question_case_success():
    case = {
        "id": "questions-test",
        "position": "前端工程师",
        "description": "React 开发",
        "difficulty": "intermediate",
        "language": "zh",
        "question_count": 2,
    }
    fake = FakeArkClient([{"questions": ["问题一：谈谈 React 组件设计", "问题二：如何做性能优化"]}])
    result = evaluate_question_case(fake, case)
    assert result["ok"] is True
    assert result["count_ok"] is True
    assert result["actual_count"] == 2
    assert result["length_ok"] is True


def test_aggregate_metrics():
    results = [
        {"ok": True, "score_deviation": 1.0, "evidence_complete": True,
         "keywords_covered": ["a"], "keywords_missing": ["b"], "latency_ms": 100},
        {"ok": False, "error": "失败", "latency_ms": 50},
        {"ok": True, "score_deviation": 3.0, "evidence_complete": False,
         "keywords_covered": [], "keywords_missing": [], "latency_ms": 300},
    ]
    metrics = aggregate(results)
    assert metrics["cases"] == 3
    assert metrics["parse_success"] == 2
    assert metrics["parse_success_rate"] == round(2 / 3, 4)
    assert metrics["avg_score_deviation"] == 2.0
    assert metrics["evidence_coverage"] == 0.5
    assert metrics["keyword_coverage"] == 0.5
    assert metrics["avg_latency_ms"] == 200.0
    assert metrics["p95_latency_ms"] == 300.0
