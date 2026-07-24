"""面评生成：结构对齐深澜面评 —— 一、简历(嵌原始简历文件) / 二、AI初筛(按岗位标准包评分) / 三、面试评价。
评分尺子＝HR知识库里对应岗位的胜任力模型(AI面评文档)，实时读取，知识库改了自动跟上。
HR 在进度表人工校正岗位后，resync() 自动改面评标题+按新岗位标准包重打AI初筛分(三、面试评价不动)。"""
import doubao
import standards


def _h3(t):
    return {"block_type": 5, "heading3": {"elements": [{"text_run": {"content": t}}]}}


def _p(t):
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": t or ""}}]}}


def _ol(t):
    """飞书原生有序列表块(自动编号——玄玄铁律:绝不手敲序号)。"""
    return {"block_type": 13, "ordered": {"elements": [{"text_run": {"content": t or ""}}]}}


def _label_list(label, items):
    """「标签:」一行 + 原生有序列表若干条。items 为空返回空列表。"""
    items = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not items:
        return []
    return [_p(f"{label}：")] + [_ol(x) for x in items]


def _block_text(b):
    """取一个块的纯文本(标题块/文本块通用)。"""
    for key in ("heading3", "heading2", "heading1", "text"):
        if key in b:
            return "".join(e.get("text_run", {}).get("content", "") for e in b[key].get("elements", []))
    return ""


def ai_section(fs, position, fields, position_hint=""):
    """「二、AI初筛」=简历-岗位匹配检查(玄玄定的边界:只评简历上看得见的,
    不碰沟通/逻辑/临场表现等面试观察维度,也不打分——分数留给面试)。
    产出:约不约面的建议 + 给面试官的考察提示。"""
    summary = fields.get("简历摘要", "") or "（简历信息有限）"
    rubric = standards.rubric_for(fs, position, position_hint)
    p = (
        "你是招聘初筛官,只看简历做「约面前检查」。注意:这是简历阶段,"
        "你只能评估简历上有明确证据的东西(学历/毕业时间/年限/技能/项目经历/跳槽频率);"
        "严禁评估沟通表达、逻辑思维、临场反应等只有面试才能观察的维度,严禁打分。\n"
        f"【该岗位的用人标准(其中面试观察类维度忽略,只取简历能核对的要求)】\n{rubric or '(无专属配置,按岗位常识)'}\n"
        f"【应聘岗位】{position or '待定'}\n【候选人简历】\n{summary}\n"
        '只输出JSON:{"约面建议":"建议约面/待定/不建议","匹配度":"高/中/低",'
        '"硬性门槛":["逐项核对学历/毕业时间/年限等,写符合还是不符,一条一句"],'
        '"匹配亮点":["简历里与岗位要求对得上的证据,一条一句,最多4条"],'
        '"风险与缺口":["简历可见的风险:经历缺口/跳槽频繁/岗位不对口等,一条一句,最多3条"],'
        '"面试需验证":["简历看不出来、留给面试官当场考察的点,最多3条"]}'
    )
    try:
        e = doubao.parse_json(doubao.ask(p))
    except Exception:
        e = {}
    blocks = [
        _h3("二、AI 初筛（简历-岗位匹配）"),
        _p(f"结论：{e.get('约面建议', '')} · 匹配度：{e.get('匹配度', '')}"),
    ]
    blocks += _label_list("硬性门槛", e.get("硬性门槛"))
    blocks += _label_list("匹配亮点", e.get("匹配亮点"))
    blocks += _label_list("风险与缺口", e.get("风险与缺口"))
    blocks += _label_list("面试需验证", e.get("面试需验证"))
    return blocks


def generate(fs, name, position, fields, resume_data=None, resume_name="简历.pdf", position_hint=""):
    # 笔试节(玄玄需求13:00:面评第一部分加笔试,占位待后续补充)。放最前面——
    # 不能夹在「二、AI初筛」和「三、面试评价」之间,否则 resync()岗位校正会把它当AI节吃掉。
    blocks = [_h3("笔试（待补充）"),
              _h3("一、简历")] + ai_section(fs, position, fields, position_hint) + \
             [_h3("三、面试评价"), _p("一面："), _p("二面："), _p("三面：")]
    title = f"面试评价-{position or 'xx岗位'}-{name or 'xxx'}"
    did, url = fs.create_doc(title, blocks)

    # 把原始简历文件嵌到"一、简历"标题(现在 index 1:笔试[0]之后)之后
    if resume_data:
        try:
            fs.insert_file_block(did, 2, resume_name, resume_data)
        except Exception:
            pass
    # 开组织内可编辑：应用建的文档默认只应用是 owner，HR 打不开/改不了，这里放开给公司同事
    try:
        fs.set_doc_org_editable(did)
    except Exception:
        pass
    return url


def render_round_eval(e, round_name):
    """面后AI面评 → 飞书块(排版对齐玄玄给的示例:字段一行一段,列表用原生有序列表)。"""
    blocks = [_p(f"结论：{e.get('结论', '')}"),
              _p(f"一句话总结：{e.get('一句话总结', '')}")]
    blocks += _label_list("优点", e.get("优点"))
    blocks += _label_list("缺点", e.get("缺点"))
    for k in ("基本信息", "求职进展", "求职期望", "工作情况", "个人情况"):
        v = str(e.get(k, "") or "").strip()
        if v:
            blocks.append(_p(f"{k}：{v}"))
    dims = e.get("分项打分") or []
    if dims:
        blocks.append(_p(f"总分{e.get('总分', '')}分，分项打分："))
        for d in dims[:8]:
            blocks.append(_ol(f"{d.get('维度', '')}：{d.get('得分', '')}/{d.get('满分', '')}。{d.get('简评', '')}"))
    v = str(e.get("补充判断", "") or "").strip()
    if v:
        blocks.append(_p(f"补充判断：{v}"))
    blocks += _label_list("下一轮建议重点验证", e.get("下一轮建议"))
    return blocks


def insert_round_eval(fs, doc_id, round_name, eval_data):
    """把面后AI面评(结构化dict)插进面评文档「{round_name}:」块之后,按示例排版渲染。
    找不到轮次块就追加到文档末尾(不丢内容)。返回插入位置说明。"""
    blocks = fs.doc_blocks(doc_id)
    root = next(b for b in blocks if b["block_id"] == doc_id)
    children = root.get("children", [])
    by_id = {b["block_id"]: b for b in blocks}
    idx = None
    for i, cid in enumerate(children):
        t = _block_text(by_id.get(cid, {})).strip()
        if t.startswith(round_name):  # "一面：" / "一面:"
            idx = i + 1
            break
    new_blocks = render_round_eval(eval_data, round_name)[:50]
    if idx is None:
        fs.replace_section(doc_id, len(children), len(children), new_blocks)  # 纯插入到末尾
        return "文档末尾(没找到轮次块)"
    fs.replace_section(doc_id, idx, idx, new_blocks)  # start==end → 纯插入
    return f"「{round_name}」之后"


def resync(fs, doc_id, name, position, fields, position_hint=""):
    """HR 人工校正岗位后联动面评：改标题 + 只重写「二、AI初筛」节(按新岗位标准包重打分)。
    「一、简历」(嵌的原始文件)和「三、面试评价」(HR手写)整段不碰。"""
    blocks = fs.doc_blocks(doc_id)
    root = next(b for b in blocks if b["block_id"] == doc_id)
    children = root.get("children", [])
    by_id = {b["block_id"]: b for b in blocks}

    start = end = None
    for i, cid in enumerate(children):
        t = _block_text(by_id.get(cid, {}))
        if t.startswith("二、AI"):
            start = i
        elif t.startswith("三、面试评价") and start is not None:
            end = i
            break
    if start is None or end is None:
        raise RuntimeError("面评结构不认识(找不到 二、AI初筛 / 三、面试评价)，不动")

    new_sec = ai_section(fs, position, fields, position_hint)
    fs.replace_section(doc_id, start, end, new_sec)
    fs.update_doc_title(doc_id, f"面试评价-{position}-{name}")
