package com.fixture.app.data

// 改编：真实工程 xiaoyibang 的请求体组装主流形态是 Gson JsonObject.addProperty
// （见 biz/AccountLoader.java 探针）；本文件用 skill 文档承诺的 mutableMapOf 模式
// 承载同语义（去业务化），并作为 Kotlin 侧端点调用点素材。

import okhttp3.RequestBody

import com.fixture.app.api.CourseApiService

class PaymentRepository(private val api: CourseApiService) {

    fun buildOrderBody(productId: String, quantity: Int, couponId: String?): MutableMap<String, Any?> {
        val body = mutableMapOf(
            "productId" to productId,
            "quantity" to quantity,
            "couponId" to couponId,
            "source" to 1,
            "channel" to "android"
        )
        return body
    }

    suspend fun refreshCourses(categoryId: String) {
        val resp = api.listCourses(categoryId, 1)
        CourseCache.store(resp)
    }
}
