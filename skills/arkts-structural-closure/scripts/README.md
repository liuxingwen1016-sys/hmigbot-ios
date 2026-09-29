# 结构 helper

调用前读取上级 SKILL.md。structural_loop.py 是带 iOS 图片前置检查的入口，
其他目标检测器调用包内原 HMigBot 实现；不存在自动调用 LLM 的脚本。
state/result 由真实检查写入。helper 出错或不支持当前平台时保留未验证状态。
