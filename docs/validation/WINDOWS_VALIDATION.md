# Windows x64 v0.2.1 复验交接

> Commands and code paths in this document are relative to the repository root. See the [documentation index](../README.md).

**交付状态：修正候选，待新 Windows 实机回执。** 目标环境为 Windows 11 x64。v0.2.0 回执已证明安装、7项浏览器和手动三周流程可运行，但正式自动验收失败：CSV夹具换行、自动停止、过滤环境原生启动、性能数据库释放均有问题；这些旧失败不被覆盖。v0.2.1 的 macOS 通过不能代替 Windows 通过。

演示仅含团队自造合成数据，Orbyte 为模拟；本轮不调用真实模型。源码 ZIP 不是 Windows EXE，原生 ZIP 必须在 Windows 构建。

## 1. 安装和自动复验

1. 将源码 ZIP完整解压到新的中文、空格目录，例如 `C:\wheat_assistant 复验\wheat_assistant`。保留旧版本目录和旧回执，不复制 Mac `.venv`、`node_modules`、私有 `.env` 或旧数据库。
2. 准备 uv 和 Node.js 22+（含npm）。运行 `Setup_Windows.bat`；它用锁文件准备 Python 3.12，即使系统另有Python也不改用它。首次下载需要网络。
3. 再运行 `Setup_Windows.bat`，确认已有 `.env` 不被覆盖。不需要填写key。
4. 运行 `Validate_Windows.bat`，或在终端运行 `Validate_Windows.bat --no-pause`。

每次验证新建 `output/verification/v0.2.1/<attempt-id>/`，按顺序运行八阶段：Python测试、TS/生产构建、安装Chromium、浏览器验收、源码HTTP验收、本机原生构建、独立解压原生HTTP验收、三次规模性能验收。失败立即停止，后续步骤明确为 `not_run`；修复后重跑会创建另一目录。

2026-10-24整改新增同目录的 `python-tests.json`，在pytest成功、失败或采集出错时写入计数、退出码和安全定位。仅公开测试名称（参数值被替换）、阶段、异常类、数值WinError和仓库内Python位置；原始消息、局部变量和捕获输出仍留在本机日志。CI失败时也上传这份JSON，测试失败不会因此变为成功。

本批还修复两处测试主动删除只读blob缓存的Windows兼容性，并固定团队合成XLSX的时间元数据，避免同周样例跨秒重新生成时哈希变化。首次新CI的170通过／1失败定位到下载MIME断言后，API显式声明XLSX类型，不再依赖主机注册表的扩展名映射；错误映射回归修复前2失败、修复后通过。实际上传原件的哈希和业务差异校验保持。当前真实CI结果见[验收记录](ACCEPTANCE.md)最新条目；自动CI不能代替下方人工Excel和真实操作者回执。

第二轮Windows已通过173测试及浏览器验收，但源码停止后的250ms端口探测只取得待完成的10035，未取得明确拒绝。新探测使用原10秒总截止内的剩余时间等待同一次连接完成，仍要求ECONNREFUSED／10061及独占绑定均成功；10035、超时和权限拒绝均不是通过证据。应用该次停止本身为退出0、无强制清理，原失败JSON保留。

第三轮Windows175测试、浏览器、源码／原生三周及各三重启通过；三次性能试次数据和清理完整，但导出中位10.043秒超过原10秒标准，仍记失败。后续仅优化生成工作簿的全量验证：八表、行数、表头样式继续重开检查，公式改为安全流式扫描全部工作表XML（包括声明尺寸之外的尾部），不删行、不采样、不放宽时间目标。新增尾部公式／公式样文本回归，当前本地178测试通过，Windows结果按对应新CI回执核验。

通过要求：

- `windows-validation.json` 的八阶段全部 `passed`，自动总评 `automated_passed: true`（`passed`为兼容别名）。`acceptance_status`仍为 `pending_operator_confirmation`，不能据此宣称人工验收完成。
- `windows-source-release.json`、`windows-native-release.json` 都通过，`ai_calls: 0`；三次 `restart_cycles` 均为新实例且历史/旧下载一致；所有停止记录 `graceful: true`、`forced_cleanup: false`、端口拒绝连接且可绑定。
- `windows-performance.json` 有 **3个完整试次**、`complete_trials: 3`、清理全部成功、八表/10000追溯/5000 SKU/内存采样通过，导出中位数 ≤10秒。缺数据、WinError32或不完整试次均不算通过。
- 各报告的源码指纹一致，原生包SHA与实际文件一致。`base_commit`是开发基线，工作区候选还由 `candidate_sha256` 标识，不能把基线SHA当成新版本commit。

原生包位置为 `dist/wheat_assistant-Windows-AMD64-v0.2.1.zip`，以程序实际输出和报告中的名称为准。CI配置不代表CI已经运行或实机通过。

## 2. 人工复验清单

请在本批目录新建 `windows-manual-checklist.md`，记录日期、实际操作者的项目代号、工具执行与真人复核是否分别完成。逐项填写通过/失败/未执行，不替他人签名。

- [ ] `Start_wheat_assistant.bat` 自动打开网页，无key可用。确认显示v0.2.1，输入为合成样例。
- [ ] Week1：新建流程，明确确认 `Jasmine500 → TEA-001`、`carton → box`；检查六组并运行。结果 `36 = 24 + 3 + 3 + 6`，规则v1。
- [ ] 导出并用实际Excel打开八张表；TEA-001=21、SOAP-002=33、RICE-003=84。保留Excel保护视图，不关闭系统保护。
- [ ] Week2明确复用v1：`Partially shipped` 初始为 **Unreviewed**；即使勾选六组，运行按钮仍禁用。
- [ ] 明确选择 **Hold as exception** 或勾选对应 `Confirm hold`，重新确认六组后可运行；结果 `39 = 24 + 3 + 3 + 9`，三条新状态只在Exceptions中，规则仍v1。
- [ ] 修改规则或切换来源版本后，旧Hold确认和六组检查清除，必须重新预检/确认；不能继承上批确认。
- [ ] 在Week2新草稿中把该状态改为Exclude，重新检查和六组确认；结果 `39 = 24 + 6 + 3 + 6`，规则v2，旧Hold结果仍在。
- [ ] Week3明确复用v2：24行全部included，规则保持v2，本批独立审批。
- [ ] 在启动控制台按Ctrl+C；如询问终止批处理则输入Y。旧地址不再提供服务；再次启动后能浏览上述四次运行并下载旧导出。关闭浏览器不等于停止应用。
- [ ] 完整解压新原生ZIP到另一中文、空格目录，无源码、`.venv`、`node_modules`或私有`.env`；重复上述无key流程、Excel打开、停止与重启。

原生依赖隔离可在该目录的PowerShell中使用**本进程范围**PATH，不修改系统配置：

```powershell
$wheat_assistantOldPath = $env:PATH
try {
    $env:PATH = Join-Path $env:SystemRoot 'System32'
    .\wheat_assistant.exe --data-dir .\synthetic-data --port 8765 --strict-port
} finally {
    $env:PATH = $wheat_assistantOldPath
}
```

若端口被其他服务占用，选择空闲端口并记录；自动验收使用严格原端口重启。保留SystemRoot/WINDIR等系统环境，禁止清空所有系统变量。仅隔离PATH时，如实记录此方法，不能写成“在未安装Python/Node的全新系统验证”。

## 3. 交回内容与失败处理

交回本次目录内的五份JSON（总评、pytest、源码、原生、性能）、人工清单、必要的应用/Excel合成数据截图，以及新原生ZIP或单独明确其未附。失败提前停止时如实说明哪些报告尚未生成。通过PowerShell核对ZIP：

```powershell
Get-FileHash -Algorithm SHA256 .\dist\wheat_assistant-Windows-AMD64-v0.2.1.zip
```

原始控制台/浏览器轨迹及 `.runtime/windows-validation/`、`.runtime/release-private/`、`.runtime/benchmark-private/` 日志可能含私人目录，保留本机排查，未经脱敏不要分享。不要发送 `.env`、`synthetic-data`、实际运行数据库、`.git`、缓存或整个开发目录。

自动JSON中的 `manual_start_stop`、`manual_excel` 保持 `pending_operator_confirmation`；自动通过不能替代操作者回执或真人复核。失败时保留原始JSON，注明失败阶段/错误码/重现步骤；不要删除断言、放宽10秒目标、跳过步骤或覆盖失败报告。若安全软件阻止未签名开发包，记录错误，交给设备负责人处理；不关闭系统保护。
