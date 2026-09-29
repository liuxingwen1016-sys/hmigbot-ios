package com.fixture.app.api;

// 改编自真实工程 xiaoyibang app/.../api/ApiConst.java（去业务化）：
// `public static final String` 形态 —— 硬编码第三方 base URL + BuildConfig 注入拼接 +
// Domain-Name 路由 header 值常量 + 字符串状态码。D-B 缺陷锚素材。
// 注：真实名 URL_LOCATION；此处取 API_URL 使 base_urls 锚只考 Java 声明车道
// （全大写 *_URL 命名过滤是另一层，不在本锚混入）。

import com.fixture.app.BuildConfig;

public class ApiConst {

    /** 因为后端返回的code是String类型 */
    public static final String SUC_CODE = "200";

    public static final String API_URL = "https://restapi.amap.com/";
    public static final String BASE_H5_URL = BuildConfig.API_ENV + "h5/";

    public static final String DOMAIN_NAME_LOCATION = "location";
    public static final String DOMAIN_NAME_DYNAMIC = "dynamic";
}
