"""一次性清理:删掉 synced.add bug 刷出来的于兆涵重复记录 + 白名单预置源头防重刷。
默认 DRY RUN(只统计不删);加 --go 才真删。用服务身份(cli_aad38),在容器镜像里跑。"""
import sys, os, json, time, requests
from config import cfg
from feishu import Feishu, BASE

GO = "--go" in sys.argv
NAME = "于兆涵"
fs = Feishu()

def cell(v):
    if isinstance(v, str): return v
    if isinstance(v, list) and v and isinstance(v[0], dict): return v[0].get("text", "")
    return v or ""

# ── 1. AI-HR 源头 ──
src = fs.search_records(cfg.AIHR_APP, cfg.AIHR_TABLE, "姓名", "is", NAME, limit=100)
print(f"=== AI-HR 表 {NAME} 源头记录: {len(src)} 条 ===")
src_cids = []
for r in src:
    f = r["fields"]
    cid = cell(f.get("AIHR候选人ID")) or r["record_id"]
    src_cids.append(cid)
    print(f"  record={r['record_id']} HR评估={cell(f.get('HR评估'))} cid={cid}")

# ── 2. 进度表 于兆涵(仅备忘录=AI约面同步 才删,保护真候选人) ──
rows = fs.search_records(cfg.PROG_APP, cfg.PROG_TABLE, "姓名", "is", NAME, limit=100000)
targets, others = [], []
for r in rows:
    memo = cell(r["fields"].get("备忘录"))
    (targets if "AI约面同步" in memo else others).append(r)
print(f"\n=== 进度表 {NAME}: 共 {len(rows)} 条 | 备忘录=AI约面同步(将删)={len(targets)} | 其他备忘录(保留)={len(others)} ===")
if others[:3]:
    print("  保留样例:", [(r['record_id'], cell(r['fields'].get('备忘录'))) for r in others[:3]])

ids = [r["record_id"] for r in targets]
if not GO:
    print(f"\n[DRY RUN] 将删除 {len(ids)} 条于兆涵重复记录。确认无误后加 --go 执行。")
    sys.exit(0)

# ── 真删(批量,每批 500) ──
deleted = 0
for i in range(0, len(ids), 500):
    chunk = ids[i:i+500]
    r = requests.post(
        f"{BASE}/bitable/v1/apps/{cfg.PROG_APP}/tables/{cfg.PROG_TABLE}/records/batch_delete",
        headers=fs._h(), json={"records": chunk}, timeout=120,
    ).json()
    if r.get("code") == 0:
        deleted += len(chunk)
        print(f"  已删 {deleted}/{len(ids)}")
    else:
        print(f"  删除失败: {r.get('code')} {r.get('msg')}"); break
    time.sleep(0.5)
print(f"\n✅ 进度表已删除 {deleted} 条于兆涵重复记录")

# ── 3. 白名单预置源头 cid,防重启后再刷 ──
sp = cfg.STATE_FILE
try:
    st = json.load(open(sp)) if os.path.exists(sp) else {"synced": [], "reached": {}}
except Exception:
    st = {"synced": [], "reached": {}}
s = set(st.get("synced", []))
before = len(s)
s.update(src_cids)
st["synced"] = list(s)
json.dump(st, open(sp, "w"), ensure_ascii=False)
print(f"✅ 白名单已加入源头 cid {src_cids}(synced {before}→{len(s)}),重启后不会再刷")
