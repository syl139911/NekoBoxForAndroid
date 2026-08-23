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
 * 序列化格式（v4，type 固定为 "http"，父类 StandardV2RayBean 在 http 分支写入 host+path，此处不重复）：
 *   [父类 StandardV2RayBean v4 序列化的全部内容，包含 serverAddress/serverPort/type="http"/host/path/security/TLS...]
 * * 然后追加：
 *   - username (String)
 *   - password (String)
 *   - delHost (boolean)
 *
 * 反序列化：先走父类 StandardV2RayBean.deserialize（读完 serverAddress/serverPort/type/host/path/...），
 *          再读 username/password/delHost。path 已在父类读完，此处不再重复读。
 */
@SuppressWarnings("unchecked")
public class HttpBean extends StandardV2RayBean {

    public String username;
    public String password;
    public Boolean delHost;

    @Override
    public void initializeDefaultValues() {
        // 必须在 super 之前设好，否则父类会把 type 默认为 "tcp"，
        // 导致 serialize 时 switch(type) 走 tcp 分支不写 host/path，
        // path 在序列化→反序列化过程中丢失，VPN 闪退。
        if (type == null || type.isBlank()) type = "http";
        super.initializeDefaultValues();
        if (username == null) username = "";
        if (password == null) password = "";
        if (delHost == null) delHost = false;
    }

    /**
     * 序列化：先由父类 StandardV2RayBean 写 v4 完整内容（含 type=http 时的 host+path），
     * 再追加 username/password/delHost。
     * 注意：path 不在此处重复写入（父类已处理）。
     */
    @Override
    public void serialize(ByteBufferOutput output) {
        super.serialize(output);
        output.writeString(username);
        output.writeString(password);
        // delHost: v1 及以上格式才有，写在最后以便反序列化检测
        output.writeBoolean(delHost != null && delHost);
    }

    /**
     * 反序列化：先由父类 StandardV2RayBean.deserialize 读完所有父类字段（包含 v4 的 host/path），
     * 再读 username/password/delHost。
     *
     * 兼容性处理：
     * - v0（最早的格式）：buffer 里 username 位置是 host，无 delHost。
     *   readString() 读到 host 内容（而非真正的 username），delHost 保持初始值 false。
     *   这是已知局限，v0 数据需要重新保存。
     * - v1 及以上：username/password/delHost 均正确读取。
     */
    @Override
    public void deserialize(ByteBufferInput input) {
        super.deserialize(input);
        username = input.readString();
        password = input.readString();
        // delHost 存在于 v1+，v0 数据读到的是 buffer 尾随垃圾，抛异常被 catch 忽略
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

    public static final Serializable.Creator<HttpBean> CREATOR =
        new Serializable.Creator<HttpBean>() {
            @NonNull
            public HttpBean newInstance() {
                return new HttpBean();
            }

            @Override
            public HttpBean[] newArray(int size) {
                return new HttpBean[size];
            }

            @Override
            public HttpBean createFromParcel(@NonNull android.os.Parcel parcel) {
                return KryoConverters.deserialize(newInstance(), parcel.createByteArray());
            }
        };
}
