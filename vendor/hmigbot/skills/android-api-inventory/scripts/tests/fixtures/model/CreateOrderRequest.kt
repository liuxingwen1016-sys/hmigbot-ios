package com.example.model

/**
 * #4 的证物：createOrder 的真实请求契约字段全在这里（productId/quantity/...），
 * 但 extract_android_apis.py 只记 `request: CreateOrderRequest` 一个参、不打开本类。
 * 这 5 个字段 = 生产中漂移/漏的真契约，抽取器完全看不到。
 */
data class CreateOrderRequest(
    val productId: String,
    val quantity: Int,
    val couponId: String?,
    val addressId: String,
    val remark: String
)
