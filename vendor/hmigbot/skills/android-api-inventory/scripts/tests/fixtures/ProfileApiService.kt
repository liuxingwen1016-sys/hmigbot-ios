package com.example.api

import retrofit2.http.*
import com.example.model.ProfileFilter

/**
 * 泛化 fixture（防止修法只贴合 register 单例）：
 * updateProfile = 18 参一行一个 + 中间夹空行/注释，跨 ~22 行（异于 register 的形）；
 * getProfile = @Path/@Query 混合 + nullable；
 * batchGet = 嵌套泛型 Map<String, List<String>>（测 #2 修法的一级嵌套）。
 */
interface ProfileApiService {

    @FormUrlEncoded
    @POST("/profile/update")
    suspend fun updateProfile(
        @Field("nickname") nickname: String,
        @Field("avatar") avatar: String,
        @Field("gender") gender: Int,
        @Field("birthday") birthday: String,
        @Field("signature") signature: String,
        // 基本信息
        @Field("city") city: String,
        @Field("province") province: String,
        @Field("country") country: String,

        @Field("company") company: String,
        @Field("position") position: String,
        @Field("school") school: String,
        @Field("industry") industry: String,
        @Field("website") website: String,
        @Field("email") email: String,
        @Field("phone") phone: String,
        @Field("wechat") wechat: String,
        @Field("weibo") weibo: String,
        @Field("tags") tags: String
    ): BaseResponse<Unit>

    @GET("/profile/{uid}")
    suspend fun getProfile(
        @Path("uid") uid: String,
        @Query("fields") fields: String?
    ): BaseResponse<ProfileData>

    @POST("/profile/batchGet")
    suspend fun batchGet(
        @Query("ids") ids: List<Long>,
        @Body filter: Map<String, List<String>>
    ): BaseResponse<List<ProfileData>>
}
