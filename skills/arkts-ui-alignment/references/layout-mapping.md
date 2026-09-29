# 原生布局到 ArkUI

SwiftUI 以组合、modifier 顺序、alignment、layoutPriority、safe area 为输入；
UIKit 以约束 relation/priority、intrinsic size、hugging/compression、trait 为输入。
Column/Row/Stack/Flex/RelativeContainer 根据这些约束选型；不要机械固定坐标。
Stack 子项位置使用目标合法的布局/position/容器对齐方式，`.align()` 不是通用子项定位器。
point 与 vp、UIFont 与 fp 根据真实设备/字体缩放校验，不承诺无条件 1:1。
layout、绘制、命中区域分别对照；修复不能改变业务状态或遮挡可操作控件。
