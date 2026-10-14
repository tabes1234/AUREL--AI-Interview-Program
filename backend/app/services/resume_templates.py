"""履历成章：简历模板目录（后端唯一事实源，导出与前端预览共用同一 section_order）。"""

RESUME_TEMPLATES: list[dict] = [
    {
        "id": "clean",
        "name": "清爽通用型",
        "description": "居中标题、均衡分节，适合大多数岗位的海投首选。",
        "section_order": ["summary", "work", "projects", "education", "skills", "certificates", "awards"],
        "accent": "#4D83D6",
        "header_align": "center",
    },
    {
        "id": "campus",
        "name": "校园与应届生型",
        "description": "教育经历前置，突出校园实践与可塑性，适合在校生与应届生。",
        "section_order": ["education", "summary", "projects", "work", "skills", "certificates", "awards"],
        "accent": "#4D83D6",
        "header_align": "left",
    },
    {
        "id": "tech",
        "name": "技术研发型",
        "description": "技能栈置顶、项目详情展开，突出技术深度与工程实践。",
        "section_order": ["summary", "skills", "work", "projects", "education", "certificates", "awards"],
        "accent": "#315FAD",
        "header_align": "left",
    },
    {
        "id": "product",
        "name": "产品与运营型",
        "description": "项目经历前置、强调数据与结果表达，适合产品、运营、增长岗。",
        "section_order": ["summary", "projects", "work", "skills", "education", "certificates", "awards"],
        "accent": "#4D83D6",
        "header_align": "left",
    },
    {
        "id": "design",
        "name": "设计与创意型",
        "description": "左右分栏、作品链接醒目，适合设计、创意与内容类岗位。",
        "section_order": ["summary", "projects", "work", "education", "skills", "links", "awards"],
        "accent": "#315FAD",
        "header_align": "left",
        "layout": "two-column",
    },
    {
        "id": "research",
        "name": "科研与学术型",
        "description": "教育与项目（含论文成果）前置、行文严谨，适合科研与深造方向。",
        "section_order": ["education", "projects", "awards", "work", "skills", "certificates", "summary"],
        "accent": "#315FAD",
        "header_align": "center",
    },
    {
        "id": "finance",
        "name": "财务与管理型",
        "description": "版式稳重、证书资质突出，适合财务、审计与管理类岗位。",
        "section_order": ["summary", "work", "education", "certificates", "skills", "projects", "awards"],
        "accent": "#315FAD",
        "header_align": "left",
    },
]

TEMPLATE_BY_ID = {t["id"]: t for t in RESUME_TEMPLATES}

# 模板设计参考来源（官方公开指导资料；2026-10-13 人工核对可访问，仅借鉴通用结构与
# 经历描述原则转化为原创模板，不复制任何真实求职者的简历或个人信息）
TEMPLATE_REFERENCE_SOURCES: list[dict] = [
    {
        "name": "清华大学学生职业发展指导中心《学生就业指南》简历章节",
        "url": "https://career.tsinghua.edu.cn/__local/A/39/C8/0F017B98CFA29AF10D067E61415_33728D94_23AE444.pdf",
        "purpose": "简历结构、经历描述（STAR 方法）、重点展示与排版方式参考",
        "consulted_on": "2026-10-13",
    },
    {
        "name": "国家大学生就业服务平台「2027 校园招聘」求职指导",
        "url": "https://career.ncss.cn/ncss/zt/2027xyzp.shtml",
        "purpose": "面向应届毕业生与实习求职者的简历结构（基本信息/教育背景/实习与项目经历/技能证书）与经历描述公式参考",
        "consulted_on": "2026-10-13",
    },
]


def get_template(template_id: str) -> dict | None:
    return TEMPLATE_BY_ID.get(template_id)
