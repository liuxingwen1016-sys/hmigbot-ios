# 上游来源与派生改动

本工具基于用户提供的独立 HMigBot CodeX 1.6.1，作者元数据为 fuxi-ailabs，仓库元数据为 https://github.com/fuxi-ailabs/hmigbot-CodeX 。不是 HMigBot Plus。

[原插件清单](upstream/.codex-plugin/plugin.json)声明 license 为 MIT；本机发行目录未发现独立 LICENSE 正文，因此此处如实保留来源和原声明，不代替上游补写授权。原 README、CHANGELOG、安装/配置/调度材料保存在 docs/upstream 中供比对，不作为本版本安装入口。

[导入清单](upstream/import-manifest.json)逐文件记录导入时的路径、大小和 SHA256；忽略的仅为文件系统元数据及构建缓存（如 .DS_Store、._*、__pycache__），不删校验器依赖。[派生修改清单](upstream/derivative-manifest.json)记录当前内容相对导入基线的变化。

原 99 份技能、31 份角色与依赖完整位于 vendor/hmigbot，3,516 文件与导入基线 SHA256 一致。
启用层为 96 技能、29 角色：退出 10 个原源专用技能和 4 个源角色，增加 7 个 iOS 技能和 2 个 iOS 角色，
复用目标规程并改写其源输入。启用入口使用通用 source_anchors 与 ios-semantics，原二进制及平台限制保留。
vendor 不在插件发现路径；旧平台词汇属于真实原文和来源记录，不能通过改写归档伪造原始来源。

完整资源安装到工作区，原目录可完全不在另一台机器上。运行时不读取上述来源路径；仓库地址只是溯源信息。
