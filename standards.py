"""岗位标准包：从公司「AI面评 Prompt」文档读取各岗位的评分标准(深澜同款尺子)，
给面评按维度打分用。文档里按【岗位配置 N：岗位名】分段。"""
import re
import time

AIEVAL_DOC = "Nsgbw1j1Bi1IYUkG6kkcaKcDnFe"  # AI面评 Prompt 文档（知识库·单一真源）
_TTL = 120  # 秒。知识库改了，最多 2 分钟内自动生效（不写死一份）
_cache = None
_cache_at = 0

# 标准岗位字段值 → 用于匹配配置标题的关键词
_KEYS = ["前端", "后端", "运维", "测试", "产品", "UI", "售前", "售后",
         "销售", "FDE", "管培生", "出海", "HR", "行政", "财务", "IP"]
# 岗位关键词 ≠ 配置标题用词时的别名(如岗位叫 HR、配置叫「人力资源管理专员」)
_ALIAS = {"HR": ["HR", "人力"], "IP": ["IP", "内容助理"]}


def _load(fs):
    """带时效地从知识库读最新标准；过期就重读，保证跟知识库同步。"""
    global _cache, _cache_at
    if _cache is None or (time.time() - _cache_at) > _TTL:
        content = fs.read_doc_content(AIEVAL_DOC)
        cfgs = {}
        for chunk in re.split(r"【岗位配置\s*\d+[:：]", content)[1:]:
            header = chunk.split("】")[0].strip()
            cfgs[header] = chunk[:2000]
        m = re.search(r"【岗位配置\s*1[:：]", content)
        head = content[:m.start()] if m else content[:9000]
        _cache = {"cfgs": cfgs, "shell": head}
        _cache_at = time.time()
    return _cache


def prompt_shell(fs):
    """面评Prompt的通用壳(任务目标/身份/风格/分数规则/固定输出结构/工作流程),
    即知识库文档「十一、岗位配置表」之前的全部——面后面评按它的格式输出,玄玄改文档自动生效。"""
    try:
        return _load(fs)["shell"]
    except Exception:
        return ""


def rubric_for(fs, position, hint=""):
    """按岗位取该岗位的评分标准；取不到返回 ''(退回通用打分)。
    hint = 更细的岗位线索(如文件名里的「AI管培生（市场）」)，用来在一个岗位有多个方向时选对配置
    (如管培生分技术/市场，前端≠全栈)。"""
    text = f"{position} {hint}".strip()
    if not text:
        return ""
    try:
        cfgs = _load(fs)["cfgs"]
    except Exception:
        return ""
    # 岗位字段优先定配置(HR校正过的岗位说了算)，岗位空/没命中才用文件名线索兜底
    pk = next((k for k in _KEYS if k in (position or "")), None) \
        or next((k for k in _KEYS if k in (hint or "")), None)
    if not pk:
        return ""
    keys = _ALIAS.get(pk, [pk])
    matches = [(h, t) for h, t in cfgs.items() if any(k in h for k in keys)]
    if not matches:
        return ""
    if len(matches) > 1:  # 同一岗位多方向：按线索里的方向词二选一(市场/技术/出海/政务)
        for d in ("市场", "技术", "出海", "政务"):
            if d in text:
                for h, t in matches:
                    if d in h:
                        return t
    return matches[0][1]
