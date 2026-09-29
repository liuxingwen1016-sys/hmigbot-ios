package com.fixture.app.biz;

// 改编自真实工程 xiaoyibang biz/UserLoader.java（去业务化）：Repository 装配层，
// 作为端点调用点回溯素材。注意：请求体组装用 Gson JsonObject.addProperty ——
// 真实工程主流模式（skill 文档三模式之外），用作 scanner 覆盖缺口的 advisory 探针
// （只报告不计入硬门）。

import com.fixture.app.api.EnrollApiService;
import com.fixture.app.api.LegacyLoginService;

import io.reactivex.Observable;
import retrofit2.HttpException;

public class AccountLoader {

    private EnrollApiService mApiService;
    private LegacyLoginService mLoginService;

    public Observable<CommonResp<SmsPojo>> sendSms(String mobile, int smsType) {
        JsonObject jsonObject = new JsonObject();
        jsonObject.addProperty("phoneNumber", CipherTools.encode(mobile));
        jsonObject.addProperty("smsType", smsType);
        return observe(mApiService.sendSmsCode(jsonObject));
    }

    public Observable<LoginResult> loginByPwd(String mobile, String password, int type) {
        return observe(mLoginService.login(CipherTools.encode(mobile), CipherTools.encode(password), type));
    }

    public Observable<LoginResult> loginByCode(String mobile, String code, int type) {
        return observe(mLoginService.login(CipherTools.encode(mobile), CipherTools.encode(code), type));
    }

    public JsonObject buildLoginPayload(String mobile, String password, int type) {
        JsonObject jsonObject = new JsonObject();
        jsonObject.addProperty("userAccount", CipherTools.encode(mobile));
        jsonObject.addProperty("password", CipherTools.encode(password));
        jsonObject.addProperty("loginType", type);
        jsonObject.addProperty("decodeType", 1);
        return jsonObject;
    }

    private <T> Observable<T> observe(Observable<T> source) {
        return source;
    }
}
