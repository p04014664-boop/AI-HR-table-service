# 句子秒聘 · 表格管理服务

「触达之前」的表格搬运与触发。**用飞书应用身份(句子秒聘)跑，不依赖任何人的 Claude Code / 登录**，可部署上服务器 7×24 自跑。

## 它干什么

- **规则①**：AI-HR 表【HR评估=约面】→ 豆包判真实岗位/大类/渠道 + 读简历补候选人身份和手机号 + 把点约面的人设成一面面试官 + 搬简历附件 → 写进招聘进度表。幂等(按候选人ID去重)。
- **规则②**：进度表【AI触达】复选框勾选 → 调宏佳的触达服务 `/reach` 加企微好友。幂等(按记录ID)。
- **简历解析**：自动识别 PDF(有文字层直接读) / 图片·照片(豆包看图)，抽出姓名/手机/学历/应届等。

## 为什么不依赖 Claude Code

服务是纯 Python，认证只用**应用的 app_id + app_secret**(换 tenant_access_token) + **火山 key**。跑在服务器上，谁的电脑/CC 关了都不影响。Claude Code 只用来写/改代码，不在运行时出现。

## 上线前置（权限）

句子秒聘应用需开通并授权：

| 能力 | scope | 现状 |
|---|---|---|
| 读/建/改记录 | base:record:retrieve/create/update | 已有 |
| 删记录 | base:record:delete | 待开 |
| 上传下载文件(简历附件) | drive:drive | 待开 |
| 读文档(可选,面评取身份) | docx:document:readonly | 按需 |

**外加**：把 **AI-HR 表** 和 **真进度表** 都「添加为文档应用/授权」给句子秒聘，否则 `RolePermNotAllow`。
> 审批链接见台账 / `.env.example`。真进度表授权前，`PROG_*` 先指向测试表。

## 本地跑

```bash
pip install -r requirements.txt
cp .env.example .env    # 填真值
python main.py --once   # 只跑一轮(演练)
python main.py          # 常驻轮询
```

`DRY_RUN=true` 只识别打日志、不写表；验证无误后设 `false` 真跑。

## 部署（Docker，照宏佳触达服务的方式）

```bash
docker build -t miaopin-table .
docker run -d --name miaopin-table --restart unless-stopped \
  --env-file .env -v $(pwd)/data:/app/data miaopin-table
```

`data/` 挂卷持久化幂等状态(state.json)，容器重建不丢。

## 切到真进度表

真进度表授权给句子秒聘后，改 `.env`：
```
PROG_APP_TOKEN=JUCZbMNaSaoviosYIsjcRKcynKc
PROG_TABLE_ID=tblBedUZDTl2PASn
```
先 `DRY_RUN=true --once` 演练确认字段映射对，再切 `false`。
