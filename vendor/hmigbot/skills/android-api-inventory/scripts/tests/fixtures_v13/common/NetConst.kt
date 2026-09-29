package com.fixture.app.common

// 改编自真实工程 xiaoyibang ApiConst/Constant 语义（转写为 Kotlin 形态）：
// 环境 base 地址字面量 + BuildConfig 动态拼接 + 路径常量对象。

import com.fixture.app.BuildConfig

object NetEnv {
    // 开发/联调环境（debug）
    val debugApiUrl = "http://stub-collegeserver.enrollhub-test.cn/"
    // 生产环境（release）
    val releaseApiUrl = "https://api.enrollhub.cn/"
    // 由 BuildConfig 注入的动态拼接 base（三环境切换语义，来自真实 app/build.gradle API_ENV）
    val BASE_URL = BuildConfig.API_ENV + "college/"
}

object CourseUrl {
    const val DETAIL = "/course/detail"
    const val LIST = "/course/list"
}
