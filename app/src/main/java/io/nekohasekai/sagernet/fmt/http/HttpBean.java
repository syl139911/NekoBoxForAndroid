package io.nekohasekai.sagernet.fmt.http;

import androidx.annotation.NonNull;

import com.esotericsoftware.kryo.io.ByteBufferInput;
import com.esotericsoftware.kryo.io.ByteBufferOutput;

import org.jetbrains.annotations.NotNull;

import io.nekohasekai.sagernet.fmt.KryoConverters;
import io.nekohasekai.sagernet.fmt.Serializable;
import io.nekohasekai.sagernet.fmt.v2ray.StandardV2RayBean;

/**
 * HTTP 代理 Bean。
 *
 * 继承链：Serializable → AbstractBean → StandardV2RayBean → HttpBean
 *
 * 序列化格式（Kryo buffer）：
 *   [父类 StandardV2RayBean 全部内容]
 *     └─ type="http" 时走 http 分支写入 host+path
 *   [string username]
 *   [string password]
 *   [boolean delHost]
 *
 * ⚠️ type 必须在 super.initializeDefaultValues() 之前设为 "http"，
 *    否则父类会把它重置为 "tcp"，导致 serialize 走 tcp 分支不写 host/path，
 *    而 deserialize 走 http 分支读 host/path → 字段错位 → VPN 闪退。
 *
 * 兼容性：
 *   - 新代码读旧数据：delHost 不存在时 readBoolean 返回 false（Kryo buffer 尾部返回 0）
 *   - 旧代码读新数据：尾部多出 1 字节 boolean 被忽略
 *   - path/host 由父类在 type 分支中处理，本类不重复写入
 */
@SuppressWarnings("unchecked")
public class HttpBean extends StandardV2RayBean {

    public String username;
    public String password;
    public Boolean delHost;

    @Override
    public void initializeDefaultValues() {
        // ⚠️ 必须在 super 之前设好 type="http"
        // 父类 initializeDefaultValues() 里：if (type == null) type = "tcp"
        // 如果先调 super，type 会被设为 "tcp"，本类的 null 检查永远不会触发
        type = "http";  // 强制覆盖，不管原来是什么
        super.initializeDefaultValues();

        // 父类已处理 host/path 的 null 默认值（StandardV2RayBean.initializeDefaultValues）
        // 这里只处理本类字段
        if (username == null) username = "";
        if (password == null) password = "";
        if (delHost == null) delHost = false;
    }

    /**
     * 序列化：父类写完后追加 username/password/delHost。
     * 因为 type 已在 initializeDefaultValues 中固定为 "http"，
     * 父类 serialize 的 switch(type) 一定走 http 分支写入 host+path。
     */
    @Override
    public void serialize(ByteBufferOutput output) {
        super.serialize(output);
        output.writeString(username);
        output.writeString(password);
        output.writeBoolean(delHost != null && delHost);
    }

    /**
     * 反序列化：先读父类（含 type/host/path），再读 username/password/delHost。
     * delHost 用 try-catch 兼容旧数据（无此字段时 readBoolean 返回 false）。
     */
    @Override
    public void deserialize(ByteBufferInput input) {
        super.deserialize(input);
        username = input.readString();
        password = input.readString();
        try {
            delHost = input.readBoolean();
        } catch (Exception e) {
            delHost = false;
        }
    }

    @NotNull
    @Override
    public HttpBean clone() {
        return KryoConverters.deserialize(new HttpBean(), KryoConverters.serialize(this));
    }

    /**
     * CREATOR：使用基类 Serializable.Creator 的默认 createFromParcel，
     * 子类只需实现 newInstance 和 newArray。
     */
    public static final Serializable.Creator<HttpBean> CREATOR =
        new Serializable.Creator<HttpBean>() {
            @NonNull
            @Override
            public HttpBean newInstance() {
                return new HttpBean();
            }

            @Override
            public HttpBean[] newArray(int size) {
                return new HttpBean[size];
            }
        };
}