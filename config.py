"""运行时配置：全部从环境变量读，密钥绝不写进代码/仓库。"""
import os


def _bool(v, default=False):
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")


class Config:
    # 飞书应用身份（句子秒聘）—— 上线用这个，绝不用任何人的 CLI/登录
    FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

    # 火山方舟 / 豆包（应用级 key）
    ARK_API_KEY = os.environ.get("ARK_API_KEY", "")
    ARK_MODEL = os.environ.get("ARK_MODEL", "doubao-seed-2-0-lite-260428")

    # AI-HR 来源表（深澜）
    AIHR_APP = os.environ.get("AIHR_APP_TOKEN", "H4NTbtLkia9z3fsO0c7cWDWNnod")
    AIHR_TABLE = os.environ.get("AIHR_TABLE_ID", "tblTSVXwu1onvPMa")

    # 招聘进度表：默认指向【测试表】(句子秒聘已可读写)。
    # 真进度表授权给句子秒聘后，把这两个环境变量改成：
    #   PROG_APP_TOKEN=JUCZbMNaSaoviosYIsjcRKcynKc  PROG_TABLE_ID=tblBedUZDTl2PASn
    PROG_APP = os.environ.get("PROG_APP_TOKEN", "WzXpbCdYgaZDk0s7dSiczy20nnc")
    PROG_TABLE = os.environ.get("PROG_TABLE_ID", "tblVRrAmRPtQsY1L")

    # 触达服务（宏佳）
    REACH_URL = os.environ.get("REACH_SERVICE_URL", "http://ai-hr.juzibot.com")

    # 触达前置校验缺信息时,去这个群@相关人提醒(默认=句子秒聘群)
    REMIND_CHAT_ID = os.environ.get("REMIND_CHAT_ID", "oc_8f33f2eb5afd3efb810ed338d995cf3f")

    # 对外 HTTP 接口端口(触达服务回调 /progress/backfill /progress/handover)
    API_PORT = int(os.environ.get("API_PORT", "8090"))

    POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SEC", "120"))
    # DRY_RUN=true 只识别打日志、不真写表/不真触达。切生产前务必先演练。
    DRY_RUN = _bool(os.environ.get("DRY_RUN", "true"), True)
    # 单轮最多处理几个（0=不限）。演练时可设小一点。
    MAX_PER_CYCLE = int(os.environ.get("MAX_PER_CYCLE", "0"))
    # 幂等状态文件（去重）。容器部署要挂卷持久化，否则重建会丢。
    STATE_FILE = os.environ.get("STATE_FILE", "data/state.json")


cfg = Config()
