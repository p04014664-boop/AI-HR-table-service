"""对外 HTTP 接口(触达服务 → 表格服务,按 docs/触达服务接口文档.md 约定)。
分工铁律:触达服务不碰表格,回填进度/标记转人工都调这里;本服务不碰 Mongo/不对外发消息。
- POST /progress/backfill  回填进度/备忘录 {dataId?, phone?, event, note, status?, interviewTime?, meetingLink?}
- POST /progress/handover  转人工 {dataId?, phone?, reason, reasonText, candidateReply?}
- GET  /health
"""
import json
import logging
import re
import threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from config import cfg
from feishu import Feishu

log = logging.getLogger("api")
fs = Feishu()
_CST = timezone(timedelta(hours=8))


def _cell(v):
    if isinstance(v, list):
        return " ".join((x.get("text") or x.get("name", "")) if isinstance(x, dict) else str(x) for x in v)
    if isinstance(v, dict):
        return v.get("text") or v.get("link") or ""
    return v if isinstance(v, str) else ""


def _locate(data_id, phone):
    """按 dataId 定位进度表记录,缺/找不到再按手机号(联系方式)兜底。返回 (record_id, fields) 或 (None, None)。"""
    records = fs.list_records(cfg.PROG_APP, cfg.PROG_TABLE)
    if data_id:
        for r in records:
            if r["record_id"] == data_id:
                return r["record_id"], r["fields"]
    if phone:
        p = re.sub(r"\D", "", str(phone))[-11:]
        for r in records:
            if p and p in re.sub(r"\D", "", _cell(r["fields"].get("联系方式"))):
                return r["record_id"], r["fields"]
    return None, None


def _parse_time_ms(s):
    """'2026-07-21 14:00' / 毫秒时间戳 → 毫秒时间戳(int)。解析不了返回 None。"""
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)) or (isinstance(s, str) and s.isdigit()):
        v = int(s)
        return v if v > 10**12 else v * 1000  # 秒级也兼容
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(str(s).strip(), fmt).replace(tzinfo=_CST).timestamp() * 1000)
        except ValueError:
            continue
    return None


def _append_memo(old, line):
    stamp = datetime.now(_CST).strftime("%m-%d %H:%M")
    entry = f"[{stamp} 触达] {line}"
    return f"{old}\n{entry}" if old else entry


def _backfill(body):
    rid, f = _locate(body.get("dataId"), body.get("phone"))
    if not rid:
        return {"ok": False, "msg": "dataId/phone 都定位不到进度表记录"}
    note = (body.get("note") or "").strip() or (body.get("event") or "")
    if body.get("meetingLink"):
        note += f" 会议链接:{body['meetingLink']}"
    upd = {"备忘录": _append_memo(_cell(f.get("备忘录")), note)}
    ts = _parse_time_ms(body.get("interviewTime"))
    if ts:
        upd["一面时间"] = ts
    if cfg.DRY_RUN:
        log.info(f"[DRY] backfill {rid}: {json.dumps(upd, ensure_ascii=False)[:150]}")
    else:
        fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, upd)
    log.info(f"✅ backfill {_cell(f.get('姓名')) or rid}: {body.get('event', '')} {note[:60]}")
    return {"ok": True, "dataId": rid}


def _handover(body):
    rid, f = _locate(body.get("dataId"), body.get("phone"))
    if not rid:
        return {"ok": False, "msg": "dataId/phone 都定位不到进度表记录"}
    reason = body.get("reason") or ""
    line = f"【转人工|{reason}】{body.get('reasonText') or ''}"
    if body.get("candidateReply"):
        line += f" 候选人原话:「{body['candidateReply']}」"
    upd = {"转人工": True, "备忘录": _append_memo(_cell(f.get("备忘录")), line)}
    if cfg.DRY_RUN:
        log.info(f"[DRY] handover {rid}: {line}")
    else:
        fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, upd)
    log.info(f"✅ handover {_cell(f.get('姓名')) or rid}: {reason} {body.get('reasonText', '')[:60]}")
    return {"ok": True, "dataId": rid}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 静音默认访问日志,统一走 logging
        pass

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health"):
            return self._send(200, {"ok": True, "service": "aihr-table", "dry_run": cfg.DRY_RUN})
        return self._send(404, {"ok": False, "msg": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"ok": False, "msg": "body 不是合法 JSON"})
        try:
            if self.path.rstrip("/") == "/progress/backfill":
                return self._send(200, _backfill(body))
            if self.path.rstrip("/") == "/progress/handover":
                return self._send(200, _handover(body))
            return self._send(404, {"ok": False, "msg": "not found"})
        except Exception as e:
            log.error(f"接口异常 {self.path}: {e}")
            return self._send(500, {"ok": False, "msg": str(e)})


def start():
    """后台线程起 HTTP 服务(不阻塞主轮询)。"""
    srv = ThreadingHTTPServer(("0.0.0.0", cfg.API_PORT), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    log.info(f"HTTP 接口已启动 :{cfg.API_PORT} (/progress/backfill /progress/handover /health)")
    return srv
