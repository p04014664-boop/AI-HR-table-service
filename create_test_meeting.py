"""app 身份建一场带 VC + 自动录制的会议(模拟面试日程),邀请玄玄,打印加入链接。
验证:app 建的会议,妙记归不归 app、app 能不能读逐字稿。"""
import os, time, requests
from urllib.parse import quote
BASE = "https://open.feishu.cn/open-apis"
XUAN = "ou_412fbf5295db5c8eed270cadcbed1122"  # 张玄玄

tok = requests.post(f"{BASE}/auth/v3/tenant_access_token/internal",
    json={"app_id": os.environ["FEISHU_APP_ID"], "app_secret": os.environ["FEISHU_APP_SECRET"]},
    timeout=20).json()["tenant_access_token"]
H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

cal = requests.post(f"{BASE}/calendar/v4/calendars/primary", headers=H, timeout=20).json()
print("primary calendar code=", cal.get("code"), cal.get("msg") or "")
calendar_id = ((cal.get("data") or {}).get("calendars") or [{}])[0].get("calendar", {}).get("calendar_id")
if not calendar_id:
    print("❌ 没取到应用主日历(可能缺 calendar 权限):", cal); raise SystemExit
cal_enc = quote(calendar_id, safe="")

start = int(time.time()) + 90        # 1.5 分钟后开始
end = start + 30 * 60
r = requests.post(f"{BASE}/calendar/v4/calendars/{cal_enc}/events", headers=H, json={
    "summary": "AI-HR妙记归属测试-app建",
    "start_time": {"timestamp": str(start), "timezone": "Asia/Shanghai"},
    "end_time": {"timestamp": str(end), "timezone": "Asia/Shanghai"},
    "vchat": {"vc_type": "vc", "meeting_settings": {"auto_record": True, "allow_attendees_start": True}},
    "need_notification": True,
}, timeout=20).json()
print("建日程 code=", r.get("code"), r.get("msg") or "")
ev = (r.get("data") or {}).get("event") or {}
eid = ev.get("event_id")
murl = (ev.get("vchat") or {}).get("meeting_url", "")
print("event_id=", eid)
print("会议链接=", murl or "(空,稍等回查)")

# 邀请玄玄进来好加入
if eid:
    ra = requests.post(f"{BASE}/calendar/v4/calendars/{cal_enc}/events/{eid}/attendees", headers=H,
        json={"attendees": [{"type": "user", "user_id": XUAN}], "need_notification": True}, timeout=20).json()
    print("邀请玄玄 code=", ra.get("code"), ra.get("msg") or "")
if not murl and eid:
    time.sleep(2)
    g = requests.get(f"{BASE}/calendar/v4/calendars/{cal_enc}/events/{eid}", headers=H, timeout=20).json()
    murl = ((g.get("data") or {}).get("event") or {}).get("vchat", {}).get("meeting_url", "")
    print("回查会议链接=", murl or "(还是空)")
print("\n▶ 玄玄:从飞书日历找到「AI-HR妙记归属测试-app建」,或点上面链接,进会议、说两句、等自动录制、结束会议。")
