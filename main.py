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


def cycle():
    # 每轮只拉一次进度表,7条规则共用(2000+条×每规则各拉一遍会把API打爆)
    try:
        prog = rules.fetch_progress()
    except Exception as e:
        log.error(f"拉进度表失败,本轮跳过: {e}")
        return
    steps = [
        ("规则①约面同步", lambda: rules.rule1_sync(prog)),
        ("规则②触达", lambda: rules.rule2_reach(prog)),
        ("链路B手动简历", lambda: rules.rule3_manual_resume(prog)),
        ("规则④岗位校正联动", lambda: rules.rule4_position_correction(prog)),
        ("规则⑤转人工同步", lambda: rules.rule5_handover(prog)),
        ("规则⑥转人工超时提醒", lambda: rules.rule6_handover_overdue(prog)),
        ("规则⑦轮次推进", lambda: rules.rule7_rounds(prog)),
        ("规则⑧改期联动", lambda: rules.rule8_time_change(prog)),
    ]
    for label, fn in steps:
        try:
            n = fn()
            if n:
                log.info(f"{label}：本轮处理 {n} 条")
        except Exception as e:
            log.error(f"{label}出错: {e}")


def main():
    once = "--once" in sys.argv
    log.info(f"===【句子秒聘·表格管理服务】启动 · DRY_RUN={cfg.DRY_RUN} · "
             f"进度表={cfg.PROG_APP}/{cfg.PROG_TABLE} · 轮询{cfg.POLL_INTERVAL}s ===")
    api.start()  # 触达服务回调接口(/progress/backfill /progress/handover)
    while True:
        cycle()
        if once:
            break
        time.sleep(cfg.POLL_INTERVAL)


if __name__ == "__main__":
    main()
