package com.fixture.app.api

// 改编：真实工程 xiaoyibang 无 Kotlin Retrofit 接口（全 Java+RxJava）；本文件把真实
// Java 端点形状转写为 Kotlin suspend 形态，验证 Kotlin 车道：多值静态注解（圆括号
// 多串）/ 裸注解 + @Url / 常量引用路径解析。

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Headers
import retrofit2.http.POST
import retrofit2.http.Query
import retrofit2.http.Url

interface CourseApiService {

    @Headers("Accept: application/json", "X-Client-Type: android")
    @GET("/course/list")
    suspend fun listCourses(@Query("categoryId") categoryId: String, @Query("pageNum") pageNum: Int): CourseListResp

    @GET(CourseUrl.DETAIL)
    suspend fun courseDetail(@Query("courseId") courseId: String): CourseDetailResp

    @POST
    suspend fun uploadTrace(@Url uploadUrl: String, @Body payload: TracePayload): CommonResp<String>
}
