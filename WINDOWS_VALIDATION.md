# Windows x64 验证交接（0.2.0）

本包是源码，Windows 原生包必须在 Windows 上构建。本轮开发机为 macOS arm64；下列 Windows 项目目前均为待验证，不能以脚本或 CI 配置代替实际通过。演示仅含合成数据，Orbyte 为模拟。

## 1. 首次安装

1. 将源码 ZIP **完整解压**到本地目录，可选带空格和中文的目录，例如 `C:\MaiZi 验证\MaiZi_Assistant`。不要在压缩包预览中运行。
2. 安装 Python 环境管理器 uv 和 Node.js 22+（含 npm），重新打开终端。首次安装需要联网，uv 会按锁文件准备 Python 3.12 与依赖。
3. 双击 `Setup_Windows.bat`，应显示 `Setup complete`；再运行一次，确认既有 `.env` 不被覆盖。不需要填 API key。
4. 双击 `Validate_Windows.bat`。它会运行全部 Python 测试、TypeScript／生产构建、无 key 的源码三周 HTTP 流程，构建本机原生 ZIP，并独立解压到带中文和空格的新目录，验证原生三周流程、停止及端口释放。不会调用模型或上传结果。

自动结果应在 `output/verification/windows-validation.json` 显示 `passed: true`，五个步骤均通过。另有 `windows-source-release.json` 和 `windows-native-release.json`，两份均应 `passed: true`、`ai_calls: 0`、`stop_and_port_release: true`。全量 Python 测试数量及最终版本以 `ACCEPTANCE.md` 为准。

## 2. 人工首次启动、停止与重启

请逐项保留真实结果，失败时记录操作与界面错误，不勾选未执行项。

- [ ] `Start_MaiZi.bat` 自动打开本地网页，未配置 key 也能使用。
- [ ] 点击 `01 Configure`，手动确认 `Jasmine500 → TEA-001` 和 `carton → box`；检查六组规则、执行。结果为 36 = 24 included + 3 excluded + 3 duplicate + 6 exception。
- [ ] 查看异常原值及处理轨迹；确认异常后导出，Excel 可打开八张表。商品数量为 TEA-001 21、SOAP-002 33、RICE-003 84。
- [ ] `02 Catch a change` 明确复用上次版本；`channel-b` 的 `Partially shipped` 保持待处理，明确改为 Exclude 后重新检查与六组确认；结果为 39 = 24 + 6 + 3 + 6。
- [ ] `03 Reuse` 复用兼容版本；结果 24 行全部 included，规则版本不增加，本批仍独立审批。
- [ ] 在启动控制台按 Ctrl+C；若询问终止批处理，输入 Y。原地址不再提供服务；再次启动可读到旧结果并下载旧导出。关闭浏览器本身不会停止服务。
- [ ] 解压新生成的 `dist/MaiZi-Windows-AMD64-v0.2.0.zip`，在未带源码、`.venv`、Node 或私有 `.env` 的另一目录启动 `MaiZi.exe`，重复无 key 演示。自动独立解压测试会先执行一次相同核心路径。
- [ ] 记录 Windows 版本、x64 架构、安装与人工测试结果、失败步骤，以及本机生成 ZIP 的 SHA-256。不发送用户名、机器名、私人目录或密钥。

## 3. 交回证据

交回三份 JSON、上述人工勾选结果，以及出现问题时的**脱敏**界面错误即可。自动报告含原生包 SHA-256；如另需计算，可在 PowerShell 使用 `Get-FileHash -Algorithm SHA256 .\dist\MaiZi-Windows-AMD64-v0.2.0.zip`。

详细日志 `.runtime/windows-validation-private.log` 可能含本机私人路径，先保留本机排查，不直接分享。不要发送 `.env`、运行数据库、缓存或 `.git`。自动报告的 `manual_start_stop: pending_operator_confirmation` 只有收到人工回执后才能由验收负责人关闭。

遇到安装失败，按窗口具体错误修复后重跑；请勿删除已有业务目录。若安全软件阻止未签名开发包，记录错误并使用源码入口，交由设备负责人处理，不关闭系统安全保护。端口 8765 被占用时启动器会选择其他本地端口，以控制台输出为准。
