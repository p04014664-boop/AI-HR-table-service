"""入口：定时轮询跑规则①②。`python main.py --once` 只跑一轮(演练用)。"""
import sys
import time
import logging
from config import cfg
import rules
import api

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("main")


def cycle_fast():
    """高频(每 POLL_INTERVAL 秒):表格即时动作——约面同步/触达/转人工,各自 search 精准查,不扫全表。"""
    for label, fn in [("规则②触达", rules.rule2_reach),
                      ("规则⑤转人工同步", rules.rule5_handover)]:
        try:
            n = fn()
            if n:
                log.info(f"{label}：本轮处理 {n} 条")
        except Exception as e:
            log.error(f"{label}出错: {e}")


def cycle_slow():
    """低频(每 SLOW_INTERVAL 秒):手动简历/岗位校正/改期/面后面评——拉进度表全表遍历,不需要秒级。"""
    try:
        prog = rules.fetch_progress()
    except Exception as e:
        log.error(f"拉进度表失败,慢循环跳过: {e}")
        return
    # rule1 约面同步:主路径是事件驱动(events.py),这里轮询兜底补漏
    try:
        n1 = rules.rule1_sync()
        if n1:
            log.info(f"规则①约面同步(轮询兜底)：本轮补 {n1} 条")
    except Exception as e:
        log.error(f"规则①兜底出错: {e}")
    for label, fn in [("链路B手动简历", lambda: rules.rule3_manual_resume(prog)),
                      ("规则④岗位校正联动", lambda: rules.rule4_position_correction(prog)),
                      ("规则⑧改期联动", lambda: rules.rule8_time_change(prog)),
                      ("规则⑨面后面评", lambda: rules.rule9_interview_eval(prog))]:
        try:
            n = fn()
            if n:
                log.info(f"{label}：本轮处理 {n} 条")
        except Exception as e:
            log.error(f"{label}出错: {e}")


def main():
    once = "--once" in sys.argv
    log.info(f"===【句子秒聘·表格管理服务】启动 · DRY_RUN={cfg.DRY_RUN} · "
             f"快循环{cfg.POLL_INTERVAL}s(约面/触达/转人工) · 慢循环{cfg.SLOW_INTERVAL}s(手动简历/校正/改期/面评) ===")
    api.start()  # HTTP接口:触达回填/知识库 + ⚡/table-event(AI-HR自动化约面秒建,主路径);rule1轮询兜底
    import time as _t
    last_slow = 0
    while True:
        cycle_fast()
        if _t.time() - last_slow >= cfg.SLOW_INTERVAL:
            cycle_slow()
            last_slow = _t.time()
        if once:
            break
        time.sleep(cfg.POLL_INTERVAL)


if __name__ == "__main__":
    main()
