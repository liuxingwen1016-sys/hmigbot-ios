package com.example.api

import retrofit2.http.*

/**
 * 判别性 fixture — 测 #1「>15 行签名截断」。
 * sendSmsCode = 基线对照（短签名，应干净抽取）；
 * register = 16 个 @Field 一行一个，签名跨 ~18 行，超出脚本 i+15 窗口。
 */
interface AuthApiService {

    // ── 基线对照：短签名，应抽出 2 参 ──
    @FormUrlEncoded
    @POST("/auth/sendSmsCode")
    suspend fun sendSmsCode(
        @Field("mobile") mobile: String,
        @Field("bizType") bizType: Int
    ): BaseResponse<Unit>

    // ── #1 KILLER：16 参一行一个，闭括号在窗口外 ──
    @FormUrlEncoded
    @POST("/auth/register")
    suspend fun register(
        @Field("username") username: String,
        @Field("password") password: String,
        @Field("mobile") mobile: String,
        @Field("smsCode") smsCode: String,
        @Field("nickname") nickname: String,
        @Field("avatar") avatar: String,
        @Field("gender") gender: Int,
        @Field("birthday") birthday: String,
        @Field("city") city: String,
        @Field("channel") channel: String,
        @Field("deviceId") deviceId: String,
        @Field("inviteCode") inviteCode: String,
        @Field("appVersion") appVersion: String,
        @Field("osType") osType: Int,
        @Field("infoSource") infoSource: String,
        @Field("registerType") registerType: Int
    ): BaseResponse<UserData>
}
