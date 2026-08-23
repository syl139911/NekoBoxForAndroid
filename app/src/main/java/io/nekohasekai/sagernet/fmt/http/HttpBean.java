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
        output.writeInt(2);
        super.serialize(output);
        output.writeString(username);
        output.writeString(password);
        output.writeString(path);
        output.writeBoolean(delHost);
    }

    @Override
    public void deserialize(ByteBufferInput input) {
        int version = input.readInt();
        super.deserialize(input);
        username = input.readString();
        password = input.readString();
        if (version >= 2) {
            path = input.readString();
            delHost = input.readBoolean();
        } else if (version >= 1) {
            delHost = input.readBoolean();
        } else {
            delHost = false;
        }
    }

    @NotNull @Override
    public HttpBean clone() {
        return KryoConverters.deserialize(new HttpBean(), KryoConverters.serialize(this));
    }

    public static final Creator<HttpBean> CREATOR = new Creator<HttpBean>() {
        @NonNull @Override public HttpBean newInstance() { return new HttpBean(); }
        @Override public HttpBean[] newArray(int size) { return new HttpBean[size]; }
        @Override public HttpBean createFromParcel(@NonNull android.os.Parcel parcel) {
            return KryoConverters.deserialize(newInstance(), parcel.createByteArray());
        }
    };
}
