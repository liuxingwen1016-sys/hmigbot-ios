# Windows 原生运行说明（2026-08-15 起；2026-09-14 源侧收口）

> 本 skill 的全部脚本已是 Python（`scripts/*.py`），**Windows / macOS / Linux 跑的是同一份文件**，
> 无需 Git Bash / WSL。
>
> **2026-09-14 源侧收口**：此前 py 化只在 codex 产物侧完成，源侧 `.sh` 与 `.py` 并存；本轮把源侧最后
> 23 个 `.sh` 一并退役（`git rm`），文档、agent、跨 skill 调用点、`subprocess` 调用一律改指 `.py`。
> 所以**现在这份说明对源侧与 codex 产物同样成立**，不再有"以哪一份为准"的问题。
> 退役前的 `.sh` 侧行为已固化成 golden（`scripts/_tests/fixtures/golden_sh_0914/`，套件每次跑都比），
> 要看原文：`git show 915_vvSpeed:arkts-skills/skills/arkts-visual-verify/scripts/<name>.sh`。
>
> ## ⚠️ 正常情况下**不需要任何前置步骤**——直接跑就行
>
> 编码、临时目录、路径分隔、工具定位全部由代码自愈（`lib_tools.py` + 全量 `encoding="utf-8"`）。
> 本页余下内容是**排障手册**，只在预检报错时才需要看。

## 1. 可选预检（30 秒，想确认环境时跑）

```powershell
python <SKILLS_ROOT>\arkts-visual-verify\scripts\lib_tools.py
```

输出里 `hdc` / `adb` / `hvigorw` 应是真实路径。若某项显示裸名（`"hdc"` 而不是完整路径），说明该工具
既不在 PATH、也不在本平台默认安装位——按第 2 节补一个环境变量即可。**全是真实路径 = 无需任何设置，直接开跑。**

## 2. 仅在预检报裸名时才需要（PowerShell 当前会话；持久化用「系统属性→环境变量」）

```powershell
$env:HDC = "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe"
$env:ADB = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$env:DEVECO_HOME = "C:\Program Files\Huawei\DevEco Studio"   # hvigorw.bat 定位（自动重编/装机脚本才用）
```

`lib_tools` 的查找顺序是 **env > PATH > 本平台默认安装位候选表**，所以把工具加进 PATH 与设 env 等效。

## 3. Python 解释器名

Windows 上通常只有 `python`（或 `py`），没有 `python3`。文档里的 `python3 xxx.py` 在 Windows 读作 `python xxx.py`；
**脚本之间互相调用一律用 `sys.executable`，不受此影响**。唯一第三方依赖：`python -m pip install Pillow`
（长图拼接可选 `opencv-python`）。

## 4. 编码：已在代码里解决，不需要设 `PYTHONUTF8`

早期版本要求设 `PYTHONUTF8=1`，**现已取消**：
- 全部文件读写显式 `encoding="utf-8"`（165 处机械补齐，AST 精确插入 + 全量编译与对拍回归验证）；
- `subprocess(text=True)` 一律带 `encoding="utf-8", errors="replace"`（解析 adb/hdc 输出的中文 XML）；
- Windows 上 stdout/stderr 在脚本入口自动 `reconfigure(encoding="utf-8")`（72 个入口脚本 + `lib_tools`），
  解决"输出被管道捕获时按 cp936 编码崩"——本 skill 的脚本大量互相 subprocess 调用，这是常态路径。

**设计原则**：能焊进代码的就不写进文档。靠人记得设环境变量 = 把机械问题降级成自觉，这在本项目是明确的反模式。

## 5. 平台差异全表（均已在代码内处理，列此供排障）

| 面 | macOS/Linux | Windows | 处理点 |
|---|---|---|---|
| 工具定位 | `/Applications/DevEco-Studio.app/…`、`~/Library/Android/sdk` | `C:\Program Files\Huawei\DevEco Studio`、`%LOCALAPPDATA%\Android\Sdk`、`.exe/.bat` | `lib_tools.find_hdc/find_adb/find_hvigorw` |
| 临时目录 | `/tmp` | `%TEMP%` | `tempfile.gettempdir()` |
| 文件编码 | UTF-8 默认 | cp936 默认 | 全量显式 `encoding="utf-8"` |
| 输出流编码 | UTF-8 | 管道时 cp936 | 入口 `reconfigure` 守卫 |
| 路径分隔 | `/` | `\` | `os.path.join` / `pathlib` |
| 执行位 | `chmod +x` 有意义 | 无此概念 | py 版不依赖 `-x` 判定（sh 版曾因此**静默跳闸**） |
| shell 一行式（jq/awk/sed/管道） | 有 | 无 | 全部落进 py；文档与代码零 `bash x.sh`（2026-09-14 源侧亦零残留，套件 `test_no_sh_left_in_scripts` 守着） |
| 图像处理 | Pillow / sips / ImageMagick | Pillow | `lib_image.py`（PIL 唯一后端） |

## 6. 已知限制

- `hdc shell` 子命令（`uitest dumpLayout` / `snapshot_display` / `hilog`）在设备侧执行，三平台一致。
- 模拟器本身的 Windows 版性能与网络桥接（`10.0.2.2` 代理等）不在本 skill 范围。
