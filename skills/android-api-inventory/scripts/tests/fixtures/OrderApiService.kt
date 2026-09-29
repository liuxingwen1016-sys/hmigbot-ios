package com.example.api

import retrofit2.http.*
import com.example.model.CreateOrderRequest
import com.example.model.CancelOrderRequest

/**
 * 判别性 fixture — 测 #4 @Body DTO 内部字段无人展开 + #6 @HTTP 自定义方法 +
 * const-ref 路径解析（基线，应正常 resolve）。
 */
interface OrderApiService {

    // ── 基线：const-ref 路径应 resolve 到 /order/create；@Body DTO 字段是真契约但脚本不展开 ──
    @POST(OrderUrl.CREATE)
    suspend fun createOrder(
        @Body request: CreateOrderRequest,
        @Header("token") token: String
    ): BaseResponse<OrderData>

    // ── #6 @HTTP 自定义 DELETE（带 body）──
    @HTTP(method = "DELETE", path = "/order/cancel", hasBody = true)
    suspend fun cancelOrder(
        @Body request: CancelOrderRequest
    ): BaseResponse<Unit>
}

object OrderUrl {
    const val CREATE = "/order/create"
}
