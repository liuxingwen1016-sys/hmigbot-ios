package com.fixture.app.util;

// 改编自真实工程 xiaoyibang util/ExamRecordHelper.java 的 org.json 组装形状
// （去业务化；异常处理省略）：上报载荷字段在 Retrofit 接口之外组装（pitfall D3 场景）。

import org.json.JSONObject;

import okhttp3.MediaType;
import okhttp3.RequestBody;

public class TrackHelper {

    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");

    public static RequestBody buildTracePayload(String examId, String action, long costMs) {
        JSONObject payload = new JSONObject();
        payload.put("examId", examId);
        payload.put("action", action);
        payload.put("costMs", costMs);
        payload.put("osType", 2);
        return RequestBody.create(JSON, payload.toString());
    }
}
