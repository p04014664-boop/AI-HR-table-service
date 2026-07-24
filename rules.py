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
import standards

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


def _write_state(s):
    """原子落盘(tmp+replace)。调用方须持有 _sync_lock。"""
    os.makedirs(os.path.dirname(cfg.STATE_FILE) or ".", exist_ok=True)
    tmp = cfg.STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, ensure_ascii=False)
    os.replace(tmp, cfg.STATE_FILE)


def _save_state(s):
    """主循环规则存整个 state → 收口到 _sync_lock,并在锁内重读磁盘最新 synced 覆回。
    防止主循环用陈旧 synced 清掉 webhook 线程(_finish)刚落盘的白名单 → 候选人重复建档
    (=187 bug 换姿势偶发复发,宏佳 review 指出)。synced 只由 _finish 在锁内独占写;
    其余 key(reached/handover/round_invited…)只有主循环单线程写,不冲突。"""
    with _sync_lock:
        try:
            s["synced"] = _load_state().get("synced", s.get("synced", []))
        except Exception:
            pass
        _write_state(s)


def _enrich_candidate(rid, name, f, opts, phone_written):
    """后台补全(不阻塞秒建——玄玄最高优先级:记录先出现,解析动作滞后补):
    ①豆包判岗位(~9s)→回填 岗位/大类/渠道 + 面评标题岗位对齐 ②解析简历补身份/手机 ③搬简历附件。"""
    positions, categories, channels, screen = opts
    # ① 岗位判定(豆包慢动作,之前卡在建档主路径导致进表要10秒;挪到这里,记录已先出现)
    patch = {}
    try:
        boss = _cell(f.get("岗位"))
        src = _cell(f.get("简历来源"))
        j = doubao.classify_position(boss, src, positions, categories, channels)
        if j.get("岗位") in positions:
            patch["岗位"] = j["岗位"]
        if j.get("大类") in categories:
            patch["岗位大类"] = j["大类"]
        if j.get("渠道") in channels:
            patch["渠道"] = j["渠道"]
        # 面评标题岗位对齐(玄玄需求):深澜面评标题用BOSS岗位名,换成我们的标准岗位;链接保留
        mp_raw = f.get("面评")
        mp = _cell(mp_raw)
        link = mp_raw[0].get("link") if isinstance(mp_raw, list) and mp_raw and isinstance(mp_raw[0], dict) else ""
        std_pos = patch.get("岗位") or "岗位待定"
        if link:  # 标准标题 + 链接(飞书文本字段URL自动识别可点)
            patch["面试评价"] = f"面试评价-{std_pos}-{name}\n{link}"
        elif mp:
            patch["面试评价"] = mp
        if patch and not cfg.DRY_RUN:
            fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, patch)
        log.info(f"  ✅ 岗位后台回填: {name} 岗位={patch.get('岗位', '?')}")
    except Exception as e:
        log.warning(f"  {name} 岗位判定后台补全失败: {e}")
    # ② 简历解析(补身份/手机)+ ③ 搬附件
    att = f.get("简历") if isinstance(f.get("简历"), list) else None
    if not att:
        return
    try:
        data = fs.download_attachment(att[0])
        fields, way = resume.extract_fields(data, att[0].get("name", ""))
        upd = {}
        shen = fields.get("是否应届生", "")
        if shen in ("应届生", "非应届生"):
            upd["候选人身份"] = shen
        if not phone_written and fields.get("手机号"):
            upd["联系方式"] = fields["手机号"]
        if upd:
            fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, upd)
        try:
            tok = fs.upload_media(att[0].get("name", "简历.pdf"), data, cfg.PROG_APP)
            fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"简历": [{"file_token": tok}]})
        except Exception as e:
            log.warning(f"  {name} 简历附件搬运失败(需 drive 上传权限): {e}")
        log.info(f"  ✅ 规则①后台补全: {name} 身份={shen or '?'} ({way})")
    except Exception as e:
        log.warning(f"  {name} 简历后台补全失败: {e}")


# 字段选项 60s 缓存(每轮 rule1 都取会拖慢;选项极少变)
_opt_cache = {"at": 0, "v": None}


def _prog_options():
    import time as _t
    if _opt_cache["v"] and _t.time() - _opt_cache["at"] < 60:
        return _opt_cache["v"]
    v = (fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位"),
         fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位大类"),
         fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "渠道"),
         fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "简历筛选"))
    _opt_cache.update(at=_t.time(), v=v)
    return v


import threading as _threading
_sync_lock = _threading.RLock()  # 可重入:_save_state 也在锁内,防嵌套自锁
_inflight = set()  # 正在处理的候选人ID,防 webhook 与轮询并发建两条


def _try_claim(cid):
    """抢占某候选人的处理权:已同步过或正在处理→抢不到(返回False)。锁内实时读state,原子。"""
    with _sync_lock:
        st = _load_state()
        if cid in set(st.get("synced", [])) or cid in _inflight:
            return False
        _inflight.add(cid)
        return True


def _finish(cid, ok):
    """释放处理权;成功则落入 synced 白名单。"""
    with _sync_lock:
        _inflight.discard(cid)
        if ok:
            st = _load_state()
            s = set(st.get("synced", []))
            s.add(cid)
            st["synced"] = list(s)
            _write_state(st)  # 已在锁内,直接原子落盘;不走会覆盖 synced 的 _save_state


def _sync_one(full, opts, interviewer=None):
    """处理单条 AI-HR 约面记录 → 秒建进度表记录 + 简历后台补。full=带automatic的完整记录。
    interviewer=谁点约面的open_id。抢占锁防并发重复。返回是否新建。"""
    import threading
    f = full["fields"]
    cid = _cell(f.get("AIHR候选人ID")) or full["record_id"]
    if not _try_claim(cid):
        return False  # 已同步/正在处理,跳过(防 webhook×轮询 建两条)
    ok = False
    try:
        ok = _do_sync(full, opts, interviewer, cid, f)
    finally:
        _finish(cid, ok)
    return ok


def _do_sync(full, opts, interviewer, cid, f):
    """秒建(玄玄最高优先级:3秒进表):只填"不用解析就能拿到"的基本信息立刻建记录,
    岗位判定/面评标题/简历解析这些慢动作全丢后台线程补,不挡记录出现。"""
    name = _cell(f.get("姓名"))
    positions, categories, channels, screen = opts
    phone = _cell(f.get("联系方式"))
    concl = _cell(f.get("AI HR结论"))
    if interviewer is None:
        interviewer = (full.get("last_modified_by") or {}).get("id")
    rec = {"姓名": name, "备忘录": "AI约面同步"}
    if phone:
        rec["联系方式"] = phone
    if "通过" in concl and "通过" in screen:
        rec["简历筛选"] = "通过"
    if interviewer:
        rec["一面面试官"] = [{"id": interviewer}]
    if cfg.DRY_RUN:
        log.info(f"[DRY] 秒建: {json.dumps(rec, ensure_ascii=False)} (岗位/面评/简历后台补)")
        return True
    rid = fs.create_record(cfg.PROG_APP, cfg.PROG_TABLE, rec)
    log.info(f"⚡秒建: {name} ({rid}) —— 岗位/面评/简历后台补")
    _threading.Thread(target=_enrich_candidate,
                      args=(rid, name, f, opts, bool(phone)), daemon=True).start()
    # 白名单由 _sync_one 的 _finish(cid, ok=True) 落盘,这里不再手动 synced.add
    # (旧代码 synced.add(cid) 引用未定义名 → 真实建档必 NameError → ok 到不了 True → 白名单不落 → 才是重复建两条的真根因)
    return True


def handle_aihr_event(record_id, operator_open_id=None):
    """⚡事件驱动:AI-HR 某条记录变更 → 若是新约面则**立即**秒建进度表记录。
    operator_open_id=谁点的约面(飞书事件直接给,当一面面试官)。"""
    full = fs.get_record(cfg.AIHR_APP, cfg.AIHR_TABLE, record_id, automatic=True)
    if not full or _cell(full["fields"].get("HR评估")) != "约面":
        return
    _sync_one(full, _prog_options(), interviewer=operator_open_id)


def rule1_sync():
    """规则①(轮询兜底):事件驱动是主路径(handle_aihr_event);这里定期 search 约面补漏,
    防事件偶发丢失。search 只取约面不扫全表,只靠 state.synced 防重复。"""
    state = _load_state()
    synced = set(state["synced"])
    opts = _prog_options()
    records = fs.search_records(cfg.AIHR_APP, cfg.AIHR_TABLE, "HR评估", "is", "约面", limit=10000)
    done = 0
    for r in records:
        cid = _cell(r["fields"].get("AIHR候选人ID")) or r["record_id"]
        if cid in synced:
            continue
        full = fs.get_record(cfg.AIHR_APP, cfg.AIHR_TABLE, r["record_id"], automatic=True)
        if full and _sync_one(full, opts):
            done += 1
        if cfg.MAX_PER_CYCLE and done >= cfg.MAX_PER_CYCLE:
            break
    return done  # synced 由 _sync_one 抢占锁内更新,这里不再覆盖


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
        "round": round_name,
        "evalDoc": _cell(f.get("面试评价")),  # 面评链接:建日程时放进日程描述给面试官
    }
    if not _is_phone(contact):
        payload["wxid"] = contact  # 微信号加友,等中台支持
    requests.post(f"{cfg.REACH_URL}/reach", json=payload, timeout=30)


def rule2_reach():
    """规则②(高频快循环)：进度表【AI触达】勾选 → 前置自检必填信息 → 齐了才调触达服务加企微好友。
    提速:search 只取勾了AI触达的记录(不扫全表);取消勾选靠 reached 差集检测。
    缺信息:不触达,群里@点勾选的人报缺什么。重触达:联系方式人工校正后自动重发/取消再勾重发。
    幂等:reached 记 {记录ID: 触达时的联系方式}。"""
    state = _load_state()
    reached = state.get("reached")
    if isinstance(reached, list):
        reached = {rid: "" for rid in reached}
    state["reached"] = reached = reached or {}
    reminded = state.setdefault("reminded", {})
    invited = state.setdefault("round_invited", {})
    known_time = state.setdefault("known_time", {})
    # search 只取勾了 AI触达 的记录(复选框 is true)
    rows = fs.search_records(cfg.PROG_APP, cfg.PROG_TABLE, "AI触达", "is", "true")
    checked_ids = {r["record_id"] for r in rows}
    for rid in [k for k in list(reached) if k not in checked_ids]:
        reached.pop(rid, None)  # 取消勾选=撤销授权;再勾会重新触达
    done = 0
    for r in rows:
        f = r["fields"]
        rid = r["record_id"]
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
                at_rec = fs.get_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, automatic=True) or r
                msg = (f"{_at_of(at_rec, f)}候选人【{name or rid}】勾了AI触达，但还缺：{('、'.join(missing))}。"
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


def _sync_handover(rid, cur, name, known):
    """调触达服务 /handover 同步单条转人工状态,处理 201/无任务;成功更新 known + 触达状态。"""
    if cfg.DRY_RUN:
        log.info(f"[DRY] 规则⑤→转人工: {name} handover={cur}")
        known[rid] = cur
        return
    try:
        resp = requests.post(f"{cfg.REACH_URL}/handover",
                             json={"dataId": rid, "handover": cur}, timeout=15)
        j = resp.json() if resp.ok else {}  # NestJS POST 默认 201,只认 200 会把成功当失败
        if j.get("ok"):
            log.info(f"✅ 规则⑤转人工同步: {name} → {'人工接管' if cur else '恢复AI'} ({j.get('taskId')})")
            known[rid] = cur
            if cur:
                try:
                    fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"触达状态": "转人工中"})
                except Exception:
                    pass
        elif j.get("msg", "").startswith("dataId"):
            log.info(f"  规则⑤: {name} 无触达任务,只记状态 handover={cur}")
            known[rid] = cur
        else:
            log.warning(f"  规则⑤ {name} 同步失败({resp.status_code}): {resp.text[:120]},下轮重试")
    except Exception as e:
        log.warning(f"  规则⑤ {name} 调触达服务失败: {e},下轮重试")


def rule5_handover():
    """规则⑤(高频快循环·转人工)：进度表【转人工】勾选状态变化 → 同步给触达服务。
    提速:search 只取勾了转人工的记录;取消勾选靠 known 差集检测。true=AI停;取消=恢复AI。
    幂等:known 记每条上次状态,只变化才调,失败不记、下轮重试。"""
    state = _load_state()
    known = state.setdefault("handover", {})
    rows = fs.search_records(cfg.PROG_APP, cfg.PROG_TABLE, "转人工", "is", "true")
    cur_true = {r["record_id"] for r in rows}
    done = 0
    for r in rows:  # 新勾上的
        rid = r["record_id"]
        if known.get(rid) is True:
            continue
        _sync_handover(rid, True, _cell(r["fields"].get("姓名")), known)
        if known.get(rid) is True:
            done += 1
    for rid in [k for k, v in list(known.items()) if v is True and k not in cur_true]:  # 取消勾选的
        _sync_handover(rid, False, rid, known)
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
            log.info(f"[DRY] 规则⑧改期: {name} {rnd} {old}→{cur}")
        else:
            try:
                # 优先直推新时间(已绑定会话秒到);还没聊过绑不上会话 → 退回重触达
                resp = requests.post(f"{cfg.REACH_URL}/notify",
                                     json={"dataId": rid, "phone": _cell(f.get("联系方式")).strip(),
                                           "interviewTime": str(cur), "round": rnd}, timeout=30)
                j = resp.json() if resp.ok else {}
                if j.get("ok"):
                    way = "已直接推送给候选人确认"
                else:
                    _invite(rid, f, rnd)
                    way = "候选人还没会话,已走重触达通知"
                fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"触达状态": "已发邀约"})
                _remind(f"候选人【{name}】的{rnd}时间已改,{way}。")
                log.info(f"规则⑧ {name} {rnd}改期通知({way})")
            except Exception as e:
                log.warning(f"  {name} 改期通知失败: {e}")
                continue
        known_time[rid] = cur
        done += 1
    _save_state(state)
    return done


def rule9_interview_eval(records):
    """规则⑨(面后AI面评,玄玄拍板的流程)：HR 往【逐字稿链接】贴面试逐字稿文档链接 →
    读逐字稿 → 用知识库面评Prompt(壳=固定输出结构+分数规则,实时读)+该岗位标准包打分 →
    写进该候选人面评文档「三、面试评价」的「一面：」下面 → 群里@一面面试官补人工结论。
    幂等:state.evaled 记 {rid: 链接},链接没变不重评;换链接(如更正)会重评。
    ⭐存量铁律(玄玄定,两次教训):新规则上线,表里已有的数据一律视为已处理,只管之后新增/变化的。"""
    state = _load_state()
    evaled = state.setdefault("evaled", {})
    if not state.get("evaled_seeded"):
        # 首次运行:把所有已有逐字稿链接的行全部登记为已处理,零动作(存量是以前人工处理完的)
        n = 0
        for r in records:
            link = _cell(r["fields"].get("逐字稿链接")).strip()
            if link:
                evaled[r["record_id"]] = link
                n += 1
        state["evaled_seeded"] = True
        _save_state(state)
        log.info(f"规则⑨首启:预置存量逐字稿 {n} 条为已处理(不动作),只管之后新增")
        return 0
    done = 0
    for r in records:
        rid = r["record_id"]
        f = r["fields"]
        link = _cell(f.get("逐字稿链接")).strip()
        if not link or evaled.get(rid) == link:
            continue
        name, pos = _cell(f.get("姓名")), _cell(f.get("岗位"))
        m = _RE_DOC.search(link)
        if not m:
            if evaled.get(rid) != f"BAD:{link}":
                log.warning(f"规则⑨ {name} 逐字稿链接读不了(要飞书文档链接): {link[:60]}")
                evaled[rid] = f"BAD:{link}"
                _save_state(state)
            continue
        try:
            transcript = _read_transcript(m.group(1))
        except Exception:
            try:  # wiki 链接:先换 obj_token 再读
                transcript = fs.read_doc_content(fs.wiki_obj_token(m.group(1)))
            except Exception as e:
                log.warning(f"规则⑨ {name} 逐字稿读取失败: {e}")
                continue
        if len(transcript.strip()) < 200:
            log.warning(f"规则⑨ {name} 逐字稿内容过短({len(transcript)}字),跳过")
            evaled[rid] = link
            _save_state(state)
            continue
        shell = standards.prompt_shell(fs)
        rubric = standards.rubric_for(fs, pos)
        prompt = (f"{shell}\n【当前岗位配置】\n{rubric or '(无专属配置,按岗位所属类别默认体系)'}\n\n"
                  f"【候选人】{name} 应聘岗位:{pos}\n【一面面试逐字稿】\n{transcript[:30000]}\n\n"
                  # 判断原则/写作风格/条数字数/分数规则一律以上面知识库 prompt 为准,这里不再重复,
                  # 只加一个最小 JSON 外壳(渲染飞书块需要结构化),字段严格对应其「八、固定输出结构」。
                  "按上面的规范评这场一面。**只输出 JSON**(不要任何其它文字),字段严格对应「八、固定输出结构」:\n"
                  '{"结论":"","一句话总结":"","优点":[],"缺点":[],"基本信息":"","求职进展":"",'
                  '"求职期望":"","工作情况":"","个人情况":"","总分":0,'
                  '"分项打分":[{"维度":"","得分":0,"满分":0,"简评":""}],'
                  '"补充判断":"","下一轮建议":[]}')
        if cfg.DRY_RUN:
            log.info(f"[DRY] 规则⑨面后面评: {name}")
            evaled[rid] = link
            continue
        try:
            text = doubao.parse_json(doubao.ask(prompt))
        except Exception as e:
            log.warning(f"规则⑨ {name} 打分失败: {e}")
            continue
        # 面评文档:字段里是链接就直接写;是深澜文本/为空就现建一份再写
        mp = _cell(f.get("面试评价"))
        dm = _RE_DOC.search(mp)
        try:
            if dm:
                did = dm.group(1)
            else:
                att = f.get("简历")
                data = fs.download_attachment(att[0]) if isinstance(att, list) and att else None
                fname = att[0].get("name", "简历.pdf") if isinstance(att, list) and att else "简历.pdf"
                fr = {}
                if data:
                    try:
                        fr, _ = resume.extract_fields(data, fname)  # 现建文档时重解析简历,初筛才有真材料
                    except Exception:
                        pass
                url = mianping.generate(fs, name, pos, fr, data, fname)
                fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"面试评价": url})
                did = _RE_DOC.search(url).group(1)
            where = mianping.insert_round_eval(fs, did, "一面", text)
            log.info(f"✅ 规则⑨ {name} 一面AI面评已写入面评文档({where})，未发群(反馈形式待定)")
            evaled[rid] = link
            done += 1
        except Exception as e:
            log.warning(f"规则⑨ {name} 写入面评失败: {e}")
            continue
    _save_state(state)
    return done


import re as _re_mod
_RE_DOC = _re_mod.compile(r"/(?:docx|docs|wiki)/([A-Za-z0-9]{20,})")


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


# ============ 规则⑩ 逐字稿自动收集（全自动·用户身份，2026-07-23）============
# 背景：app 身份读不了人拥有的妙记（飞书把 app 当"非组织成员"，组织内可见只对人开放）。
#       用【用户身份】搜+读真实面试的「文字记录」文档（已用句子局长用户 token 在真实逐字稿上实测通）。
# 链路：面试结束 → 妙记生成「文字记录:线上面试-{岗位}-{姓名}」→ 本规则用户身份按标题搜到 →
#       把文档链接写进【逐字稿链接】→ 触发已有规则⑨自动出面评。全程零人工。
# 已接进 main.py cycle_slow（在规则⑨之前跑）。用户 scope+redirect 已开、服务账号(玄玄HR账号)已OAuth、
# token 落 data/user_token.json 自动续。seeding 铁律：首启把"已发生过的面试"全视为已处理，绝不回填历史（防刷屏）。
_fu = None
_TRANSCRIPT_MIN_AGE = 30 * 60      # 面试结束多久后才去搜（妙记生成+索引要时间）
_TRANSCRIPT_GIVEUP = 7 * 86400     # 面试过去这么久还没搜到就放弃（没开录制/无妙记）


def _read_transcript(doc_id):
    """读逐字稿正文：优先用户身份(能读妙记「文字记录」文档,app 读不了)，
    未授权/失败回退应用身份(能读 app 自建或被分享的文档)。规则⑨/⑩共用。"""
    global _fu
    try:
        if _fu is None:
            from feishu_user import FeishuUser
            _fu = FeishuUser()
        if _fu.authorized():
            return _fu.read_doc(doc_id)
    except Exception as e:
        log.warning(f"用户身份读逐字稿失败,回退app: {e}")
    return fs.read_doc_content(doc_id)


def _interview_ms(f):
    """读【一面时间】为毫秒时间戳（字段可能是数字/字符串），拿不到返回 None。"""
    v = f.get("一面时间")
    if isinstance(v, (int, float)):
        return int(v)
    s = _cell(v).strip()
    return int(s) if s.isdigit() else None


def rule10_collect_transcript(records):
    """逐字稿自动收集（用户身份）。见本节顶部说明。"""
    import time as _t
    global _fu
    if _fu is None:
        from feishu_user import FeishuUser
        _fu = FeishuUser()
    if not _fu.authorized():
        log.warning("规则⑩：用户身份未授权，跳过（先跑 oauth_bootstrap.py）")
        return 0
    now_ms = int(_t.time() * 1000)
    state = _load_state()
    done = state.setdefault("transcript", {})   # {rid: 写入的链接}
    # —— seeding：首启把"已发生过的面试/已有逐字稿"全登记为已处理，只管之后新完成的面试 ——
    if not state.get("transcript_seeded"):
        if not records:
            return 0  # 拉表为空(疑拉表失败)不 seeding,否则漏掉的历史面试下轮会被回填刷屏
        n = 0
        for r in records:
            f = r["fields"]
            past = (_interview_ms(f) or 0) and _interview_ms(f) < now_ms
            if _cell(f.get("逐字稿链接")).strip() or past:
                done[r["record_id"]] = "SEED"
                n += 1
        state["transcript_seeded"] = True
        _save_state(state)
        log.info(f"规则⑩首启：预置存量 {n} 条为已处理（不回填历史），只管之后新完成的面试")
        return 0
    n = 0
    for r in records:
        rid, f = r["record_id"], r["fields"]
        if rid in done or _cell(f.get("逐字稿链接")).strip():
            continue
        name = _cell(f.get("姓名"))
        t_ms = _interview_ms(f)
        if not name or not t_ms:
            continue
        age = now_ms - t_ms
        if age < _TRANSCRIPT_MIN_AGE * 1000:
            continue                              # 面试还没结束/刚结束，等妙记生成
        if age > _TRANSCRIPT_GIVEUP * 1000:
            done[rid] = "GIVEUP"; _save_state(state)
            log.info(f"规则⑩ {name}：面试过去 >{_TRANSCRIPT_GIVEUP//86400} 天仍无文字记录，放弃（未开录制?）")
            continue
        try:
            hit = _fu.find_transcript(name, _cell(f.get("岗位")), t_ms)
        except Exception as e:
            log.warning(f"规则⑩ {name} 搜文字记录失败（用户 token?）: {e}")
            continue
        if not hit:
            continue                              # 还没搜到/多命中放弃，下轮再试（不标 done）
        _title, _tok, url = hit
        if cfg.DRY_RUN:
            log.info(f"[DRY] 规则⑩ {name} → 找到文字记录 {_title}，将写【逐字稿链接】{url}（DRY 不落 state）")
            continue
        try:
            fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"逐字稿链接": url})
            done[rid] = url; _save_state(state); n += 1
            log.info(f"✅ 规则⑩ {name} 逐字稿链接已自动填入（{_title}）→ 规则⑨将出面评")
        except Exception as e:
            log.warning(f"规则⑩ {name} 写【逐字稿链接】失败: {e}")
    return n
