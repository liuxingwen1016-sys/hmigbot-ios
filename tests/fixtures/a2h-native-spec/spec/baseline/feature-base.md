# Feature Base: 共享基础设施

source_platform: ios。基于单文件 CounterViewController.swift；此样例不包含 App 工程和其他模块。

## 数据模型
count: number = 0，整数范围 0–5；目标 CounterViewModel 持有。

## 数据库
源单元没有持久化语句；不为本样例引入数据库。

## 网络层
源单元没有网络调用；不虚构 API 或 HttpClient。

## 事件系统
UIKit target-action 对应页面按钮事件；没有源通知订阅。

## 偏好设置
源单元没有偏好存储；退出页面后状态生命周期需以宿主装配事实为准。

## 权限声明
所读单元无系统权限请求；未推断完整 App 的权限。

## 公共组件库
本单元没有共享组件；Count 标签和两个按钮为本页所有。

## 跨栈映射基线
UIKit UILabel/UIButton → ArkUI Text/Button；controller 中的页面计数状态 → @ObservedV2 CounterViewModel；目标 UI 按原 component-builder 的 V2 规程实施。
