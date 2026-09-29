package com.fixture.app.common;

// 改编自真实工程 xiaoyibang util/Constant.java（去业务化）：字符串失效码（真实后端
// code 为 String："000"/"401"）+ 数值踢出码（synthetic 附加，对应 code 桶数值形态）。
// D-B 缺陷锚素材：Java 接口体常量应进 api_related_constants（数值→code 桶）。

public interface Constant {

    /** token 失效 */
    String TOKEN_INVALIDATE = "000";
    /** token 失效（网关层） */
    String TOKEN_INVALIDATE_MSG = "401";
    /** 强制下线事件码（synthetic：数值形态） */
    int CODE_KICK_OUT = -1001;
}
