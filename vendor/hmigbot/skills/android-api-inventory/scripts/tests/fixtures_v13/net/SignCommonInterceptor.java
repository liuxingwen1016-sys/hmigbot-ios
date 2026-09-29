package com.fixture.app.net;

// 改编自真实工程 xiaoyibang comLib/.../net/HttpCommonInterceptor.java（去业务化）：
// 公共请求头注入（公参 map 遍历写 header）+ 短信接口 MD5 加签（authSign）。
// 含 Builder 内部类（同真实形状）。

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.Response;

public class SignCommonInterceptor implements Interceptor {

    private Map<String, String> commonParamsMap = new HashMap<>();

    @Override
    public Response intercept(Chain chain) throws IOException {
        Request oldRequest = chain.request();
        Request.Builder requestBuilder = oldRequest.newBuilder();
        requestBuilder.method(oldRequest.method(), oldRequest.body());

        if (commonParamsMap.size() > 0) {
            String nonceStr = String.valueOf(System.currentTimeMillis() % 100000);
            for (Map.Entry<String, String> params : commonParamsMap.entrySet()) {
                requestBuilder.header(params.getKey(), params.getValue());
                if ("nonceStr".equals(params.getKey())) {
                    nonceStr = params.getValue();
                }
            }
            addSmsAuthHeader(requestBuilder, nonceStr);
        }
        Request newRequest = requestBuilder.build();
        return chain.proceed(newRequest);
    }

    private void addSmsAuthHeader(Request.Builder requestBuilder, String nonceStr) {
        String stringToHash = "nonceStr=" + nonceStr + "&key=fixture.enrollhub";
        String authSign = HashUtil.getMd5HexStr(stringToHash);
        requestBuilder.addHeader("authSign", authSign);
    }

    public static class Builder {
        SignCommonInterceptor target;

        public Builder() {
            target = new SignCommonInterceptor();
        }

        public Builder addHeaderParams(String key, String value) {
            target.commonParamsMap.put(key, value);
            return this;
        }

        public SignCommonInterceptor build() {
            return target;
        }
    }
}
