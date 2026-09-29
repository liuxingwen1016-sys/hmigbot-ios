package com.fixture.app.net;

// 改编自真实工程 xiaoyibang app/.../util/TokenInterceptor.java（去业务化）：
// 请求头注入会话凭证 + 响应体读取解析 + 失效码判定后发事件强制退出。
// （真实工程用 Constant.TOKEN 常量引用，此处按真实 Constant.java 的值内联字面量。）

import java.io.IOException;
import java.nio.charset.Charset;

import org.json.JSONObject;

import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;
import okio.Buffer;
import okio.BufferedSource;

public class AuthTokenInterceptor implements Interceptor {

    private static final Charset UTF8 = Charset.forName("UTF-8");
    private static final String CODE_SESSION_EXPIRED = "000";
    private static final String CODE_UNAUTHORIZED = "401";

    @Override
    public Response intercept(Chain chain) throws IOException {
        Request originalRequest = chain.request();
        Request newRequest = originalRequest.newBuilder()
                .addHeader("token", SessionStore.getToken())
                .build();
        return checkToken(chain.proceed(newRequest));
    }

    private Response checkToken(Response response) {
        try {
            ResponseBody responseBody = response.body();
            BufferedSource source = responseBody.source();
            source.request(Long.MAX_VALUE);
            Buffer cache = source.buffer();
            String bodyString = cache.clone().readString(UTF8);
            JSONObject jsonObject = new JSONObject(bodyString);
            String code = jsonObject.optString("code");
            if (code.equals(CODE_SESSION_EXPIRED) || code.equals(CODE_UNAUTHORIZED)) {
                if (SessionStore.isActive()) {
                    BusFactory.getBus().post(new ForceLogoutEvent());
                }
            }
            return response;
        } catch (Exception e) {
            LogStub.e(getClass(), "checkToken--->" + e.getMessage());
        }
        return response;
    }
}
