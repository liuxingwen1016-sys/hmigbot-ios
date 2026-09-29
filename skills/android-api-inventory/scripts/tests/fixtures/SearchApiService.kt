package com.example.api

import retrofit2.http.*

/**
 * 判别性 fixture — 测 #3 vararg 漏抓 + #2 generic 类型逗号截断。
 * searchItems 里 infoSource 是普通 @Query（应抽到），ids 是 vararg（预测漏）。
 */
interface SearchApiService {

    // ── #3 vararg + 易漏 @Query（infoSource 此处是普通参、应抽到）──
    @GET("/search/items")
    suspend fun searchItems(
        @Query("keyword") keyword: String,
        @Query("infoSource") infoSource: String,
        @Query("ids") vararg ids: Long
    ): BaseResponse<List<Item>>

    // ── #2 @QueryMap 泛型类型含逗号 ──
    @GET("/search/filter")
    suspend fun filter(
        @QueryMap filters: Map<String, String>,
        @Query("page") page: Int
    ): BaseResponse<List<Item>>
}
