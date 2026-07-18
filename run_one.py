"""受控单人真跑：只处理指定姓名的一个候选人，写进真进度表。用于受控测试，绝不碰其他人。
用法：PROG_*指向真表 + 应用凭据后， python run_one.py 姜欣妍
"""
import sys
import json
import logging
from config import cfg
from feishu import Feishu
import doubao
import resume
from rules import _cell

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("run_one")
fs = Feishu()


def run(name):
    log.info(f"=== 受控单人真跑：只处理【{name}】，进度表={cfg.PROG_APP}/{cfg.PROG_TABLE} ===")

    # 1) 只清掉真表里"这个人"的旧AI同步记录（避免重复），别人不动
    prog = fs.list_records(cfg.PROG_APP, cfg.PROG_TABLE)
    old = [r for r in prog if _cell(r["fields"].get("姓名")) == name
           and "AI约面同步" in _cell(r["fields"].get("备忘录"))]
    for r in old:
        fs.delete_record(cfg.PROG_APP, cfg.PROG_TABLE, r["record_id"])
        log.info(f"清掉 {name} 的旧同步记录 {r['record_id']}")

    # 2) 读 AI-HR 里这个人
    ai = fs.list_records(cfg.AIHR_APP, cfg.AIHR_TABLE, automatic_fields=True)
    hit = [r for r in ai if _cell(r["fields"].get("姓名")) == name]
    if not hit:
        log.error(f"AI-HR 里没找到 {name}"); return
    r = hit[0]
    f = r["fields"]
    hrp = _cell(f.get("HR评估"))
    log.info(f"{name} 当前 HR评估 = {hrp!r}")
    if hrp != "约面":
        log.warning(f"{name} 不是约面（是{hrp!r}），规则①不该搬。要测请先在 AI-HR 点约面。")
        return

    # 3) 全套规则①
    positions = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位")
    categories = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位大类")
    channels = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "渠道")
    screen = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "简历筛选")

    boss = _cell(f.get("岗位")); src = _cell(f.get("简历来源")); phone = _cell(f.get("联系方式"))
    concl = _cell(f.get("AI HR结论")); mianping = _cell(f.get("面评"))

    j = doubao.classify_position(boss, src, positions, categories, channels)
    log.info(f"判岗位: {boss} → {j.get('岗位')} / {j.get('大类')} / 渠道 {j.get('渠道')}")

    shen = ""
    att = f.get("简历") if isinstance(f.get("简历"), list) else None
    if att:
        data = fs.download_media(att[0]["file_token"])
        fields, way = resume.extract_fields(data, att[0].get("name", ""))
        shen = fields.get("是否应届生", "")
        if not phone:
            phone = fields.get("手机号", "")
        log.info(f"简历解析({way}): 身份={shen} 手机={phone}")

    interviewer = (r.get("last_modified_by") or {}).get("id")

    rec = {"姓名": name, "备忘录": "AI约面同步"}
    if j.get("岗位") in positions: rec["岗位"] = j["岗位"]
    if j.get("大类") in categories: rec["岗位大类"] = j["大类"]
    if j.get("渠道") in channels: rec["渠道"] = j["渠道"]
    if phone: rec["联系方式"] = phone
    if "通过" in concl and "通过" in screen: rec["简历筛选"] = "通过"
    if mianping: rec["面试评价"] = mianping
    if shen in ("应届生", "非应届生"): rec["候选人身份"] = shen
    if interviewer: rec["一面面试官"] = [{"id": interviewer}]

    rid = fs.create_record(cfg.PROG_APP, cfg.PROG_TABLE, rec)
    log.info(f"✅ 已写入真进度表: {name} ({rid})")

    # 4) 搬简历附件
    if att:
        try:
            tok = fs.upload_media(att[0].get("name", "简历.pdf"),
                                  fs.download_media(att[0]["file_token"]), cfg.PROG_APP)
            fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, rid, {"简历": [{"file_token": tok}]})
            log.info("✅ 简历附件已搬进真表")
        except Exception as e:
            log.warning(f"简历附件搬运失败: {e}")

    log.info("最终记录: " + json.dumps({**rec, "简历": "✓已带附件" if att else "无", "record_id": rid}, ensure_ascii=False))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "姜欣妍")
