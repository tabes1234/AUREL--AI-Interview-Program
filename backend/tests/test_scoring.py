"""T1 评分引擎的单元测试。"""

from app.services import scoring
from app.services.ark_client import ArkError
from tests.conftest import VALID_SCORING, FakeArkClient

QA_PAIRS = [
    {
        "question": "介绍你的项目经验",
        "answer": "我做过订单管理系统",
        "follow_up": None,
        "follow_up_answer": None,
    }
]


def test_score_interview_computes_overall_from_dimensions() -> None:
    client = FakeArkClient([VALID_SCORING])
    result = scoring.score_interview(
        client, position="前端工程师", difficulty="intermediate", language="zh", qa_pairs=QA_PAIRS
    )

    assert result.overall_score == 6.8  # (6+8+7+6)/4
    assert [d.name for d in result.dimensions] == ["内容深度", "表达清晰", "逻辑结构", "岗位匹配"]
    assert result.strengths == ["表达有条理", "态度认真"]


def test_score_interview_rejects_invalid_structure() -> None:
    client = FakeArkClient([{"summary": "ok"}])
    try:
        scoring.score_interview(
            client, position="前端", difficulty="basic", language="zh", qa_pairs=QA_PAIRS
        )
        raise AssertionError("应当抛出 ArkError")
    except ArkError:
        pass


def test_build_qa_lines_includes_follow_up() -> None:
    lines = scoring.build_qa_lines(
        [
            {
                "question": "Q1",
                "answer": "A1",
                "follow_up": "F1",
                "follow_up_answer": "FA1",
            }
        ]
    )
    assert "追问：F1" in lines
    assert "追问回答：FA1" in lines
