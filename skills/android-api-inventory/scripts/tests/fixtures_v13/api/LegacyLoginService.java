package com.fixture.app.api;

// synthetic：真实工程 xiaoyibang 未使用 Call+FormUrlEncoded 形态（全站 RxJava Observable），
// 此文件为声明兼容探针 —— 保 Java @Field 表单参数 + Call 泛型返回 + 多行签名可抽。

import retrofit2.Call;
import retrofit2.http.Field;
import retrofit2.http.FormUrlEncoded;
import retrofit2.http.POST;

public interface LegacyLoginService {

    @FormUrlEncoded
    @POST("/auth/v2/login")
    Call<LoginResp> login(@Field("mobile") String mobile,
                          @Field("password") String password,
                          @Field("loginType") int loginType);
}
