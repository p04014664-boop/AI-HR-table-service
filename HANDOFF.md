# HANDOFF · 句子秒聘表格管理服务

给接手同事/另一个工具。看这份 + `PRODUCT.md` + `README.md` 就能接。

## 🟢 最新状态（2026-07-18 已上线并全自动跑通）

**✅ 面评格式定稿+深挖排查(2026-07-19凌晨)**：①玄玄批面评排版→**照他示例文档`RDDMdeNbpowX5mxWA2Qcmjp7nZ9`重做**:优点/缺点/分项打分用**飞书原生有序列表**(block_type13,绝不手敲序号-铁律)、字段一行一段、金字塔简洁(rule9输出改JSON+mianping.render_round_eval渲染);②**AI初筛重做=「简历-岗位匹配」**:只评简历可见(硬性门槛逐项核对/匹配亮点/风险缺口/面试需验证),**不打分**(分留给面试),禁评沟通逻辑等面试维度——玄玄批"初筛用面试维度是胡来"的修正;③**深挖出线上最大缺口:LLM无任何key一直裸奔**(意图分类全回退OTHER/知识库问答只有兜底话术,此前E2E的"AI回复"其实全是模板消息)→gatewayChat支持完整chat/completions路径接**火山豆包**顶上(env:ANTHROPIC_API_KEY=ark key+LLM_PROXY_ENDPOINT=ark完整URL+LLM_MODEL=doubao),意图分类7/7、KB问答实测正常(薪资按口径答不转人工+答完拉回约面);Claude/Bedrock key到位换env即可;④修backfill回填时间按轮次写字段(原硬编码一面时间);⑤建日程auto_record实测✓;⑥**待办:cli_aad38缺通讯录权限**(邮箱换openId返回空→面试官当不成主持人→妙记归属有问题,要玄玄/宏佳开contact权限+范围全员);⑦真实对话全流程/微信号加友待真人配合实测。展示用测试行recvpLMF46JCUj+新版面评`KLWldcWnZoR7QIxvttIckG6bnob`保留待玄玄验收。

**✅ 全量回归(2026-07-19深夜,玄玄要求"整测一遍"):全链路通过**：①健康:4容器(aihr-table/miaopin/miaopin-console/aihr-nginx)+nginx透传(/reach /mh/callback /console)✓②/kb权限玄玄已开,知识库全链路通(9973字,触达服务实拉含红线+问答)✓③时间槽位单测✓(修了raw重复拼接)④链路B自动填充✓⑤**规则⑨真实E2E**:贴逐字稿→按知识库固定输出结构生成11字段面评(结论:推76分,分项用人力岗30分制专属体系)→精准插入「一面:」后✓(修了漏import standards)⑥约成链路:backfill INTENT_ACCEPT→**勾【一面】复选框+触达状态=已确认+一面时间+备忘录+群报喜**全对✓。测试数据已全部回滚。宏佳更新已同步(console:RolesGuard即时生效+合并了我们的重发修复;AI-HR无新代码)。

**代码仓库**：https://github.com/p04014664-boop/AI-HR-table-service （**公开**——玄玄拍板，公开前已抹服务器IP；GitHub账号 p04014664-boop，gh CLI 已登录本机）。宏佳触达服务仓库：git@github.com:JhjInsist/AI-HR.git（公开），本地克隆在 `../秒聘服务-宏佳/`（服务器旧版备份在 `../秒聘服务-宏佳-服务器旧版备份/`，含 .env）。**分工铁律（玄玄定的）：所有操作表格=本服务；所有操作Mongo+对外发消息=宏佳触达服务。**

**⭐触达前置自检(2026-07-18晚·玄玄E2E实测后定的规则,已实现部署)**：勾【AI触达】≠立即触达。rule2 先自检 `_REACH_REQUIRED=[联系方式,岗位,一面时间,一面面试官]`，缺任何一项→**不触达**，秒聘bot去句子秒聘群 `<at>` 点勾选的人(last_modified_by,兜底@一面面试官)报"缺什么"，补齐后下轮自动触达。同记录同缺项组合只提醒一次(state.reminded,缺项变化重新提醒)。**背景**：玄玄本人E2E时没填一面时间就触达了,AI欢迎语发"(时间待定)"很尴尬。E2E还发现:接口提速(全表扫→单条直查+search,15s→亚秒,写表异步)、HR岗位匹配不上"人力资源管理专员"配置(加了_ALIAS)、按人力标准包玄玄简历56分vs通用虚高90分。**测试数据已回滚**(删测试行+测试面评doc)。宏佳侧遗留:mh回调有一类"未识别类型"(加好友结果没落库,他侧小缺口);玄玄测试触达的Mongo task在他库里(不碍事,重测会建新task)。

**⭐⭐知识库飞书化+面后AI面评(2026-07-19深夜,已上线)**：①**FAQ知识库表**=进度表base新数据表`tblogUqdG4hxuZ9f`「候选人FAQ知识库」(问题/答案/类型[问答/红线/口径/语气]/启用),已导入176条(Excel157问答+边界说明红线9口径9语气1);**⚠️等玄玄:高级权限里把这张表加进「秒聘」角色**,没加前/kb报RolePermNotAllow。②`GET /kb`(api.py,120s缓存)拼知识库文本;触达llm.answer优先拉/kb(60s缓存)→HR改表2分钟生效,配置台Excel上传退役。玄玄说FAQ"几百道题"的完整版位置待他发(他发的链接其实是面评Prompt文档)。③**规则⑨面后面评**:【逐字稿链接】新值→读docx→prompt=知识库面评文档的壳(standards.prompt_shell,一~十节:固定输出结构/分数规则,实时读)+岗位标准包+逐字稿→豆包→写进面评文档「一面：」后(mianping.insert_round_eval;面试评价非链接时现建文档)→群@面试官补人工结论;妙记页面链接读不了会@提醒贴"文字记录"文档链接。④**⭐存量铁律(玄玄定,记忆已存)**:规则⑨上线没seeding,把148条历史逐字稿当新增刷屏@周子杰,玄玄紧急停服→已修:首启把存量全部预置已处理(evaled_seeded),**以后任何新规则都必须先seeding**。⑤妙记自动搜索:应用身份suite/docs-api/search接口通(code 0),能否搜到面试官私有文字稿等首场真实面试验证;成则全自动填链接。⑥**服务器新格局**:宏佳方案A已上线=aihr-nginx占80(/console→中台,/*→miaopin),**miaopin容器不再发布80端口**(run命令去-p);中台miaopin-console容器:8091。⑦**IP白名单**:cli_aad38被配了IP白名单(99991401),本机直连API全被拒,一次性脚本改在服务器 docker run --rm 跑;群里已问宏佳。

**⭐⭐对话流程v2+约成全链路(2026-07-19晚,玄玄口述第二轮,已上线)**：①**约成动作链**:候选人确认→触达侧建日程(标题`线上面试-{岗位}-{姓名}`、描述带面评链接(rule2/_invite传evalDoc)、**面试官任主持人owner+assign_hosts、auto_record=true**→妙记文字稿归面试官)→backfill(带round)→表格侧**勾【一面】复选框**(=双方达成一致,round对应勾一/二/三面)+群@一面面试官"✅约成"②**改期**:引导给**时间区间**(话术"周四周五下午这样给个范围"),候选人给到具体哪天/钟点(不逼到分钟)→即找面试官拍板(群@,改一面时间=拍板);"下周吧"这种没到天→追问,3轮→转人工③**拒绝两步**:先挽留问原因(rejectAsked),再拒才转人工④**HUMAN意图**(要求人工→转)⑤听不懂**3轮**(原2改3)⑥**薪资不再转人工**(KB改为"面议,面试细聊";answer prompt=知识库优先+常识得体回答+真敏感才转,哨兵词"问下同事")⑦**沉默扫描器**(main.ts setInterval 30min):邀约(WELCOMED)超24h没回→转人工;改期拖延(INTENT_RESCHEDULE无pendingTime)超24h→每日回访,3天→转人工⑧转人工统一动作:表格勾框+状态转人工中+群@面试官"去秒回工作台接手"。**中台协同(宏佳 miaopin-console)**:⚠️ConfigService=**Mongo app_configs优先、env兜底**,app_configs现为空(env生效),中台初始化配置必须写 DRY_RUN=false/TABLE_SERVICE_URL,否则静默覆盖env;nginx方案A会占80、触达容器去-p 80:80(其余run参数不能动);console仓库暂 not found 等他推;cli_aad38发版要和他错开。

**⭐⭐触达对话流程重造(2026-07-19,玄玄口述规格,已上线)**：GitHub协作者已生效(接受邀请后可直推JhjInsist/AI-HR master)。核心规格=**AI目标是拿到确认的面试时间;改期时拿到具体时间必须找面试官拍板,AI绝不擅自定时间**。已实现:①**时间不一致=改期提案**:候选人给的时间≠约定(sameAsScheduled按天+半天/钟点比对)→不建日程,回"我和面试官确认下"→pendingTime存任务→backfill带expectTime→表格置"要改期"+群@一面面试官"改一面时间=拍板"→面试官改时间→规则⑧/notify直推候选人→候选人确认→此时才建日程;②**改期追问**:说改期但时间不全→extractTimeSlot槽位(date/part/clock,"周五下午"级)缺啥问啥,**3轮拿不到→转人工**(rescheduleAsks);③**连续2轮OTHER听不懂→转人工**(otherStreak);④DRY_RUN已改false(之前backfill被dry挡着,触达状态列一直没动过——真相:触达侧回填从没生效过)。**人工介入边界(已实现)**:要求人工/薪资类/知识库答不上/拒绝/加友发送失败/改期3轮/听不懂2轮。**待拍板(没实现)**:沉默跟进(24h催1次48h转人工?)、拒绝时要不要挽留一句、QUESTION答完拉回主线、条件式改期("等我看看")的定时回访。

**⭐⭐两服务统一接管(2026-07-19,玄玄拍板"你统一去改")**：不再区分我方/宏佳服务器——**触达服务(miaopin)的代码和部署现在也归我们改**。已统一落地:①**微信号加友**:createTask 支持 wxid 入参(跳过手机号校验,微信号当搜索词发秒回 addFriend——企微本就支持手机号/微信号搜索);②**话术分轮次**:欢迎语模板 {round} 占位,任务带 round,二面邀约不再说"一面约在";③**POST /notify 改期直推**:表格侧规则⑧优先调它,候选人已绑会话→秒推新时间+回到待确认态,没会话→退回重触达;④**部署真相**:同事之前的容器里根本没配 TABLE_SERVICE_URL(他说配了但没进容器,backfill一直没真打到表格服务),已补 `http://aihr-table:8090` 并验证互通;线上也没带bdd2de7,本次部署才真正带上。**miaopin部署流程(以后照此)**:本地`npm run build`→rsync dist+src+package*→`/opt/miaopin-service`→docker build→run(--network aihr-net -p 80:80 --env-file /opt/miaopin-deploy.env -v data)。env-file=/opt/miaopin-deploy.env(从旧容器抄的+TABLE_SERVICE_URL;DRY_RUN=true但实测不拦加友/发消息,没动)。**代码推送**:JhjInsist/AI-HR 无写权限,统一推 fork `p04014664-boop/AI-HR` master(线上以我们部署为准,仓库同步靠fork,玄玄可让宏佳给权限或转移仓库)。

**⭐场景对齐第一轮(2026-07-19,玄玄口述)**：①转人工语义定稿=勾:人工模式/取消:切回AI(线上即此)②**规则⑥转人工超时提醒已删**(转人工后去秒回工作台看消息即可)③**轮询30s→5s**(.env POLL_INTERVAL_SEC=5;8规则共享1次拉表,频率OK已观察零限流)④**规则⑦轮次推进已实现但停用**(main.py注释,等按场景聊完再开)⑤**联系方式栏语义定稿=「能联系上他的微信号」**:默认手机号=微信号;加不上好友→HR电话人工校正→回填(可能是微信号)→**联系方式变化且勾着=自动重触达**、**取消勾选再勾=重触达**(reached从list改{rid:联系方式}老格式自动迁移);非手机号格式→payload带wxid字段。**⚠️等中台(宏佳):微信号加友**——他createTask校验`/^1[3-9]\d{9}$/`会把微信号拒掉+秒回加友接口要支持按微信号搜索,这个没对齐前微信号触达发过去会被拒(我侧日志能看到)。

**⭐主干道P0+轮次推进已上线(2026-07-19,玄玄拍板"直接提主流程")**：分工定稿=玄玄走主干道流程细节、宏佳做中台;不再走PR(PR#1/#2都已关,宏佳bdd2de7自行同步了二次触达修复=消息匹配加手机号兜底)。新上线:①**「触达状态」单选字段**(玄玄没建我用句子局长CLI建的,9选项:待触达/已发好友申请/已加上好友/已发邀约/已确认/要改期/已拒绝/转人工中/触达失败),backfill/handover/rule2/rule5全链路写入;②**规则⑥转人工超时**:勾转人工>24h没取消→群@提醒一次;③**规则⑦轮次推进**:一面反馈=通过→二面时间+面试官没齐→群@提醒排面(每轮一次);齐了→自动`_invite`调/reach发二面邀约(老好友重触达,靠宏佳bdd2de7兜底绑定),三面同理;**授权模型=首轮勾AI触达授权全程,后续轮自动**;④**规则⑧改期联动**:已触达候选人当前轮时间被改→自动重发邀约+群通报,面试官改表格=确认改期;⑤**性能**:每轮只拉一次进度表8规则共用(原来每规则各扫一遍);⑥interviewTime改传毫秒字符串(裸number会让宏佳侧.trim()崩)。**中台待宏佳**:round参数的话术分轮(现在二面邀约话术还是"一面约在";/reach已带round字段)、主动推送消息接口(改期即时通知)。

**⭐全局方案已出(2026-07-18深夜,玄玄休息前布置)**：全盘体检+下一步方案文档 → 本目录`全局方案-下一步.md` + 飞书 https://juzihudong.feishu.cn/docx/Hh40doGqOo7MpyxhGT1cVawznff 。**等玄玄拍板3件事:①催宏佳合PR#2 ②建「触达状态」单选字段 ③二面三面是否首轮授权后自动**。深夜体检:反向转人工全链路验证通(接口→Mongo双向)、修掉rule5把NestJS 201当失败无限重试的bug(周子杰那条重试84次)、白名单完整(synced74)、日志清零。**玄玄的AI约面测试行已被同事清掉,表里只剩他的在职员工记录(绝不能碰)**;他的Mongo触达任务仍未绑wxid(二次触达bug未修,宏佳线上代码=旧onFriendConfirm,已验证编译产物,他说"做的是一件事"不成立,PR#2保留)。

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
