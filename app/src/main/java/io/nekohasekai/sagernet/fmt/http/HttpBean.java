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
 *     └─ 含 type/host/path/security 等，type="http" 时走 http 分支写入 host+path
 *   [string username]
 *   [string password]
 *   [boolean delHost]          — KunBox 新增，v0 旧数据无此字段
 *
 * 兼容性：
 *   - 新代码读旧数据：delHost 字段不存在时 readBoolean 返回 false（Kryo buffer 到尾部返回 0）
 *   - 旧代码读新数据：尾部多出 1 字节 boolean 被忽略，不影响父类字段读取
 *
 * 注意：path 已在父类 StandardV2RayBean 中处理，本类不重复写入。
 */
@SuppressWarnings("unchecked")
public class HttpBean extends StandardV2RayBean {

    public String username;
    public String password;
    public Boolean delHost;

    @Override
    public void initializeDefaultValues() {
        super.initializeDefaultValues();
        if (username == null) username = "";
        if (password == null) password = "";
        if (delHost == null) delHost = false;
    }

    /**
     * 序列化：父类全部字段 → username → password → delHost。
     * 不写本类版本号（保持与已有数据格式一致）。
     * path/host 由父类在 type="http" 分支处理，此处不重复。
     */
    @Override
    public void serialize(ByteBufferOutput output) {
        super.serialize(output);
        output.writeString(username);
        output.writeString(password);
        output.writeBoolean(delHost != null && delHost);
    }

    /**
     * 反序列化：父类全部字段 → username → password → delHost。
     *
     * delHost 用 try-catch 兜底：
     *   - 旧数据无 delHost → readBoolean 在 buffer 尾部返回 false，或抛异常被 catch 兜底
     *   - 新数据有 delHost → 正常读取
     * 这是向后兼容的标准做法，避免给格式加版本号导致旧代码无法读新数据。
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
     * CREATOR：使用基类 Serializable.Creator。
     * 基类已实现 createFromParcel = KryoConverters.deserialize(newInstance(), bytes)，
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
