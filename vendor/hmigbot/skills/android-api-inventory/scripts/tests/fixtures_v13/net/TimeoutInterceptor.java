package com.fixture.app.net;

// 改编自真实工程 xiaoyibang comLib/.../net/DynamicTimeoutInterceptor.java（去业务化）：
// 纯超时调节，无任何鉴权/加签/公参/响应体改写行为 —— evidence 标签负例。
// 同文件第二个实现类为改编附加（synthetic），验证同文件多实现抽取。

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.Response;

public class TimeoutInterceptor implements Interceptor {

    private static final int COMMON_API_TIME_OUT = 30;
    private static final int VERIFY_API_TIME_OUT = 60;

    private int apiTimeOut = COMMON_API_TIME_OUT;

    @Override
    public Response intercept(Chain chain) throws IOException {
        Request request = chain.request();
        String url = request.url().toString();
        apiTimeOut = url.contains("/verify/") ? VERIFY_API_TIME_OUT : COMMON_API_TIME_OUT;
        return chain.withConnectTimeout(apiTimeOut, TimeUnit.SECONDS)
                .withReadTimeout(apiTimeOut, TimeUnit.SECONDS)
                .withWriteTimeout(apiTimeOut, TimeUnit.SECONDS)
                .proceed(request);
    }
}

class SlowNetworkMarkInterceptor implements Interceptor {

    @Override
    public Response intercept(Chain chain) throws IOException {
        long startMs = System.currentTimeMillis();
        Response resp = chain.proceed(chain.request());
        long costMs = System.currentTimeMillis() - startMs;
        if (costMs > 5000L) {
            NetMetrics.markSlow(chain.request().url().host(), costMs);
        }
        return resp;
    }
}
