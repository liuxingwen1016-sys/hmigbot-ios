package com.fixture.app.api;

// 改编自真实工程 xiaoyibang app/.../api/ApiPath.java（去业务化改值；形状保真：
// Java 接口体常量 `String X = "...";`、**无前导斜杠**、路径模板 {param}、javadoc 夹行）。
// D-B 缺陷锚素材：候选 scanner 常量解析只认 Kotlin val/const val，Java 接口体形态全漏；
// 且 url_constants 的 path-style 过滤只认前导 `/`（真实工程路径无前导斜杠）—— 双阻塞。

/**
 * 接口路径常量（改编）
 */
public interface ApiPath {

    /**
     * 发送短信
     */
    String SEND_SMS_CODE = "examinee/v5/sms/authcode";
    /** 获取首页的学校列表 */
    String GET_SCHOOL_LIST = "examinee/v5/enroll/college";
    /** 获取实人认证的结果 */
    String GET_VERIFY_RESULT = "examinee/v5/user/describeVerify/{bizId}";
    /** 抽题预览 */
    String GET_SUBJECT_QUESTION_PREVIEW = "examinee/v5/exam/previewQuestion/{branchId}/{subjectId}";
}
