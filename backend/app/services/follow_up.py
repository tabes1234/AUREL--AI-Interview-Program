"""追问判断：基于候选人回答决定是否追问一次。"""

from app.services.ark_client import ArkClient, ArkError


class FollowUpDecision:
    def __init__(self, need_follow_up: bool, follow_up: str | None, reason: str) -> None:
        self.need_follow_up = need_follow_up
        self.follow_up = follow_up
        self.reason = reason


def decide_follow_up(
    client: ArkClient,
    *,
    position: str,
    question: str,
    answer: str,
    language: str,
) -> FollowUpDecision:
    lang_name = "中文" if language == "zh" else "English"
    system = (
        "你是模拟面试中的面试官。候选人刚回答了一个问题，你需要判断是否值得追问。"
        "追问原则：回答明显过浅、含糊其辞、有未展开的关键点或与岗位强相关的可疑经历时，追问一次；"
        "回答已充分时不要为了追问而追问。"
    )
    user = (
        f"目标岗位：{position}\n"
        f"主问题：{question}\n"
        f"候选人回答：{answer}\n"
        f"追问语言：{lang_name}\n"
        '输出 JSON：{"need_follow_up": true/false, '
        '"follow_up": "追问内容（不需要时为 null）", "reason": "简短判断理由"}'
    )

    data = client.chat_json(system, user, service="follow_up")
    need = data.get("need_follow_up")
    reason = str(data.get("reason") or "").strip() or "未说明理由"
    if not isinstance(need, bool):
        raise ArkError("AI 模型返回的追问判断格式无效")

    if need:
        follow_up = data.get("follow_up")
        if not isinstance(follow_up, str) or not follow_up.strip():
            raise ArkError("AI 模型决定追问但未提供追问内容")
        return FollowUpDecision(True, follow_up.strip(), reason)
    return FollowUpDecision(False, None, reason)
