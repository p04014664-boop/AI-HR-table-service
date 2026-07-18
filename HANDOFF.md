# HANDOFF · 句子秒聘表格管理服务

给接手同事/另一个工具。看这份 + `PRODUCT.md` + `README.md` 就能接。

## 🟢 最新状态（2026-07-18 已上线并全自动跑通）

**代码仓库**：https://github.com/p04014664-boop/AI-HR-table-service （**公开**——玄玄拍板，公开前已抹服务器IP；GitHub账号 p04014664-boop，gh CLI 已登录本机）。宏佳触达服务仓库：git@github.com:JhjInsist/AI-HR.git（公开），本地克隆在 `../秒聘服务-宏佳/`（服务器旧版备份在 `../秒聘服务-宏佳-服务器旧版备份/`，含 .env）。**分工铁律（玄玄定的）：所有操作表格=本服务；所有操作Mongo+对外发消息=宏佳触达服务。**

**⭐触达前置自检(2026-07-18晚·玄玄E2E实测后定的规则,已实现部署)**：勾【AI触达】≠立即触达。rule2 先自检 `_REACH_REQUIRED=[联系方式,岗位,一面时间,一面面试官]`，缺任何一项→**不触达**，秒聘bot去句子秒聘群 `<at>` 点勾选的人(last_modified_by,兜底@一面面试官)报"缺什么"，补齐后下轮自动触达。同记录同缺项组合只提醒一次(state.reminded,缺项变化重新提醒)。**背景**：玄玄本人E2E时没填一面时间就触达了,AI欢迎语发"(时间待定)"很尴尬。E2E还发现:接口提速(全表扫→单条直查+search,15s→亚秒,写表异步)、HR岗位匹配不上"人力资源管理专员"配置(加了_ALIAS)、按人力标准包玄玄简历56分vs通用虚高90分。**测试数据已回滚**(删测试行+测试面评doc)。宏佳侧遗留:mh回调有一类"未识别类型"(加好友结果没落库,他侧小缺口);玄玄测试触达的Mongo task在他库里(不碍事,重测会建新task)。

**联调状态(2026-07-18晚)**：宏佳已完成触达服务去表格化并部署;我方已群发三件事就绪+base URL `http://aihr-table:8090`(他配 TABLE_SERVICE_URL 即联调);反向转人工(HR勾框→停AI)已提 **PR https://github.com/JhjInsist/AI-HR/pull/1**(fork p04014664-boop/AI-HR,分支handover-endpoint),等他合+部署。**待对齐分歧:/reach 触发=勾AI触达(玄玄定)vs 一面信息就绪(宏佳文档),已在群里提出。**

**⭐服务间接口（2026-07-18晚,已上线互通）**：按宏佳定的 `秒聘服务-宏佳/docs/触达服务接口文档.md` 实现了表格服务侧 HTTP 接口(api.py, 端口8090)：`POST /progress/backfill`(回填备忘录/一面时间,dataId定位、phone兜底) + `POST /progress/handover`(AI判定转人工→置【转人工】=是+备忘录记原因) + `/health`。容器加入宏佳建的 docker 网络 **`aihr-net`**，他的服务调 **`http://aihr-table:8090`**(容器内实测通)；宿主机调 127.0.0.1:8090。规则② `/reach` 入参已对齐契约{dataId,phone,name,position,interviewer,interviewTime}(触发仍按玄玄定的勾【AI触达】,非宏佳文档写的"一面信息就绪")。**转人工双向**：HR勾框→rule5→宏佳/handover→Mongo停AI；AI自判→宏佳调我/progress/handover→我置框=是(rule5回声同步Mongo,幂等收敛不成环)。进度表【转人工】复选框玄玄已建,rule5已在盯。

**规则⑤转人工（2026-07-18新增，两端已写完）**：进度表【转人工】复选框(玄玄要建,还没建,建了自动生效)变化 → 本服务 POST 触达服务 `/handover {dataId,handover}` → 宏佳服务更新 Mongo reach_tasks.humanTakeover → 候选人消息 AI 静默不接待；取消勾选恢复AI。本服务侧已部署；**宏佳侧代码已提交进他仓库本地克隆(commit 490ada9: schema+/handover接口+onMessage拦截,tsc过)，但他服务器容器还是旧代码，endpoint 上线要他部署**——rule5 对 404/失败会warning+下轮重试，无害。

**项目文档（已发句子秒聘群）**：https://juzihudong.feishu.cn/docx/EDRyduP9uo8SoGxPLkVcZdGynEg 。句子秒聘群 chat_id=`oc_8f33f2eb5afd3efb810ed338d995cf3f`，**发群用秒聘bot(cli_aad38)API直发**，句子局长bot不在此群(230001)。

**部署**：Docker 容器 `aihr-table` 跑在服务器 `公司服务器(IP不入公开仓库,见服务器/内部台账) /opt/aihr-table-service`（与宏佳触达服务 `miaopin` 并存），句子秒聘应用身份(cli_aad38)、每30秒轮询、DRY_RUN=false 真写、不依赖任何人CC/登录。`.env`（密钥）在服务器上，改代码用 `rsync` 到该目录再 `docker build && docker run`。

**应用**：句子秒聘 `cli_aad38fd84da1dbb3`（app_secret 与豆包 ARK key **不进仓库**——在服务器 `/opt/aihr-table-service/.env`，或飞书开放平台/火山方舟控制台查）。已开权限：base:record读写删、drive上传、**docx:document(应用身份)**。真进度表高级权限里给「秒聘」角色配了"可编辑"。豆包 model `doubao-seed-2-0-lite-260428`(文字+视觉)。

**三条链路都实测通**：
- 链路A(约面自动同步)：点约面→30秒自动进真进度表(岗位判断/身份/手机/面试官last_modified_by/简历附件全齐)。**白名单 data/state.json 预置70个老约面→绝不碰**。
- 链路B(手动传简历)：进度表空白行丢简历→自动读(PDF直读/图片豆包看图)→填姓名/手机/身份/岗位(从简历经历推测→映射标准岗位)。只碰"空白行+有简历+备忘录空"。
- **面评生成**：链路B候选人自动生成面评文档挂进面试评价。结构对齐深澜：**一、简历(嵌原始简历文件) / 二、AI初筛(按岗位标准包评分) / 三、面试评价**。

**⭐核心原则(玄玄反复强调)**：一切原点=HR知识库的岗位标准包。**面评评分实时从「AI面评Prompt文档」`Nsgbw1j1Bi1IYUkG6kkcaKcDnFe` 读**(按【岗位配置N】分段，standards.py，120s TTL，知识库改了自动跟上，不写死)。深澜同款尺子。

**代码**：config/feishu/doubao/resume/standards/mianping/rules/main.py + Dockerfile。一次性脚本 run_one.py(单人)/gen_mianping.py(补面评)/rejudge.py(补岗位)不进镜像。

**关键坑/教训**：①真进度表高级权限→附件下载要用附件对象的 `url` 字段(非medias/download)②docx嵌文件=建block_type23返回视图块33、真文件块是其子块、上传parent_type=docx_file到子块再patch replace_file③open_id分应用(读写同一应用才能设人员字段)④进度表混着在职员工，去重别只靠姓名⑤权限分"用户身份"vs"应用身份"，服务要应用身份那栏。

**⭐岗位判断(2026-07-18修)**：手动简历的岗位**先从BOSS文件名`【岗位_城市 薪资】姓名.pdf`抓**(resume.position_from_filename)——这是候选人真实投递岗位、最权威；抓不到才退回读正文猜。之前只读正文猜，姜欣妍有PM实习被误判"产品团队"，实际文件名写着`【AI管培生（市场）】`。管培生等分方向的岗位：standards.rubric_for(fs,岗位,hint=文件名岗位) 用hint里的方向词(市场/技术/出海/政务)在多个同名配置里选对标准包。岗位会写进面评标题`面试评价-{岗位}-{姓名}`。

**⭐文档权限(2026-07-18修)**：应用建的docx默认只有应用是owner、HR打不开改不了。mianping每建一份自动 `fs.set_doc_org_editable`→设「组织内可编辑」(link_share_entity=tenant_editable)，公司同事拿链接即可编辑。已回补给之前3份。

**⭐校正联动(2026-07-18新增,rule4)**：HR在进度表人工改【岗位】→ 服务自动发现"岗位字段≠面评标题里的岗位"→ 改面评标题+按新岗位标准包重打AI初筛分。**只碰备忘录=手动简历·AI解析 的行(深澜的面评绝不动)**，「一、简历」「三、面试评价(HR手写)」整段不碰(mianping.resync 用 replace_section 只换二节)。幂等：标题一致=零成本跳过。已在测试文档E2E验证(产品经理→后端工程师,HR手写保留)。standards.rubric_for 改为**岗位字段优先**定配置、文件名hint只兜底/消歧方向。

**待办/可选**：范子腾重复行已清(渠道BOSS-惠合并进保留行recv5qGtD4bscr后删了1334)；第3份手动简历(后端·猎头推荐PDF无【】)没抽到姓名；面评生成慢(每份30-40s)。**真表删记录被Claude安全拦截需用户确认**——设计上删除都先问玄玄。

---

## 当前状态（2026-07-18）
- **v1 建成**：10 文件的独立 Python 服务，能 Docker 部署。
- **已用句子秒聘应用身份(cli_aad38)跑通 DRY_RUN**：读真 AI-HR → 判岗位 → 下载+解析简历(补身份/手机) → 设面试官(last_modified_by) → 规则①拼记录。规则②读进度表判 AI触达。全程无 CLI、无个人登录。
- 实测(限3人):刘珂/赵景渊/尹翼森 岗位=测试工程师/研发团队、身份/手机从简历读出、面试官带上,均正确。

## 还等的（阻塞真跑）
1. **句子秒聘开权限**：`base:record:delete` + `drive:drive`(上传附件)。已有 retrieve/create/update。
2. **真进度表(JUCZ/tblBed)授权给句子秒聘**：现在 `RolePermNotAllow`。授权后把 `.env` 的 `PROG_*` 指向真表。
3. 授权后：先 `DRY_RUN=true --once` 演练确认字段映射，再 `DRY_RUN=false` 真跑。

## 关键 ID
- AI-HR 来源表：`H4NTbtLkia9z3fsO0c7cWDWNnod / tblTSVXwu1onvPMa`（12字段，含联系方式，1482条、约面69）
- 真进度表：`JUCZbMNaSaoviosYIsjcRKcynKc / tblBedUZDTl2PASn`（混着候选人+在职员工，去重必须用候选人ID别用姓名）
- 测试进度表(现默认)：`WzXpbCdYgaZDk0s7dSiczy20nnc / tblVRrAmRPtQsY1L`
- 触达服务：`http://ai-hr.juzibot.com`（宏佳，公司服务器容器 miaopin）
- 豆包模型：`doubao-seed-2-0-lite-260428`（同一模型文字+视觉）

## 待办 / 下一步
- [ ] 权限到位 → 切真表演练 → 真跑
- [ ] 部署上服务器(Docker，照宏佳触达服务方式)，data/ 挂卷
- [ ] **手动传简历那条链路**(链路B)：进度表【简历】栏收到附件→解析→回填字段，尚未写(引擎 resume.py 已就绪，缺触发+回填)
- [ ] 去重升级为「表即状态」(现用 data/state.json 本地文件)
- [ ] AI触达字段：真进度表叫「AI触答」(笔误)，代码已兼容两种名；玄玄可能改名

## 坑/教训
- 飞书 open_id **分应用**：读写必须同一应用，否则人员字段(面试官)写不进。
- 真进度表混着在职员工(张玄玄本人是员工记录)，去重只靠姓名会覆盖真人 → 用候选人ID。
- 附件跨表要「下载→上传」，upload 需 drive 权限。
- 无删除权限时 batch_delete 静默失败，要查返回码。
