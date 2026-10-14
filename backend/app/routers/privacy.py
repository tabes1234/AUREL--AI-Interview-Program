"""T7 隐私与数据留存说明（机器可读，供界面与审计使用）。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


@router.get("")
def privacy_policy() -> dict:
    return {
        "audio": {
            "storage": "memory_only",
            "note": "上传/录音的音频只在内存中用于转录与指标计算，绝不写入磁盘或数据库",
        },
        "secrets": {
            "storage": "server_env_only",
            "note": "API Key 与令牌只存在于服务端 .env / 环境变量，绝不入库、不进日志、不进前端代码",
        },
        "database_stored": [
            "面试任务、问题、回答与评分报告",
            "知识文档与分块（用于检索）",
            "简历匹配记录",
            "表达分析：转录文本、客观指标、多角色复盘结果",
            "模型调用观测记录（服务名、模型、耗时、状态，不含提示词与密钥）",
        ],
        "deletion_endpoints": [
            "DELETE /api/v1/expression/records/{id}",
            "DELETE /api/v1/knowledge/documents/{id}",
        ],
        "observability_note": "llm_call_records 只记录元数据（服务、模型、耗时、状态），不记录提示词正文与密钥",
    }
