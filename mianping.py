"""面评生成：结构对齐深澜面评 —— 一、简历(嵌原始简历文件) / 二、AI初筛(按岗位标准包评分) / 三、面试评价。
评分尺子＝HR知识库里对应岗位的胜任力模型(AI面评文档)，实时读取，知识库改了自动跟上。
HR 在进度表人工校正岗位后，resync() 自动改面评标题+按新岗位标准包重打AI初筛分(三、面试评价不动)。"""
import doubao
import standards


def _h3(t):
    return {"block_type": 5, "heading3": {"elements": [{"text_run": {"content": t}}]}}


def _p(t):
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": t or ""}}]}}


def _block_text(b):
    """取一个块的纯文本(标题块/文本块通用)。"""
    for key in ("heading3", "heading2", "heading1", "text"):
        if key in b:
            return "".join(e.get("text_run", {}).get("content", "") for e in b[key].get("elements", []))
    return ""


def ai_section(fs, position, fields, position_hint=""):
    """按岗位标准包给候选人打分，返回「二、AI初筛」整节的块列表(含节标题)。"""
    summary = fields.get("简历摘要", "") or "（简历信息有限）"
    rubric = standards.rubric_for(fs, position, position_hint)

    if rubric:
        p = (
            "你是资深招聘官。严格按下面这份【岗位评分标准】的维度和权重给候选人打分，不要用你自己的通用判断。"
            '只输出JSON：{"各维度得分":{"维度名":分数},"总分":0,"结论":"","一票否决":"无或具体",'
            '"亮点":"","顾虑":""}\n'
            f"【岗位评分标准】\n{rubric}\n\n【候选人简历】\n{summary}"
        )
    else:
        p = (f"你是资深招聘官，基于简历针对「{position or '所投'}」岗位做初筛，只输出JSON："
             '{"总分":0,"结论":"","亮点":"","顾虑":""}\n' + f"简历摘要：{summary}")
    try:
        e = doubao.parse_json(doubao.ask(p))
    except Exception:
        e = {}

    dims = e.get("各维度得分", {}) or {}
    dim_line = "  ".join(f"{k}:{v}" for k, v in dims.items())
    src_note = "（按岗位标准包评分）" if rubric else "（通用评分·未匹配到标准包）"

    blocks = [
        _h3("二、AI 初筛" + src_note),
        _p(f"结论：{e.get('结论', '')}"),
        _p(f"总分：{e.get('总分', '')}      一票否决：{e.get('一票否决', '无')}"),
    ]
    if dim_line:
        blocks.append(_p(f"各维度得分：{dim_line}"))
    blocks += [_p(f"亮点：{e.get('亮点', '')}"), _p(f"顾虑：{e.get('顾虑', '')}")]
    return blocks


def generate(fs, name, position, fields, resume_data=None, resume_name="简历.pdf", position_hint=""):
    blocks = [_h3("一、简历")] + ai_section(fs, position, fields, position_hint) + \
             [_h3("三、面试评价"), _p("一面："), _p("二面："), _p("三面：")]
    title = f"面试评价-{position or 'xx岗位'}-{name or 'xxx'}"
    did, url = fs.create_doc(title, blocks)

    # 把原始简历文件嵌到"一、简历"标题(index 0)之后
    if resume_data:
        try:
            fs.insert_file_block(did, 1, resume_name, resume_data)
        except Exception:
            pass
    # 开组织内可编辑：应用建的文档默认只应用是 owner，HR 打不开/改不了，这里放开给公司同事
    try:
        fs.set_doc_org_editable(did)
    except Exception:
        pass
    return url


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
