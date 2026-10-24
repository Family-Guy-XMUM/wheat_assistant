# wheat_assistant v0.2.1 修正候选验收

> Commands and code paths in this document are relative to the repository root. See the [documentation index](../README.md). This file preserves historical local acceptance results; current cloud deployment evidence is indexed [separately](../../Submission/preliminary/evidence/README.md).

**状态：修正候选，待 Windows v0.2.1 实机复验。** 详细命令和逐项回执要求见 [WINDOWS_VALIDATION.md](WINDOWS_VALIDATION.md)。本轮没有新增真实模型调用；原有模型质量未通过的结论保留。

本轮修正：CSV夹具字节保护、Windows环境大小写、SQLite显式释放、拥有的进程树停止/端口/重启验证、逐批明确Hold确认。FlowSpec v1、旧摘要和历史结果保持；新审批缺少或带过期状态确认返回409。

本轮组合包含原有101项业务检查（两条默认Hold路径加强）、Harness的18项独立回归、协调者10项进程/报告/打包回归及8项浏览器路径。正式完整组合的实际数量与结果以本次 `verification/final-checks.json` 为准，不把分组成功当成新Windows通过。

固定规模正式性能结果见本次 `verification/performance.json`：必须三次完整试次、八表/10000唯一追溯/5000 SKU全量浏览/临时库清理成功，导出中位数≤10秒且RSS采样有效。25ms父子进程RSS采样会重复计算共享页。macOS数据不能作为Windows性能结果。

源码版真实HTTP验证包含三周36/39/24行、规则版本1/2/2、未确认状态审批409、不同端口同目录重复实例拒绝、严格端口占用拒绝、三轮原端口重启/新实例/历史下载一致。原生候选须另附独立解压的同类JSON，未附报告不得视为通过。v0.2.1证据按版本/验证批次保存，源码包的 `verification/` 只选择本次版本，原始日志不打包。

Windows原生包须在Windows构建；本机提供的是Windows源码复验ZIP及macOS arm64包。所有包以实际SHA-256识别，不把基线commit冒称新提交。未进行push、公开发布或正式提交。

---

## v0.2.0 历史验收记录

以下保留上一批本地验收结论。其旧路径、101项/7项数量、3.122秒和“Windows未执行”均指当时状态；后来收到的Windows回执总评失败，新版本须重新验收。旧报告不作为v0.2.1通过证据，也不默认随本次源码ZIP分发。

# wheat_assistant 0.2.0 本地整改验收（2026-10-22 MYT）

本轮由 Codex / agent-audit 协调、实现主线并最终重跑验收；DeepSeek Harness / agent-contract-tests 实现 CSV／模板导出加固，新增26项独立测试，并进行两轮只读复核。Replit Status Guard 原有来源与哈希保持。没有新增 Git commit、push、公开发布或赛事提交。

**当前交付状态：源码整改和 macOS 本地验收完成；Windows 等待今晚实机回执；真实模型质量未通过。不能将这两项写成全部验收通过。** 原生包独立验证的机器结果以随包 JSON 为准。

## 已实现与复核

- 严格 CSV、合法跨行与转义、准确物理起止行、UTF-8/BOM、单字段及原始行 JSON 的 Excel 字符上限；错误明确，不截断。选定模板工作表，公开属性复制基本样式；八表临时写入、重开验证、原子发布，保留公式文本与大整数精度。
- 明细100条默认，可选50/100/200；SKU50条、历史20条，搜索、末页、异常原因分组、原值和轨迹。活动默认关联当前运行、审批和来源，可切换全局。
- failed/interrupted 运行复用原ID与快照。审批／创建运行／导入响应丢失后先查保存状态，显式开始执行。相同 keyed 导入、审批、运行、结果与导出器版本幂等；失败新导出保留旧默认下载。所有下载和模拟任务均校验 artifact 存在与 SHA-256。
- 显式选择流程版本；流程身份、规则版本和本批审批分离。六组规则及输入差异、同来源多文件完整状态、主表单位、异常修正规则入口。变更重新预检和审批，原件／旧规则／旧结果保留。
- 保留 FlowSpec v1 和原摘要算法，旧解析一致才可恢复，不一致转新批。启动前验证备份；已知缺 revision 的旧表补列，已存在entities表缺必填列时明确拒绝，不尝试迁移其他应用表；没有entities时保留原表并新建本应用表。桌面启动器按数据目录加 OS 单实例锁。

## 实际检查

| 项目 | 结果／证据 |
|---|---|
| Python 回归 | 101 passed；原66项未删除或修改；另有 Harness26项及协调者9项。现有 Starlette/httpx 弃用警告1条 |
| TypeScript／Vite | 生产构建通过，依赖锁验证通过；依赖未扩展 |
| 浏览器 | 7 passed：三周完整审批与导出；一万行/五千SKU首末页与搜索；断网显式重试；approve/run响应丢失；快速切换过期响应；普通上传新来源/75种状态/主表单位/导入响应丢失 |
| 源码真实HTTP | 三周1→2→2规则版本、36/39/24行、21/33/84数量、八表、模拟handoff幂等通过；重复实例被拒绝，停止释放端口，真实重启后历史与旧下载可用 |
| 备份恢复 | 实际开工前备份复制到临时目录，SQLite integrity ok；85条实体、19份原件、3个已完成结果、1份旧导出哈希一致，无修改原备份 |
| 原生 macOS arm64 | 在本机重建；独立解压、无Python/Node PATH、无key三周流程及重启验证，见 `verification/native-release.json`（源码包中）或本地 `output/verification/native-release.json` |
| Windows x64 | **未执行，待用户今晚安排**；提供源码分发 ZIP、Setup/Start/Validate BAT 与 WINDOWS_VALIDATION.md，不能冒称 Windows 原生包已构建或已通过 |

浏览器扩展验收期间曾出现 `net::ERR_NETWORK_IO_SUSPENDED` 系统网络暂停；重跑相同流程通过。新测试另有两处夹具/选择器假设纠正（W2状态仅在channel-b，原生option没有显式value属性）；原有测试与业务预期未放宽。Harness终审发现的七项回归修复前7失败、修复后7通过；legacy审批和 keyed 导入另两项修复前失败、修复后通过。

原生包首次独立验收出现RuntimeError，当时脚本未保留足够阶段信息；后续同包直接重跑已完成三周、停止、重启下载。验收脚本已增加安全错误阶段信息，并将冷启动等待从15秒延长到60秒；不改变产品数据断言。最终通过以JSON回执为准，初次失败保留在本地记录，不当成从未发生。

## 固定规模性能

同一台 macOS arm64 开发机，五个合成订单文件共10,000行、5,000商品，三次独立临时库，每次实际执行和完整导出，均非缓存复用。正式导出实测为3.276／3.122／3.095秒，中位数3.122秒，低于10秒目标；父进程与执行子进程 RSS 峰值384.7／417.1／467.3 MiB。25ms采样且共享页会重复计数，非精确分配量；三次在同一Python进程依次进行，含解释器缓存影响。

每次独立重新打开八张表：Picklist5000、Order_Detail10000、SKU_Summary5000、Lineage10000；三个隔离表0、Run_Summary9；5000个SKU均数量4，10000条唯一追溯，API遍历全25页SKU，工作簿无公式。先前26.228秒为审查诊断参考，不作为严格同夹具基准或真实客户收益。

## 真实模型：保留失败

12个独立合成标注案例的确定性预期全部通过；其中6例送入本地已配置的兼容provider/model（报告模型标识 agnes-2.5-flash），每例最多2次，包括结构修复，总计**12次HTTP请求，无追加调用**。

| 案例 | 首次成功 | 修复后成功 | 结果 |
|---|---|---|---|
| 中文表头 | 否 | 否 | 两次invalid_output，拒绝 |
| 订购/已发数量 | 否 | 否 | 两次invalid_output，拒绝 |
| 未确认产品别名 | 否 | 是 | 保持异常，未发明映射 |
| 未知单位 | 否 | 否 | 两次invalid_output，拒绝 |
| 部分发货 | 否 | 否 | 两次invalid_output，拒绝 |
| 数据内提示注入 | 否 | 否 | 两次invalid_output，拒绝 |

首次0/6，修复后总1/6；唯一接受的输出未见危险错误，其余5例未取得合格结构，不能据此评估语义安全性。5例需要人工编辑；本次未替模型修改答案或更改期望。报告含每例请求数与状态，失败如实保留。之后补充正式JSON schema、明确Hold应省略状态键、具体校验错误修复提示；mock回归通过，**新提示尚未再次真实验证**。无key的可编辑规则流程已经完整验证，AI不能自动执行或跳过六组审批。

## 分发与剩余限制

- Windows x64 实机安装／启动／停止、原生包与人工Excel检查尚待回执。运行 `Validate_Windows.bat`，交回三份JSON与人工清单；详细日志可能含本机路径，留本地脱敏。macOS开发包未签名/公证，不绕过系统保护。
- 首次观察之前已被改动的旧导出，若旧库从未保存hash，无法追溯判定；新版从登记后校验。硬杀进程可能遗留未登记临时artifact，保留在本地，不自动删除业务文件。
- 120秒客户端超时不等于取消后台请求；确定性worker有30秒墙钟/20秒CPU/512MiB限制，导出后台若卡住需重启并显式重试。桌面启动器防重复实例；绕过启动器直接多进程托管API、多人认证与租户隔离不在本地原型范围。
- 历史采用offset分页，其他入口持续写入时可能需刷新；当前单操作者静止审查已验证。支持基本模板表头样式，不支持复杂宏/工作簿布局。
- 隐私检查涵盖源码、允许分发的报告与包、内部压缩成员和Python字节码；不将`.env`、运行库、缓存或`.git`纳入分发。现有本地Git身份元数据未重写，公开仓库身份检查仍须在公开前单独完成。
- 正式参赛文档、平台证明公开访问、视频与官网提交不在本轮；Replit仅为真实开发的Status Guard模块，Orbyte仅模拟。

详细机器证据保存于本地 `output/verification/`；Windows源码ZIP内的 `verification/` 是本轮已脱敏证据快照。两份分发包的SHA-256在同目录 `SHA256SUMS-v0.2.0.txt`，Windows原生包由Windows实机构建后另产生校验值。
