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
    try:
        n1 = rules.rule1_sync()
        log.info(f"规则①完成：本轮处理 {n1} 个新约面")
    except Exception as e:
        log.error(f"规则①出错: {e}")
    try:
        n2 = rules.rule2_reach()
        log.info(f"规则②完成：本轮触发 {n2} 个触达")
    except Exception as e:
        log.error(f"规则②出错(可能真进度表还没授权给应用): {e}")
    try:
        n3 = rules.rule3_manual_resume()
        if n3:
            log.info(f"链路B完成：手动简历识别 {n3} 份")
    except Exception as e:
        log.error(f"链路B(手动简历)出错: {e}")
    try:
        n4 = rules.rule4_position_correction()
        if n4:
            log.info(f"校正联动完成：{n4} 份面评已随岗位校正更新")
    except Exception as e:
        log.error(f"校正联动出错: {e}")
    try:
        n5 = rules.rule5_handover()
        if n5:
            log.info(f"规则⑤完成：{n5} 条转人工状态已同步触达服务")
    except Exception as e:
        log.error(f"规则⑤(转人工)出错: {e}")


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
