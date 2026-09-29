# SwiftSyntax provider

官方依赖：[swiftlang/swift-syntax](https://github.com/swiftlang/swift-syntax)。SwiftSyntax 解析语法，不解析跨模块类型绑定；本 provider 不执行传入的 App 源码。

源代码可通过 Swift 6.0 工具链 `swift build -c release` 构建，Package.swift 固定 SwiftSyntax 600.0.1。修改工具链时应同步核对 SwiftSyntax 版本。SwiftPM 构建需要取得依赖；本次实际验证使用已有 Swift 6.0.3 工具链随附的 SwiftSyntax/SwiftParser 库解释执行 main.swift，记录在验证报告中，不将其他平台的构建方式视为已验证。

复制 provider.example.json，填写实际可执行文件及 Swift 版本命令，然后传入 `atom swift-syntax --provider-config <file>`。配置为参数数组，不拼接 shell 命令。可使用 Mac、本机 Linux 或显式配置的 WSL 调用；本地 WSL 的运行路径保存在 work，未硬编码到分发代码。

协议：stdin 为 UTF-8 JSON `files[{path,sha256,source}]`；stdout 为协议版本 1 的 JSON。输出包括声明、函数、变量、调用、属性和编译条件及 UTF-8 范围、行列、解析诊断。source hash/文件集合/位置检查均通过后才接受输出。语法错误保留为 partial；不计作已解析的有效 App。源码编译、宏展开、活跃编译条件、类型与调用绑定仍需 Xcode/SourceKit。
