package com.fixture.app.net

// synthetic（Kotlin 冒号继承形态探针）：真实工程 xiaoyibang 拦截器全为 Java implements
// 形态；本文件语义改编自公共请求头注入场景，验证 Kotlin 冒号继承实现类可抽，
// 且 evidence 仅命中请求头写入一项。

import okhttp3.Interceptor
import okhttp3.Response

class ChannelHeaderInterceptor(private val channel: String) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val decorated = chain.request().newBuilder()
            .addHeader("X-Channel", channel)
            .addHeader("X-Client-Version", VersionInfo.NAME)
            .build()
        return chain.proceed(decorated)
    }
}
