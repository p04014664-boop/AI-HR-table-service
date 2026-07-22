"""飞书长连接事件监听:AI-HR 表记录变更 → HR评估变成约面就【立即】秒建进度表记录。
事件驱动是约面同步的主路径(秒级);轮询(rule1_sync)作兜底,防事件偶发丢失。"""
import threading
import logging
import requests
import lark_oapi as lark
from config import cfg
from feishu import Feishu
import rules

log = logging.getLogger("events")
_fs = Feishu()


def _ensure_subscribed():
    """确保应用已订阅 AI-HR 表的文档事件(幂等,重启后也保证订阅在)。"""
    try:
        r = requests.post(f"https://open.feishu.cn/open-apis/drive/v1/files/{cfg.AIHR_APP}/subscribe",
                          headers=_fs._h(), params={"file_type": "bitable"}, timeout=15).json()
        log.info(f"订阅 AI-HR 表事件: code={r.get('code')} {r.get('msg', '')}")
    except Exception as e:
        log.warning(f"订阅 AI-HR 表异常(可能已订阅,不影响): {e}")


def _on_change(data):
    """收到记录变更 → 只认 AI-HR 表 → 逐条交给 handle_aihr_event(约面才处理)。
    operator_id = 谁点的约面,直接当一面面试官。"""
    import time
    log.info(f"⚡事件到达 t={time.time():.2f}")
    try:
        ev = data.event
        if ev.file_token != cfg.AIHR_APP:
            return
        operator = ev.operator_id.open_id if ev.operator_id else None
        for action in (ev.action_list or []):
            if action.record_id:
                rules.handle_aihr_event(action.record_id, operator)
    except Exception as e:
        log.error(f"事件处理出错: {e}")


def start():
    """启动长连接监听(后台线程,daemon)。SDK 自带断线重连。"""
    _ensure_subscribed()
    handler = (lark.EventDispatcherHandler.builder("", "")
               .register_p2_drive_file_bitable_record_changed_v1(_on_change).build())
    client = lark.ws.Client(cfg.FEISHU_APP_ID, cfg.FEISHU_APP_SECRET,
                            event_handler=handler, log_level=lark.LogLevel.WARNING)
    threading.Thread(target=client.start, daemon=True).start()
    log.info("⚡ AI-HR 表事件长连接已启动(点约面→秒建进度表)")
