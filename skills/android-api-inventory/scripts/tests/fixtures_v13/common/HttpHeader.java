package com.fixture.app.common;

// 改编自真实工程 xiaoyibang util/Constant.java 的 TOKEN 段（去业务化：容器改名
// HttpHeader，与 scanner 声明文档自带示例 `HttpHeader.TOKEN = "token"` 同形）。
// D-B 缺陷锚素材：Java 接口体 String 常量应进 api_related_constants 的 header 桶。

public interface HttpHeader {

    /** 会话凭证请求头名 */
    String TOKEN = "token";
    /** 渠道请求头名 */
    String CLIENT_HEADER_CHANNEL = "x-channel";
}
