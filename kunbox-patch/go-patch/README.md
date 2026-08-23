# Go 层精简补丁 - delHost + path

## 需要修改的文件 (在你的 ../../sing-box 本地 fork 里)

### 1. option/simple.go
在 `HTTPOutboundOptions` 结构体里加 `DelHost` 字段:

```go
type HTTPOutboundOptions struct {
	DialerOptions
	ServerOptions
	Username string `json:"username,omitempty"`
	Password string `json:"***word,omitempty"`
	OutboundTLSOptionsContainer
	Path      string               `json:"path,omitempty"`
	Headers   badoption.HTTPHeader `json:"headers,omitempty"`
	// ========== 新增 ==========
	DelHost   bool                 `json:"del_host,omitempty"`
	// ==========================
}
```

### 2. protocol/http/outbound.go
在 NewOutbound 里把 DelHost 传给 client:

```go
client: sHTTP.NewClient(sHTTP.Options{
    Dialer:   detour,
    Server:   options.ServerOptions.Build(),
    Username: options.Username,
    Password: options.Password,
    Path:     options.Path,
    Headers:  options.Headers.Build(),
    // 新增
    DelHost:  options.DelHost,
}),
```

### 3. sing/protocol/http/client.go
**核心改动** - 见本目录下 `client.go.patch`
