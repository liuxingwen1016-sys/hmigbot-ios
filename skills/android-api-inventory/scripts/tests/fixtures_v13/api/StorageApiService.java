package com.fixture.solfeggio.repository.service;

// 改编自真实工程 xiaoyibang ZGSolfeggioKit .../repository/service/ApiService.java
// （去业务化重命名）：最小 @Url 动态端点接口 —— 裸注解 + 单 @Url 参数。

import io.reactivex.Observable;
import retrofit2.http.GET;
import retrofit2.http.Url;

/**
 * 存储凭证接口（改编）
 */
public interface StorageApiService {

    @GET
    Observable<CommonResp<OssStub>> fetchStorageToken(@Url String url);
}
