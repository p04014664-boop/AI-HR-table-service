"""一次性：给已处理的手动简历记录补判岗位(用改进后的推测岗位方向)，顺便补姓名/手机。"""
import logging
from config import cfg
from feishu import Feishu
import doubao, resume
from rules import _cell
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("rejudge")
fs = Feishu()
positions = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位")
categories = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "岗位大类")
channels = fs.field_options(cfg.PROG_APP, cfg.PROG_TABLE, "渠道")
for r in fs.list_records(cfg.PROG_APP, cfg.PROG_TABLE):
    f = r["fields"]
    if "手动简历" not in _cell(f.get("备忘录")):
        continue
    att = f.get("简历")
    if not (isinstance(att, list) and att):
        continue
    try:
        data = fs.download_attachment(att[0])
        fields, way = resume.extract_fields(data, att[0].get("name", ""))
    except Exception as e:
        log.info(f"下载失败 {e}"); continue
    rec = {}
    if not _cell(f.get("岗位")):
        vint = fields.get("求职意向岗位", "") or fields.get("推测岗位方向", "")
        if vint:
            j = doubao.classify_position(vint, "手动上传", positions, categories, channels)
            if j.get("岗位") in positions: rec["岗位"] = j["岗位"]
            if j.get("大类") in categories: rec["岗位大类"] = j["大类"]
            log.info(f"  推测岗位方向={vint} → {j.get('岗位')}")
    if not _cell(f.get("姓名")) and fields.get("姓名"):
        rec["姓名"] = fields["姓名"]
    if not _cell(f.get("联系方式")) and fields.get("手机号"):
        rec["联系方式"] = fields["手机号"]
    if rec:
        fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, r["record_id"], rec)
        log.info(f"✅ 补上: {_cell(f.get('姓名')) or fields.get('姓名', '?')} → {rec}")
