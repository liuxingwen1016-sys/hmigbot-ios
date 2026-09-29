package com.fixture.app.api;

// 改编自真实工程 xiaoyibang app/src/main/java/com/zego/davinci/api/ApiService.java
// （去业务化重命名；形状保真：RxJava2 Observable 返回 + @Headers 常量拼接花括号数组 +
//   ApiPath 常量路径引用 + 裸注解 + @HeaderMap/@Url 动态端点 + 多行参数对齐签名）。

import java.util.List;
import java.util.Map;

import io.reactivex.Observable;
import okhttp3.RequestBody;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.HeaderMap;
import retrofit2.http.Headers;
import retrofit2.http.POST;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import retrofit2.http.Query;
import retrofit2.http.Url;

/**
 * api接口（改编）
 */
public interface EnrollApiService {

    /** 发送短信；花括号数组 + 常量拼接形态的静态注解 */
    @Headers({"Domain-Name: " + ApiConst.DOMAIN_NAME_DYNAMIC})
    @POST(ApiPath.SEND_SMS_CODE)
    Observable<CommonResp<SmsPojo>> sendSmsCode(@Body JsonObject jsonObject);

    /** 获取首页的学校列表；单行长签名，3 个查询参数 */
    @Headers({"Domain-Name: " + ApiConst.DOMAIN_NAME_DYNAMIC})
    @GET(ApiPath.GET_SCHOOL_LIST)
    Observable<CommonResp<SchoolPagePojo>> getSchoolList(@Query("collegeCategory") String collegeCategory, @Query("pageSize") int pageSize, @Query("pageNum") int pageNum);

    /** 获取实人认证的结果；单串形式静态注解（无花括号） */
    @Headers("Cache-Control: no-cache")
    @PUT(ApiPath.GET_VERIFY_RESULT)
    Observable<CommonResp<UserPojo>> getVerifyResult(@Path("bizId") String bizId);

    /** 抽题预览；多行 Java 签名（参数换行对齐）+ 花括号纯字面量多值静态注解 */
    @Headers({"Accept: application/json", "X-Api-Version: 2"})
    @GET(ApiPath.GET_SUBJECT_QUESTION_PREVIEW)
    Observable<CommonResp<SubjectQuestionInfo>> getPreviewSubjectQuestion(@Path("branchId") String branchId,
                                                                          @Path("subjectId") String subjectId);

    /** desc 异步申请考试：裸注解 + @HeaderMap + @Url + @Body */
    @POST
    Observable<CommonResp<String>> applyExamAsync(@HeaderMap Map<String, String> headers, @Url String url, @Body JsonObject body);

    /** desc 轮询异步申请考试结果：裸注解 + @HeaderMap + @Url */
    @GET
    Observable<CommonResp<String>> pollApplyResult(@HeaderMap Map<String, Object> map, @Url String url);
}
