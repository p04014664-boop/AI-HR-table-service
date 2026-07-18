"""给手动简历记录生成面评文档(简历嵌原始文件 + AI初筛按标准包)并挂进面试评价。"""
import logging
from config import cfg
from feishu import Feishu
import resume, mianping
from rules import _cell
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("gen")
fs = Feishu()
for r in fs.list_records(cfg.PROG_APP, cfg.PROG_TABLE):
    f = r["fields"]
    if "手动简历" not in _cell(f.get("备忘录")):
        continue
    att = f.get("简历")
    if not (isinstance(att, list) and att):
        continue
    name = _cell(f.get("姓名"))
    data = fs.download_attachment(att[0])
    fields, way = resume.extract_fields(data, att[0].get("name", ""))
    url = mianping.generate(fs, name or fields.get("姓名", ""), _cell(f.get("岗位")),
                            fields, data, att[0].get("name", "简历.pdf"))
    fs.update_record(cfg.PROG_APP, cfg.PROG_TABLE, r["record_id"], {"面试评价": url})
    log.info(f"✅ {name or fields.get('姓名', '?')}（{_cell(f.get('岗位')) or '岗位待定'}）面评: {url}")
