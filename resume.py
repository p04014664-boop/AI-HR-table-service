"""简历解析：自动识别 PDF / 图片(照片)，PDF 有文字层直接读、否则渲染成图交给豆包看。"""
import re
import fitz  # pymupdf
import doubao


def position_from_filename(filename: str) -> str:
    """从 BOSS 简历文件名抓候选人真实投递的岗位。命名格式：【岗位_城市 薪资】姓名 N年.pdf。
    这是候选人自己投的岗位，比读简历正文猜更权威。抓不到(如猎头推荐文件)返回空串。"""
    m = re.search(r"【([^_】]+)[_】]", filename or "")
    return m.group(1).strip() if m else ""

FIELDS_PROMPT = (
    "从这份简历里抽取信息，只输出JSON，找不到的填空字符串："
    '{"姓名":"","手机号":"","邮箱":"","最高学历":"","毕业院校":"",'
    '"毕业时间":"","是否应届生":"应届生或非应届生","求职意向岗位":"",'
    '"推测岗位方向":"根据其经历技能推测最可能应聘的岗位方向，如后端工程师/市场运营/HR等",'
    '"简历摘要":"3-4句话概括候选人的学历/经历/核心技能/亮点"}'
)


def detect_kind(data: bytes) -> str:
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return "unknown"


def extract_fields(data: bytes, filename: str = ""):
    """返回 (字段dict, 解析方式)。方式∈ pdf-text / pdf-image / photo / unknown。"""
    kind = detect_kind(data)
    try:
        if kind == "pdf":
            doc = fitz.open(stream=data, filetype="pdf")
            text = "\n".join(p.get_text() for p in doc)
            if len(text.strip()) >= 200:  # 有文字层：直接读，省钱又快
                return _safe(doubao.ask(FIELDS_PROMPT + "\n简历文本:\n" + text[:3000])), "pdf-text"
            # 图片型 PDF：渲染首页成图，交给视觉
            img = doc[0].get_pixmap(dpi=150).tobytes("png")
            return _safe(doubao.ask_image(FIELDS_PROMPT + "（这是简历图片，请识别）", img, "image/png")), "pdf-image"
        if kind in ("jpg", "png"):
            mime = "image/jpeg" if kind == "jpg" else "image/png"
            return _safe(doubao.ask_image(FIELDS_PROMPT + "（这是简历照片，请识别）", data, mime)), "photo"
    except Exception as e:  # noqa
        return {"_error": str(e)}, kind
    return {}, "unknown"


def _safe(raw):
    try:
        return doubao.parse_json(raw)
    except Exception:
        return {}
