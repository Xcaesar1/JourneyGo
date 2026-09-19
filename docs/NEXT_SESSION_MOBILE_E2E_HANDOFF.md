# 新会话执行交接：五天高铁与飞机完整实测

## 第三轮新城市验证（优先于下方历史）

- 用户最新澄清：不全选景点、不全选兴趣，只要求新城市、新任务。本轮杭州 `task_c6c8e6920bd149b59eb8`，成都 `task_259e985acea44f08830c`。
- 界面修复 `a2599a1` 与机场接驳补齐 `23bb1cc` 均已推送部署 staging。额度 15；成都新查往返两次后已用 10、剩余 5，恢复与修订必须复用报价。
- 杭州已保存且高德整图真实打开，1 张地图、5 天、25 条每日地点记录。不要重建。杭州灯光秀排在上午等人工发现仍未修复，不能作为整趟质量优秀案例。
- 成都曾因机场接驳过长暂停，修复后原任务恢复。审核中移除夜景及景区子地点的人工过程必须如实保留，不能宣称无人干预一次成功。
- 成都现已 completed / 正式 V1，2370 元部分费用，往返 JD5161 / ZH9442；凌晨 03:21 出发去机场。高德整趟地图仅创建 1 张，5 天19条每日地点记录，真机整图和日期列表已验证，今后直接复用。
- 以 `docs/demo/mobile-e2e/20260919-r3/README.md` 和本轮脱敏验证数据为最新证据。个人地图深链及含账号昵称截图仅留 artifacts。

## 第二轮已完成（优先于下方所有历史状态）

- 手机 ADB/CDP 已恢复。武汉新任务 `task_dd969c78306d402ebd79` 和丽江旧任务 `task_0954c6f772aa4cc6b128` 均 completed，已审核保存正式 V1；不是仅部署通过。
- 结果、14 张精选截图及脱敏验证数据见 `docs/demo/mobile-e2e/20260919-r2/README.md`。武汉已统计 2900 元，丽江 2566 元；均含估算且不是全价。
- 用户授权后 staging 航班额度已为 15，实测结束已用 8、剩余 7。本轮航班报价复用、未新增付费调用，未预订。
- 丽江玉龙雪山完整游览 360 分钟，往返采用高德驾车证据；驾车日市内交通费用未评估。原生高德导航本轮未打开，只验证链接方向和模式。
- 未新增专属地图；此前武汉整趟地图继续复用，不得因为新任务而重复创建。下方手机拒绝连接、丽江受阻及额度 10 均为历史快照。

## 2026-09-19 后续产品调整（优先于下方公交硬性限制）

- 用户已明确允许没有公交的路段提供驾车路线，不评估费用；不再要求丽江必须获得包车报价才可安排。不是已确认车辆，也不替用户下单。
- 本地已实现公共交通（公交、地铁）优先；按用户最新要求，单程 10 km 及以上比较驾车，仅在含预留后更省时才替换；缺失公共交通时也可驾车兜底。未知交通费用排除，支持固定起终点驾车跳转。详见 `docs/DRIVING_FALLBACK_20260919.md`。
- 后端 741 passed / 4 skipped，前端 65 passed，构建和 Ruff 通过。`fbd5a45` 已提交推送并仅部署 staging，API/worker healthy；数据/额度/生产容器前后比对一致，线上前端文件哈希匹配本地构建。发布记录见 `docs/DRIVING_FALLBACK_20260919.md`。
- 本轮手机 CDP 连接被拒绝，未恢复线上丽江任务，不能将发布通过当成真机丽江完成。航班仍必须复用，不得重新提交或刷新。
- 武汉整趟地图已另获明确授权并创建成功，仅 1 张、5 天、20 个地点记录；真机留存见 `docs/demo/mobile-e2e/20260919/amap-export/`。再次演示复用，不重建。

## 2026-09-19 最新状态（覆盖下方历史快照）

- 代码修复 `0f3d67c` 已推送并仅部署 staging，API/worker healthy；新增公交日期和去返程实际出发时间，避免缓存跨日期/时段复用。全量后端 713 passed / 4 skipped，前端 63 passed，构建和 Ruff 通过。
- 航班额度上限仍为 10，已用 8。广州到丽江往返已经查询，后续必须复用，禁止重新提交或刷新航班。
- 武汉 task `task_f1e13a3b841646c69f81` completed，G1040/G1042，五天四晚、2802 元已统计费用，首日无景点，黄鹤楼第二天 120 分钟。六区、五天展开、地图、触摸滑动通过。
- 大同旧 task `task_ea3708e702ef4d9993bb` completed，V3，4017 元，云冈公交专日通过，航班报价未刷新。
- 丽江 task `task_0954c6f772aa4cc6b128` awaiting_input / landmark_unplaced。三个酒店、9月21日至23日均有去程、无返程公交结果。16:00 的额外诊断探测同样为空。不要以跳过雪山冒充完成。
- 用户已授权“评估包车，不预订”。尚未授权替换正式行程，也没有取得日期特定的可确认包车总价。评估报告与真实证据见 `docs/demo/mobile-e2e/20260919/`。
- 原始材料和脚本在 `artifacts/mobile-e2e-{shenzhen-wuhan,guangzhou-lijiang,datong-regression}/`、`artifacts/mobile-routes.cjs`。本机连接需进程级 `NO_PROXY=localhost,127.0.0.1`，避免 CDP 被 HTTP_PROXY 转发而 502。
- 当前不再需要重复部署；本次发布目录 `/opt/tripstar/releases/landmarks-0f3d67c-20260919` 有 state/quota/protected 前后匹配证据。生产未变，无新高德专属地图，无预订。

## 用户当前授权与目标

先核对部署、提交现有改动，然后直接在新会话执行，不仅提供建议或交接说明。

1. 手机完整测试：高铁深圳到武汉，5 天。
2. 手机完整测试：飞机广州到丽江，5 天。
3. 保存真实手机操作截图、最终结果和必要录屏。后续整理为仓库 README 的项目实操展示，不伪造成功截图。
4. 测试中发现的问题继续修复、验证、提交并部署 staging。禁止修改生产、覆盖无关改动、重复创建高德专属地图。
5. 延续已经确认的地标与去重方案；首日规则保持去程不足 3 小时且最晚 15:00 到达，最多一个景点，否则不安排景点。飞机同规则。
6. 所有发布仅限 https://staging.elonmusk0.asia/ 。没有实际验证的步骤必须写明未验证。

## 当前仓库与实际部署状态

- 工作目录 `Q:/VPS/JourneyGo`，Windows PowerShell，当前分支 `main`。没有项目 `.codegraph/`。
- 已提交并推送：`e6307f3` 地标优先与去重；`c8305f0` 高德公交空铁路字段兼容；`347e846` 基于高德父子 POI 的景区内部组件去重；`fe8f73f` 手机卡片完整显示游览估算与半日/整日标签。
- 截至本交接核对，staging API 为 `journeyops-app:cities-api-e6307f3`，worker 为 `journeyops-app:cities-worker-e6307f3`，均 healthy。不要把 Git 最新提交当作已部署版本。
- `347e846` 的远程 API/worker 镜像已构建，但服务未切换。发布目录 `/opt/tripstar/releases/landmarks-347e846-20260918/` 已有 build 日志、release.compose.yaml、previous-compose-files.txt、state-before.txt、quota-before.txt；没有 state-after/protected-after 完成证据。
- 上次本地 SSH 发布连接未返回，原工具 session_id=38650，本地 ssh.exe PID=17760（使用前重新检查 PID/命令，不能盲杀）。远程 `pgrep -af 'deploy.sh|docker compose|docker exec.*python|travel-active'` 没找到进程，但这个模式未涵盖 `docker-compose`；新会话必须检查实际进程及 Compose 状态，防止重复部署。
- 本次交接文件写入前，仅剩 Landing.vue 的改动已经作为 `fe8f73f` 提交推送。本交接文件单独提交；先用 `git status` 核对，不回滚任何新出现的用户改动。

## 先完成的工作

1. 阅读 `docs/LANDMARK_PRIORITY_20260918.md`、`docs/MOBILE_TRAVEL_E2E_20260918.md` 与本文件，核对 Git、远程容器、未结束的发布进程。
2. 完成最新代码的 staging 发布，包括 `fe8f73f` 的前端新构建。现有发布 helper 已改为 backend-only，必须重新加入前端 tar 与 Docker COPY；不要误用旧 dist。
3. 恢复原广州到大同任务，复用已保留的公交/酒店/航班证据，确认空 railway 修复后云冈石窟能安排成功。不要点击“跳过云冈石窟”来伪装成功。
4. 再开展用户本次要求的两条新路线。旧测试文件和任务不能被新路线覆盖。

## 测试输入与预算边界

- 建议沿用 2026-09-20 至 2026-09-24、1 位成人、总预算 CNY 5000、商务舒适酒店，前提是执行时日期仍在可查询范围。日期已过或报价不满足时，记录原因，不能悄悄改变用户约束。
- 深圳到武汉必须核对实际为高铁/动车 G/D 车次。仅选择泛化的“火车”而最终返回 K/Z 普通列车，不算通过本次高铁测试；如系统缺少类型约束，定位并修复。
- 广州到丽江需要一组新往返航班查询，原广州到大同报价不能冒充该路线。用户此前已授权航班累计额度 10 次，最近确认用量为 6，必须先读实时计数；新路线正常只需新增最多 2 次。禁止提高/重置额度，禁止模型重试自动追加查询。
- 酒店可在既有服务下按明确 UI 操作刷新；飞常准只查询、不订票。出发日期、预算、交通方式变化先由用户选择。
- 高德地图已有导出记录要复用。测试跳转不等于允许重新创建多张相同地图。新行程若需首次新建地图，先说明并确认，不为了录屏批量创建。

## 核心验收

- 首页候选、默认偏好、明确必去、取消推荐均能正确传入生成请求；默认推荐不得全部变成 must_visit。
- 武汉黄鹤楼、丽江玉龙雪山进入候选并优先安排。玉龙雪山按整日规划估算，分别核算往返公交、游览、用餐/休息，不能以驾车时间冒充公交；无法核实时显示具体原因和 2 到 3 个可操作选项。
- 同一体验组整趟最多一次。长城是具体景区；古城内独立寺庙不因地理包含而删除。景区组件合并必须有高德父子关系加核实规则，不以名称包含或距离单独判断。
- 五天、四晚，交通日期和人数正确；首日限制成立；时间线连续；不超过每日可用时间；已统计预算不超用户预算；未核实门票、预约、营业时间、机票税费仍明确标注。
- 手机实测所有主要分区：概览、预算、景点地图、每日行程、知识图谱、天气；展开每一天检查，验证图片滑动、地图渲染、无横向溢出和无页面错误。
- 检查错误恢复按钮真的生效；完成草案审核保存后再记录“成功”。不购买酒店/车票/机票。
- 最终记录版本、日期、输入条件、任务标识、地标安排、去重结果、预算范围、遗留告警和实际失败原因。

## 手机与工具入口

- ADB `Q:/Android/platform-tools/adb.exe`，手机 serial `A4UF6R6206005438`，型号 AAK_AN00。
- 已恢复连接。若 Windows 显示 Android Composite ADB Interface 而设备列表为空，上次 `adb kill-server` / `adb start-server` 恢复成功；不要改系统驱动或配置。
- CDP：`adb -s A4UF6R6206005438 forward tcp:60445 localabstract:chrome_devtools_remote`；连接 `http://127.0.0.1:60445`。
- PowerShell：`$env:NODE_PATH='C:/Users/god/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'`，Node 中使用已有 Playwright 的 `chromium.connectOverCDP`。
- 现有忽略脚本 `artifacts/mobile-e2e.cjs` 支持 inspect / audit / landmarks / refreshhotel / continue / approve。其中 start 的路线写死旧路线，不能直接用于新测试。新建参数化脚本或独立文件，保存为不同 task/state 文件。
- `artifacts/mobile-verify.cjs` 校验旧两条任务状态、五天四晚、首日上限、连续时间线、预算和仅两条航班查询。
- `artifacts/landmark-home.cjs` 实测了大同首页、地标展示、取消后刷新仍不选回，输出 JSON 和 PNG。新页面测试后只关闭自己创建的标签。
- 手机填写输入后 blur 并等约 700ms，避免键盘遮住按钮。展开每日行程点击 `.ant-collapse-expand-icon`，不要误点导入高德按钮。
- 标准 Python `.venv/Scripts/python.exe`，`$env:PYTHONIOENCODING='utf-8'`。格式与检查 `uvx ruff`；前端 npm test / npm run build。
- codex-long-task 和 codex-memo 当前 Windows 不在 PATH，不要因此安装无关工具；项目文档是当前交接依据。

## 现有真实证据与未完成项

- 深圳到广州旧测试 task `task_6557c12b110e4a5ea85e`，trip `trip_ad9920df0f6b4362983a`，新 V2 已通过并保存。
- 广州塔已排入 2026-09-20，120 分钟，首日一个景点；原 C7124/C7119 往返报价保留。已统计费用 CNY 2260，不含未核实费用。
- 广州到大同旧测试 task `task_ea3708e702ef4d9993bb`，trip `trip_115fa2959d334a6ca926`，当前 awaiting_input / landmark_unplaced。旧正式版本仍保留。
- 新云冈候选已取得，酒店刷新曾通过手机“更新该项查询后继续”明确发起；往返仍为原 MU6733/MU6734，两条航班记录。
- 大同暂停根因已修：高德公交 segment 内返回 `railway:{via_stops:[],alters:[],spaces:[]}`，旧判断误认为包含铁路。`c8305f0` 按非空内容判断。
- 六条保留公交证据本地回放可用，单程约 101 至 113 分钟，公交 3 路接 20/60/65/38 路，带 15 分钟机动估算。已查询证据无需重查。未来班次、景区营业时间仍须复核。
- 首页大同已实测无页面错误、363px 无横向溢出、云冈首位默认推荐、180 分钟估算、取消后刷新保持取消。
- 进一步发现云冈内部组件占卡片，`347e846` 使用 parent POI + 城市地标限定去重，不把大同古城整体当成封闭景区删除寺庙。该补丁尚未在 live 首页完成验证。
- 手机截图发现时长标签被省略号裁掉，`fe8f73f` 已增加换行和半日/整日标签；重新构建/部署后需截图复核。
- 最新完整后端回归：698 passed、4 infrastructure integration skipped；最新前端 63 passed。`fe8f73f` 构建产生了新 dist，但原会话中断使最后构建退出结果未收取，发布前重跑构建确认。
- 原始结果位于 `artifacts/mobile-e2e-{train,flight}.json`、`artifacts/mobile-*-*.png`、`artifacts/landmark-home-mobile.{json,png}`，均未提交。不要用旧截图冒充新路线。

## 部署入口与保护

- SSH alias `oracle-cpamp`；Compose 工作目录 `/opt/tripstar/JourneyOps-staging`。
- 私有站点凭据 `C:/Users/god/.codex/private/journeyops-staging/access.json`，只有 url/username/password。不得打印、写入 README 或提交。
- 可复用 `artifacts/city-release/{deploy.sh,Dockerfile.api,Dockerfile.worker,verify.py,quota.py}`。当前 FROM/expected 是 e6307f3，运行前按实际容器确认；release 路径按 commit 构造。
- 保留容器标签里的既有 Compose 配置链，不从过期远程 checkout 全量重建覆盖现有修复。用精确运行文件 tar 和新前端 dist 叠加。
- 发布前确认 active_tasks=0；健康检查 API 和 worker；核对生产/demo/db 容器 ID 未变化、部署前后业务数据 hash 与航班计数相同。
- 当前失败/未完成发布目录不得当作已成功证据；必要时用 previous-compose-files.txt 回到最后健康服务。不删除历史版本或数据。

## 展示材料保存

- 新路线原始抓取先放忽略目录 `artifacts/mobile-e2e-shenzhen-wuhan/` 与 `artifacts/mobile-e2e-guangzhou-lijiang/`，每次测试有 manifest，避免覆盖。
- 精选展示材料整理到可提交目录，例如 `docs/demo/mobile-e2e/<日期>-shenzhen-wuhan-train/` 与 `<日期>-guangzhou-lijiang-flight/`。
- 至少保存填写条件、核心景点卡片、最终概览、核心景点当天时间线、预算与地图截图。必要时用 adb screenrecord 分段录制操作，保留手机真实画面。
- 提交前裁除/遮挡账号、通知、Basic auth、API key、Cookie、私人数据；禁止提交 access.json、原始供应商全量返回、浏览器 storage 或含凭据日志。
- 留下精简验证报告和机器可读汇总（不含密钥）；区分估算/已核实/未核实。README 后续展示只引用通过验证的材料，失败或部分完成必须如实标注。
- 用户说“后续加入 README”，因此先稳定留存材料与说明；可在测试达标后添加简洁实操展示章节，不用夸大文案，不把草案当真实预订。
