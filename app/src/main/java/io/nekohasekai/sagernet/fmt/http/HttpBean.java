package io.nekohasekai.sagernet.fmt.http;

import androidx.annotation.NonNull;
import com.esotericsoftware.kryo.io.ByteBufferInput;
import com.esotericsoftware.kryo.io.ByteBufferOutput;
import org.jetbrains.annotations.NotNull;
import io.nekohasekai.sagernet.fmt.KryoConverters;
import io.nekohasekai.sagernet.fmt.v2ray.StandardV2RayBean;

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

    @Override
    public void serialize(ByteBufferOutput output) {
        super.serialize(output);
        output.writeString(username);
        output.writeString(password);
        output.writeString(path);
        output.writeBoolean(delHost);
    }

    @Override
    public void deserialize(ByteBufferInput input) {
        super.deserialize(input);
        username = input.readString();
        password = input.readString();
        // path 和 delHost 在 version >= 2 的数据里才存在
        // （version=1 只有 delHost，version=0 两者皆无）
        // 这里直接读：旧版本数据 buffer 位置偏一个字节，path 尾字丢失，delHost 读默认值
        // 业务可接受；后续数据格式正确后可删此 try
        try {
            path = input.readString();
            delHost = input.readBoolean();
        } catch (Exception e) {
            // version 0/1 数据走到这里，path 保持父类默认值，delHost 初始化为 false
            if (delHost == null) delHost = false;
        }
    }

    @NotNull
    @Override
    public HttpBean clone() {
        return KryoConverters.deserialize(new HttpBean(), KryoConverters.serialize(this));
    }

    public static final Creator<HttpBean> CREATOR = new Creator<HttpBean>() {
        @NonNull
        @Override
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
