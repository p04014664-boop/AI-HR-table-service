"""核心两条规则 + 手动传简历。全部用应用身份，DRY_RUN 安全演练。"""
import os
import json
import logging
import requests
from config import cfg
from feishu import Feishu
import doubao
import resume
import mianping

log = logging.getLogger("rules")
fs = Feishu()


def _cell(v):
    if isinstance(v, list):
        return " ".join((x.get("text") or x.get("name", "")) if isinstance(x, dict) else str(x) for x in v)
    if isinstance(v, dict):
        return v.get("text") or v.get("link") or ""
    return v if isinstance(v, str) else ""


def _load_state():
    if os.path.exists(cfg.STATE_FILE):
        try:
            return json.load(open(cfg.STATE_FILE))
        except Exception:
            pass
    return {"synced": [], "reached": []}


def _save_state(s):
    os.makedirs(os.path.dirname(cfg.STATE_FILE) or ".", exist_ok=True)
    json.dump(s, open(cfg.STATE_FILE, "w"), ensure_ascii=False)


def rule1_sync(prog_records):
    """规则①：AI-HR【HR评估=约面】→ 判岗位 + 解析简历 + 设面试官 → 写进度表。幂等(按候选人ID)。"""
    state = _load_state()
    synced = set(state["synced"])
    positions = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位")
    categories = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位大类")
    channels = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "渠道")
    screen = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "简历筛选")

    # 进度表里已被本服务 AI 同步过的人(按姓名)——第二道防重复
    already = {_cell(r["fields"].get("姓名")) for r in prog_records
               if "AI约面同步" in _cell(r["fields"].get("备忘录"))}

    records = fs.list_records(cfg.AIHR_APP, cfg.AIHR_TABLE, automatic_fields=True)
    done = 0
    for r in records:
        f = r["fields"]
        if _cell(f.get("HR评估")) != "约面":
            continue
        cid = _cell(f.get("AIHR候选人ID")) or r["record_id"]
        if cid in synced:
            continue  # 幂等①：状态文件已记录(含预置的老约面白名单)

        name = _cell(f.get("姓名"))
        if name in already:  # 幂等②：进度表已有该人AI同步记录
            synced.add(cid)
            continue
        boss = _cell(f.get("岗位"))
        src = _cell(f.get("简历来源"))
        phone = _cell(f.get("联系方式"))
        concl = _cell(f.get("AI HR结论"))
        mianping = _cell(f.get("面评"))

        j = doubao.classify_position(boss, src, positions, categories, channels)

        # 解析简历：补候选人身份 + 补没爬到的手机号
        shen = ""
        att = f.get("简历") if isinstance(f.get("简历"), list) else None
        if att:
            try:
                data = fs.download_attachment(att[0])
                fields, way = resume.extract_fields(data, att[0].get("name", ""))
                shen = fields.get("是否应届生", "")
                if not phone:
                    phone = fields.get("手机号", "")
                log.info(f"  简历解析({way}): {name} 身份={shen} 手机={phone or '无'}")
            except Exception as e:
                log.warning(f"  {name} 简历解析失败: {e}")

        # 一面面试官 = 谁点的约面(last_modified_by)。读写同一应用 → open_id 一致，能写进人员字段。
        interviewer = (r.get("last_modified_by") or {}).get("id")

        rec = {"姓名": name, "备忘录": "AI约面同步"}
        if j.get("岗位") in positions:
            rec["岗位"] = j["岗位"]
        if j.get("大类") in categories:
            rec["岗位大类"] = j["大类"]
        if j.get("渠道") in channels:
            rec["渠道"] = j["渠道"]
        if phone:
            rec["联系方式"] = phone
        if "通过" in concl and "通过" in screen:
            rec["简历筛选"] = "通过"
        if mianping:
            rec["面试评价"] = mianping
        if shen in ("应届生", "非应届生"):
            rec["候选人身份"] = shen
        if interviewer:
            rec["一面面试官"] = [{"id": interviewer}]

        if cfg.DRY_RUN:
            log.info(f"[DRY] 规则①→写: {json.dumps(rec, ensure_ascii=False)}")
        else:
            rid = fs.create_record(cfg.PROG_APP, cfg.PROG_TABLE, rec)
            if att:  # 搬简历附件：下载→上传到进度表→写附件字段
                try:
                    tok = fs.upload_media(att[0].get("name", "简历.pdf"),
                                          fs.download_attachment(att[0]), cfg.PROG_APP)
                    fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"简历": [{"file_token": tok}]})
                except Exception as e:
                    log.warning(f"  {name} 简历附件搬运失败(需 drive 上传权限): {e}")
            log.info(f"规则①已写入: {name} ({rid})")

        synced.add(cid)
        done += 1
        if cfg.MAX_PER_CYCLE and done >= cfg.MAX_PER_CYCLE:
            break

    state["synced"] = list(synced)
    _save_state(state)
    return done


def fetch_progress():
    """每轮只拉一次进度表(带 last_modified_by),各规则共用,别每条规则各扫一遍全表。"""
    return fs.list_records(cfg.PROG_APP, cfg.PROG_TABLE, automatic_fields=True)


def _at_of(record, f):
    """群提醒@谁:优先最后改记录的人(真人操作才有),兜底@一面面试官,都没有返回空串。"""
    at_id = (record.get("last_modified_by") or {}).get("id")
    if not at_id:
        iv = f.get("一面面试官")
        at_id = iv[0].get("id") if isinstance(iv, list) and iv else None
    return f'<at user_id="{at_id}"></at> ' if at_id else ""


def _remind(text):
    fs.send_group_text(cfg.REMIND_CHAT_ID, text)


# 触达前必须齐的信息(玄玄定的:勾了AI触达≠直接触达,缺信息先@人补齐)
_REACH_REQUIRED = ["联系方式", "岗位", "一面时间", "一面面试官"]


def _is_phone(s):
    import re as _re
    return bool(_re.fullmatch(r"1[3-9]\d{9}", _re.sub(r"[\s-]", "", s or "")))


def _invite(rid, f, round_name):
    """调触达服务发起某一轮的约面邀约。首轮=加好友+邀约;后续轮=同号重触达(老好友直接收新邀约)。
    联系方式栏语义(玄玄定)=「能联系上他的微信号」:默认手机号=微信号;人工校正后可能填的是微信号。
    是手机号→走 phone;不是→当微信号,phone 原样带 + wxid 字段(中台按类型选加友方式)。"""
    contact = _cell(f.get("联系方式")).strip()
    payload = {
        "dataId": rid,
        "phone": contact,
        "name": _cell(f.get("姓名")),
        "position": _cell(f.get("岗位")),
        "interviewer": _cell(f.get(f"{round_name}面试官")),
        "interviewTime": str(f.get(f"{round_name}时间") or ""),  # 传毫秒字符串,宏佳侧parseInterviewTime认13位
        "round": round_name,  # 中台暂未用,先带上,话术分轮次时就有了
    }
    if not _is_phone(contact):
        payload["wxid"] = contact  # 微信号加友,等中台支持
    requests.post(f"{cfg.REACH_URL}/reach", json=payload, timeout=30)


def rule2_reach(records):
    """规则②：进度表【AI触达】勾选 → 前置自检必填信息 → 齐了才调触达服务加企微好友。
    缺信息：不触达，去群里@点勾选的人(或一面面试官)报缺什么；补齐后下一轮自动触达。
    重触达(玄玄定的场景)：加不上好友→HR人工校正联系方式(可能填成微信号)→
      ①联系方式变了且仍勾着 → 自动重新触达新号；②取消勾选再勾 → 也重新触达。
    幂等：reached 记 {记录ID: 触达时的联系方式}；同缺项组合只提醒一次。"""
    state = _load_state()
    reached = state.get("reached")
    if isinstance(reached, list):  # 老格式(纯ID列表)迁移:联系方式记空=不知道,变化检测从下次起效
        reached = {rid: "" for rid in reached}
    state["reached"] = reached = reached or {}
    reminded = state.setdefault("reminded", {})
    invited = state.setdefault("round_invited", {})
    known_time = state.setdefault("known_time", {})
    done = 0
    for r in records:
        f = r["fields"]
        rid = r["record_id"]
        checked = f.get("AI触达") or f.get("AI触答")  # 兼容"触答"笔误字段名
        if not checked:
            if rid in reached:
                reached.pop(rid, None)  # 取消勾选=撤销授权;再勾=重新触达
            continue
        contact_now = _cell(f.get("联系方式")).strip()
        if rid in reached:
            prev = reached[rid]
            if not prev or prev == contact_now or not contact_now:
                continue  # 已触达且号没变(或老数据没记号) → 不重复
            log.info(f"规则② {_cell(f.get('姓名'))} 联系方式已人工校正({prev}→{contact_now}),重新触达")
        name = _cell(f.get("姓名"))

        # ── 前置自检:该有的信息不齐就不触达,先@人补 ──
        missing = [k for k in _REACH_REQUIRED if not (_cell(f.get(k)) or f.get(k))]
        if missing:
            sig = ",".join(missing)
            if reminded.get(rid) != sig:
                msg = (f"{_at_of(r, f)}候选人【{name or rid}】勾了AI触达，但还缺：{('、'.join(missing))}。"
                       f"补齐后我会自动发起触达~")
                if cfg.DRY_RUN:
                    log.info(f"[DRY] 规则②缺信息提醒: {msg}")
                else:
                    try:
                        _remind(msg)
                        log.info(f"规则② {name} 缺{sig}，已群内提醒")
                    except Exception as e:
                        log.warning(f"  {name} 缺信息提醒发送失败: {e}")
                        continue  # 提醒没发出去,下轮重试
                reminded[rid] = sig
            continue

        # ── 信息齐了 → 首轮触达 ──
        if cfg.DRY_RUN:
            log.info(f"[DRY] 规则②→触达: {name}")
        else:
            try:
                _invite(rid, f, "一面")
                fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"触达状态": "待触达"})
                log.info(f"规则②已触发触达: {name}")
            except Exception as e:
                log.warning(f"  {name} 触达调用失败: {e}")
                continue
        reached[rid] = contact_now
        invited[rid] = "一面"
        known_time[rid] = f.get("一面时间")
        reminded.pop(rid, None)
        done += 1
    _save_state(state)
    return done


def rule5_handover(records):
    """规则⑤(转人工)：进度表【转人工】勾选状态变化 → 同步给触达服务(宏佳)，
    由它更新 Mongo 里该候选人触达任务的 humanTakeover。true=AI 停止接待、HR 真人跟进；取消勾选=恢复AI。
    分工铁律：本服务只动表格；Mongo/对外发消息一律经触达服务。
    幂等：state 记录每条的上次状态，只有变化才调；调失败不记状态、下轮重试。"""
    state = _load_state()
    known = state.setdefault("handover", {})
    done = 0
    for r in records:
        rid = r["record_id"]
        cur = bool(r["fields"].get("转人工"))
        prev = known.get(rid)
        if prev is None and not cur:
            known[rid] = False       # 首次见到且未勾选：只登记，不打扰触达服务
            continue
        if prev == cur:
            continue
        name = _cell(r["fields"].get("姓名"))
        if cfg.DRY_RUN:
            log.info(f"[DRY] 规则⑤→转人工: {name} handover={cur}")
            known[rid] = cur
        else:
            try:
                resp = requests.post(f"{cfg.REACH_URL}/handover",
                                     json={"dataId": rid, "handover": cur}, timeout=15)
                j = resp.json() if resp.ok else {}  # NestJS POST 默认返回 201,只认 200 会把成功当失败
                if j.get("ok"):
                    log.info(f"✅ 规则⑤转人工同步: {name} → {'人工接管' if cur else '恢复AI'} ({j.get('taskId')})")
                    known[rid] = cur
                    if cur:  # HR勾的转人工也在表上标出结构化状态
                        try:
                            fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"触达状态": "转人工中"})
                        except Exception:
                            pass
                elif j.get("msg", "").startswith("dataId"):
                    # 该记录压根没触达任务(比如还没触达过)：登记状态即可，不算失败
                    log.info(f"  规则⑤: {name} 无触达任务，只记状态 handover={cur}")
                    known[rid] = cur
                else:
                    log.warning(f"  规则⑤ {name} 同步失败({resp.status_code}): {resp.text[:120]}，下轮重试")
                    continue
            except Exception as e:
                log.warning(f"  规则⑤ {name} 调触达服务失败: {e}，下轮重试")
                continue
        done += 1
    _save_state(state)
    return done


# 轮次链:上一轮反馈=通过 → 推进下一轮
_ROUNDS = [("一面", "二面"), ("二面", "三面")]


def rule7_rounds(records):
    """规则⑦(轮次推进)：X面反馈=通过 → 下一轮信息没齐就群里@人提醒排面;
    下一轮【时间+面试官】齐了 → 自动向候选人发下一轮邀约(老好友直接发,不再加好友)。
    授权模型:首轮勾【AI触达】=授权AI跟这个候选人全程沟通,后续轮不用再勾。
    门禁:没勾AI触达不动;转人工中不动;每记录每轮只邀约/提醒一次(state)。"""
    state = _load_state()
    reached = set(state["reached"])
    invited = state.setdefault("round_invited", {})
    r_reminded = state.setdefault("round_reminded", {})
    known_time = state.setdefault("known_time", {})
    done = 0
    for r in records:
        rid = r["record_id"]
        f = r["fields"]
        if rid not in reached:          # 首轮都没触达过的不归这里管
            continue
        if f.get("转人工"):              # 人工接管中,AI不推进
            continue
        name = _cell(f.get("姓名"))
        for prev, nxt in _ROUNDS:
            if _cell(f.get(f"{prev}反馈")) != "通过":
                continue
            if invited.get(rid) and _round_ge(invited[rid], nxt):
                continue  # 这一轮已经邀约过
            t, iv = f.get(f"{nxt}时间"), _cell(f.get(f"{nxt}面试官"))
            if t and iv:
                if cfg.DRY_RUN:
                    log.info(f"[DRY] 规则⑦→{nxt}邀约: {name}")
                else:
                    try:
                        _invite(rid, f, nxt)
                        fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"触达状态": "已发邀约"})
                        _remind(f"候选人【{name}】{prev}通过,已自动发出{nxt}邀约(面试官:{iv})。")
                        log.info(f"规则⑦ {name} {nxt}邀约已发起")
                    except Exception as e:
                        log.warning(f"  {name} {nxt}邀约失败: {e}")
                        continue
                invited[rid] = nxt
                known_time[rid] = t
                done += 1
            else:
                mark = f"{nxt}缺排期"
                if r_reminded.get(rid) != mark:
                    lack = "、".join([x for x, v in ((f"{nxt}时间", t), (f"{nxt}面试官", iv)) if not v])
                    msg = f"{_at_of(r, f)}候选人【{name}】{prev}已通过,请排{nxt}:补【{lack}】,填好我自动给候选人发{nxt}邀约~"
                    if cfg.DRY_RUN:
                        log.info(f"[DRY] 规则⑦排面提醒: {msg}")
                    else:
                        try:
                            _remind(msg)
                            log.info(f"规则⑦ {name} {prev}通过缺{nxt}排期,已提醒")
                        except Exception as e:
                            log.warning(f"  {name} 排面提醒失败: {e}")
                            continue
                    r_reminded[rid] = mark
            break  # 一条记录一轮只推一步
    _save_state(state)
    return done


def _round_ge(a, b):
    order = {"一面": 1, "二面": 2, "三面": 3}
    return order.get(a, 0) >= order.get(b, 0)


def rule8_time_change(records):
    """规则⑧(改期联动)：已触达候选人的当前轮【X面时间】被改 → 自动重发该轮邀约(候选人收到新时间)
    + 群里通报。面试官/HR改表格时间=确认改期,不用学任何新操作。"""
    state = _load_state()
    reached = set(state["reached"])
    invited = state.setdefault("round_invited", {})
    known_time = state.setdefault("known_time", {})
    done = 0
    for r in records:
        rid = r["record_id"]
        f = r["fields"]
        if rid not in reached or f.get("转人工"):
            continue
        rnd = invited.get(rid) or "一面"
        cur = f.get(f"{rnd}时间")
        if not cur:
            continue
        old = known_time.get(rid)
        if old is None:
            known_time[rid] = cur  # 首次登记,不触发
            continue
        if cur == old:
            continue
        name = _cell(f.get("姓名"))
        if cfg.DRY_RUN:
            log.info(f"[DRY] 规则⑧改期重邀: {name} {rnd} {old}→{cur}")
        else:
            try:
                _invite(rid, f, rnd)
                fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"触达状态": "已发邀约"})
                _remind(f"候选人【{name}】的{rnd}时间已改,新邀约已自动发给候选人确认。")
                log.info(f"规则⑧ {name} {rnd}改期重邀已发起")
            except Exception as e:
                log.warning(f"  {name} 改期重邀失败: {e}")
                continue
        known_time[rid] = cur
        done += 1
    _save_state(state)
    return done


def rule4_position_correction(records):
    """校正联动：HR 在进度表人工改了【岗位】→ 本服务生成的面评自动跟上——
    改标题为 面试评价-新岗位-姓名 + 按新岗位的标准包重打AI初筛分。
    「一、简历」「三、面试评价」(HR手写)整段不碰。只碰 备忘录=手动简历·AI解析 的行(深澜的面评绝不动)。
    幂等：标题已一致就跳过，零成本。"""
    done = 0
    for r in records:
        f = r["fields"]
        if "手动简历·AI解析" not in _cell(f.get("备忘录")):
            continue
        name, pos = _cell(f.get("姓名")), _cell(f.get("岗位"))
        url = _cell(f.get("面试评价"))
        if not (name and pos and "/docx/" in url):
            continue
        doc_id = url.rstrip("/").split("/docx/")[-1].split("?")[0]
        expect = f"面试评价-{pos}-{name}"
        try:
            title = fs.get_doc_title(doc_id)
        except Exception:
            continue
        if not title.startswith("面试评价-") or title == expect:
            continue  # 不是我们的命名 / 已经一致

        fields, hint = {}, ""
        att = f.get("简历")
        if isinstance(att, list) and att:
            hint = resume.position_from_filename(att[0].get("name", ""))
            try:
                data = fs.download_attachment(att[0])
                fields, _ = resume.extract_fields(data, att[0].get("name", ""))
            except Exception as e:
                log.warning(f"  {name} 校正联动读简历失败: {e}")
        if cfg.DRY_RUN:
            log.info(f"[DRY] 岗位校正联动: {title} → {expect}")
        else:
            try:
                mianping.resync(fs, doc_id, name, pos, fields, hint)
                log.info(f"✅ 岗位校正联动: 「{title}」→「{expect}」，AI初筛已按新岗位标准包重评")
            except Exception as e:
                log.warning(f"  {name} 校正联动失败: {e}")
                continue
        done += 1
    return done


def rule3_manual_resume(records):
    """链路B：HR 手动往进度表丢一份简历(空白行只有附件) → 读简历自动填字段。
    只碰「有简历附件 + 姓名为空 + 备忘录为空」的行，绝不动任何已有记录。"""
    positions = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位")
    categories = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位大类")
    channels = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "渠道")
    done = 0
    for r in records:
        f = r["fields"]
        att = f.get("简历")
        if not (isinstance(att, list) and att):
            continue
        if _cell(f.get("姓名")):        # 已有姓名 = 不是空白手动行，保护已有记录
            continue
        memo = _cell(f.get("备忘录"))
        if "手动简历" in memo or "AI约面同步" in memo:
            continue
        try:
            data = fs.download_attachment(att[0])
            fields, way = resume.extract_fields(data, att[0].get("name", ""))
        except Exception as e:
            log.warning(f"手动简历解析失败: {e}")
            continue
        rec = {"备忘录": "手动简历·AI解析"}
        if fields.get("姓名"):
            rec["姓名"] = fields["姓名"]
        if fields.get("手机号"):
            rec["联系方式"] = fields["手机号"]
        if fields.get("是否应届生") in ("应届生", "非应届生"):
            rec["候选人身份"] = fields["是否应届生"]
        # 岗位判断：先信 BOSS 简历文件名里的【岗位_...】(候选人真实投递岗位，最权威)，
        # 抓不到再退回读简历正文猜的方向。
        pos_hint = resume.position_from_filename(att[0].get("name", ""))
        boss = pos_hint or fields.get("求职意向岗位", "") or fields.get("推测岗位方向", "")
        if boss:
            j = doubao.classify_position(boss, "手动上传", positions, categories, channels)
            if j.get("岗位") in positions:
                rec["岗位"] = j["岗位"]
            if j.get("大类") in categories:
                rec["岗位大类"] = j["大类"]
        # 生成面评文档（手动简历没深澜面评，豆包按模板生成一份）；pos_hint 让管培生等分方向选对标准包
        if not cfg.DRY_RUN:
            try:
                rec["面试评价"] = mianping.generate(fs, rec.get("姓名", ""), rec.get("岗位", ""),
                                                fields, data, att[0].get("name", "简历.pdf"),
                                                position_hint=pos_hint)
            except Exception as e:
                log.warning(f"面评生成失败: {e}")
        log.info(f"手动简历解析({way}): {fields.get('姓名', '?')} 手机={fields.get('手机号', '')} 身份={fields.get('是否应届生', '')}")
        if cfg.DRY_RUN:
            log.info(f"[DRY] 链路B→填: {json.dumps(rec, ensure_ascii=False)}")
        else:
            fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, r["record_id"], rec)
            log.info(f"✅ 手动简历已识别填充: {rec.get('姓名', '?')} ({r['record_id']})")
        done += 1
    return done
