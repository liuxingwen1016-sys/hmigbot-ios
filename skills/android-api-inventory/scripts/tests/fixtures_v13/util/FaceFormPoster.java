package com.fixture.app.util;

// 改编自真实工程 xiaoyibang util/FaceComparator.java 的 FormBody 组装形状（去业务化）。
// 真实工程为循环 add 变量键（静态不可抽），此处按字面量链式 add 改编；
// 保留真实的 Charset 构造参数与末位签名字段形状。

import java.nio.charset.StandardCharsets;

import okhttp3.FormBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class FaceFormPoster {

    public Response postCompareForm(OkHttpClient client, String orderNo, String faceImageUrl) {
        RequestBody formBody = new FormBody.Builder(StandardCharsets.UTF_8)
                .add("orderNo", orderNo)
                .add("faceImage", faceImageUrl)
                .add("sceneCode", "face_compare")
                .add("Signature", SignUtil.hmacSha256(orderNo))
                .build();
        Request request = new Request.Builder()
                .url("https://verify.enrollhub.cn/face/compare")
                .post(formBody)
                .build();
        return client.newCall(request).execute();
    }
}
