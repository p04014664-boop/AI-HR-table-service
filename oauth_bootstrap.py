"""一次性：让一个【HR/服务账号】给服务做 OAuth 授权，拿到用户 token 落盘到 data/user_token.json。
之后服务用它搜+读妙记文字记录（规则⑩），token 会自动刷新，不用再管。
前提（玄玄在飞书开放平台做）：给 FEISHU_USER_APP_ID 那个 app 开【用户身份】scope
    （docs:document.content:read + search:docs:read + offline_access）并配好 FEISHU_OAUTH_REDIRECT。

用法（在服务器 /opt/aihr-table-service，带 .env）：
    python oauth_bootstrap.py
    → 打印一个授权链接；用【服务账号】在浏览器打开、登录、同意授权
    → 浏览器跳到 redirect 地址、URL 里带 ?code=XXXX
    → 把 code 粘回终端回车 → 令牌落盘，完成
"""
import sys
from feishu_user import FeishuUser


def main():
    fu = FeishuUser()
    if fu.authorized():
        print("已授权过（data/user_token.json 存在 refresh_token）。要重授权就删掉该文件再跑。")
        try:
            fu.token(); print("当前 token 可正常刷新 ✅")
        except Exception as e:
            print(f"但刷新失败，需重授权：{e}")
        return
    print("① 用【服务账号】在浏览器打开下面的链接，登录并同意授权：\n")
    print("   " + fu.authorize_url() + "\n")
    print("② 授权后浏览器会跳转，地址栏 URL 里有 ?code=XXXX（或 &code=XXXX）。")
    code = input("③ 把 code 粘到这里回车：").strip()
    if "code=" in code:  # 允许直接粘整条回调 URL
        code = code.split("code=")[1].split("&")[0]
    try:
        fu.exchange_code(code)
        print("\n✅ 授权成功，令牌已落盘 data/user_token.json。规则⑩可用了。")
    except Exception as e:
        print(f"\n❌ 换 token 失败：{e}\n检查：scope 是否开全、redirect 是否与开放平台一致、code 是否过期（几分钟内有效）。")
        sys.exit(1)


if __name__ == "__main__":
    main()
