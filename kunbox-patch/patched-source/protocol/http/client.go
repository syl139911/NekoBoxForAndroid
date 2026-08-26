// KunBox patched: sing/protocol/http/client.go
// 基于 sing v0.8.9 (sing-box v1.13.11 依赖)
// 改动:
//   Patch 03: +delHost 字段 + raw TCP CONNECT (替换 Go http.Request.Write)
//   Patch 07: +httpFirst 字段 + http_first 写入
//   Patch 04: +httpsFirst +httpDel +httpsDel — HTTP/HTTPS 分离处理
//   Patch 05: +removePort +host — CONNECT 不带端口 + Host 强制覆盖 + 宽松响应解析
//
// === TPBox 执行顺序 ===
//   1. conn.Write(first)    ← preface (http_first 或 https_first，按端口选择)
//   2. conn.Write(raw CONNECT) ← 拼接后的 CONNECT 行 + headers
//   3. 宽松读取响应 (手动 ReadString，接受非标准格式)
//   4. tunnel established

package http

import (
	std_bufio "bufio"
	"context"
	"encoding/base64"
	"fmt"
	"net"
	"net/http"
	"crypto/tls"
	"os"
	"strings"

	"github.com/sagernet/sing/common/buf"
	"github.com/sagernet/sing/common/bufio"
	E "github.com/sagernet/sing/common/exceptions"
	"github.com/sagernet/sing/common/logger"
	M "github.com/sagernet/sing/common/metadata"
	N "github.com/sagernet/sing/common/network"
)

var _ N.Dialer = (*Client)(nil)

type Client struct {
	dialer     N.Dialer
	serverAddr M.Socksaddr
	username   string
	password   string
	host       string
	path       string
	headers    http.Header
	// ========== KunBox 新增字段 ==========
	delHost    bool     // Patch 03: TPBox del_host 模式
	httpFirst  string   // Patch 07: HTTP preface 内容
	// ====================================
	// ========== KunBox 新增字段 (Patch 04) ==========
	httpsFirst string   // HTTPS CONNECT 独立 preface
	httpDel    []string // HTTP 删除指定 header
	httpsDel   []string // HTTPS 删除指定 header
	// ====================================
	// ========== KunBox 新增字段 (Patch 05) ==========
	removePort bool   // CONNECT 行不带端口
	hostOption string // 强制替换 Host header (独立于 headers)
	// ====================================
	// ========== KunBox 新增字段 (Patch 15) ==========
	logger     logger.ContextLogger // sing-box log 框架，替代 stderr
	// ============================================
}

type Options struct {
	Dialer   N.Dialer
	Server   M.Socksaddr
	Username string
	Password string
	Path     string
	Headers  http.Header
	// ========== KunBox 新增选项 ==========
	DelHost   bool     // Patch 03
	HttpFirst string   // Patch 07
	// ====================================
	// ========== KunBox 新增选项 (Patch 04) ==========
	HttpsFirst string   // HTTPS CONNECT 独立 preface
	HttpDel    []string // HTTP 删除指定 header
	HttpsDel   []string // HTTPS 删除指定 header
	// ====================================
	// ========== KunBox 新增选项 (Patch 05) ==========
	RemovePort bool   // CONNECT 行不带端口
	Host       string // 强制替换 Host header
	Logger     logger.ContextLogger // KunBox: sing-box log 框架
	// ====================================
}

// stderrLogger: fallback when no logger is provided (avoids nil panic)
type stderrLogger struct{}
// Logger interface
func (l stderrLogger) Trace(args ...any) {}
func (l stderrLogger) Debug(args ...any) {}
func (l stderrLogger) Info(args ...any)  { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) Warn(args ...any)  { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) Error(args ...any) { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) Fatal(args ...any) { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) Panic(args ...any) { fmt.Fprintln(os.Stderr, args...) }
// ContextLogger interface
func (l stderrLogger) TraceContext(ctx context.Context, args ...any) {}
func (l stderrLogger) DebugContext(ctx context.Context, args ...any) {}
func (l stderrLogger) InfoContext(ctx context.Context, args ...any)  { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) WarnContext(ctx context.Context, args ...any)  { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) ErrorContext(ctx context.Context, args ...any) { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) FatalContext(ctx context.Context, args ...any) { fmt.Fprintln(os.Stderr, args...) }
func (l stderrLogger) PanicContext(ctx context.Context, args ...any) { fmt.Fprintln(os.Stderr, args...) }

func NewClient(options Options) *Client {
	client := &Client{
		dialer:     options.Dialer,
		serverAddr: options.Server,
		username:   options.Username,
		password:   options.Password,
		path:       options.Path,
		headers:    options.Headers,
		// ========== KunBox 赋值 ==========
		delHost:    options.DelHost,
		httpFirst:  options.HttpFirst,
		// ================================
		// ========== KunBox 赋值 (Patch 04) ==========
		httpsFirst: options.HttpsFirst,
		httpDel:    options.HttpDel,
		httpsDel:   options.HttpsDel,
		// ==========================================
		// ========== KunBox 赋值 (Patch 05) ==========
		removePort: options.RemovePort,
		hostOption: options.Host,
		logger:     options.Logger,
		// ==========================================
	}
	if client.logger == nil {
		client.logger = stderrLogger{}
	}
	if options.Dialer == nil {
		client.dialer = N.SystemDialer
	}
	var host string
	if client.headers != nil {
		host = client.headers.Get("Host")
		client.headers.Del("Host")
		client.host = host
	}
	return client
}

// ========== KunBox Debug Getters ==========
func (c *Client) ServerAddr() M.Socksaddr { return c.serverAddr }
func (c *Client) DelHost() bool            { return c.delHost }
func (c *Client) RemovePort() bool         { return c.removePort }
func (c *Client) Path() string             { return c.path }
func (c *Client) Host() string             { return c.hostOption }
func (c *Client) HttpFirst() string        { return c.httpFirst }
func (c *Client) HttpsFirst() string       { return c.httpsFirst }
// ==========================================


func (c *Client) DialContext(ctx context.Context, network string, destination M.Socksaddr) (net.Conn, error) {
	network = N.NetworkName(network)
	switch network {
	case N.NetworkTCP:
	case N.NetworkUDP:
		return nil, os.ErrInvalid
	default:
		return nil, E.Extend(N.ErrUnknownNetwork, network)
	}
	var conn net.Conn
	conn, err := c.dialer.DialContext(ctx, N.NetworkTCP, c.serverAddr)
	if err != nil {
		c.logger.InfoContext(ctx, "HTTP CONNECT: dial to proxy FAILED: ", c.serverAddr, " err=", err)
		return nil, err
	}
	c.logger.InfoContext(ctx, "HTTP CONNECT: dial to proxy OK: ", c.serverAddr)
	if tlsConn, ok := conn.(*tls.Conn); ok {
		state := tlsConn.ConnectionState()
		c.logger.InfoContext(ctx, "HTTP CONNECT: TLS: version=", fmt.Sprintf("%x", state.Version), " cipher=", fmt.Sprintf("%x", state.CipherSuite), " server=", state.ServerName)
	}

	// ============================================================
	// === TPBox 级 HTTP CONNECT 链路重写                       ===
	// ============================================================

	isHttps := destination.Port == 443 || c.httpsFirst != ""

	// === Step 1: http_first / https_first (preface) ===
	var firstContent string
	if isHttps {
		firstContent = c.httpsFirst
	} else {
		firstContent = c.httpFirst
	}
	if firstContent != "" {
		c.logger.InfoContext(ctx, "HTTP CONNECT: first >>> ", firstContent)
		_, err = conn.Write([]byte(firstContent))
		if err != nil {
			c.logger.InfoContext(ctx, "HTTP CONNECT: httpFirst write FAILED: err=", err)
			conn.Close()
			return nil, err
		}
	}

	// === Step 2: 构建 raw TCP CONNECT ===

	// --- 构建 CONNECT 目标 ---
	// path:       拼到 host:port 后面 (如 "host:port@gw.alicdn.com")
	// removePort: 去掉端口 (如 "host" 而不是 "host:443")
	// del_host:   不改变 CONNECT 行，只删除 Host header
	var target string
	if c.removePort {
		target = destination.Fqdn
	} else {
		target = destination.String()
	}
	if c.path != "" {
		target += c.path
	}

	var raw strings.Builder
	fmt.Fprintf(&raw, "CONNECT %s HTTP/1.1\r\n", target)

	// --- Host header ---
	// del_host=true: 不发送 Host header
	// hostOption: 强制替换
	// 默认: Host = destination
	if !c.delHost {
		var hostValue string
		if c.hostOption != "" {
			hostValue = c.hostOption
		} else if c.host != "" {
			hostValue = c.host
		} else {
			hostValue = destination.String()
		}
		fmt.Fprintf(&raw, "Host: %s\r\n", hostValue)
	}

	// --- del headers ---
	delHeaders := make(map[string]bool)
	delHeaders["host"] = true
	if isHttps {
		for _, h := range c.httpsDel {
			delHeaders[strings.ToLower(h)] = true
		}
	} else {
		for _, h := range c.httpDel {
			delHeaders[strings.ToLower(h)] = true
		}
	}

	// User-Agent（可通过 http_del/https_del 删除）
	if !delHeaders["user-agent"] {
		fmt.Fprintf(&raw, "User-Agent: Go-http-client/1.1\r\n")
	}

	// 自定义 headers
	hasProxyConnection := false
	if c.headers != nil {
		for key, values := range c.headers {
			if delHeaders[strings.ToLower(key)] {
				continue
			}
			if strings.ToLower(key) == "proxy-connection" {
				hasProxyConnection = true
			}
			for _, value := range values {
				fmt.Fprintf(&raw, "%s: %s\r\n", key, value)
			}
		}
	}

	// 默认 Proxy-Connection: Keep-Alive（自定义 headers 已设置或已删除则跳过）
	if !hasProxyConnection && !delHeaders["proxy-connection"] {
		fmt.Fprintf(&raw, "Proxy-Connection: Keep-Alive\r\n")
	}

	// Proxy-Authorization
	if c.username != "" {
		auth := c.username + ":" + c.password
		fmt.Fprintf(&raw, "Proxy-Authorization: Basic %s\r\n", base64.StdEncoding.EncodeToString([]byte(auth)))
	}

	raw.WriteString("\r\n")

	connectLog := raw.String()
	if len(connectLog) > 1024 {
		connectLog = connectLog[:1024] + "...(truncated)"
	}
	c.logger.InfoContext(ctx, "HTTP CONNECT: CONNECT >>> ", connectLog)

	_, err = conn.Write([]byte(raw.String()))
	if err != nil {
		c.logger.InfoContext(ctx, "HTTP CONNECT: CONNECT write FAILED: err=", err)
		conn.Close()
		return nil, err
	}

	// === Step 3: 宽松响应解析 ===
	// 替换 http.ReadResponse()，接受非标准响应:
	//   "HTTP/1.1 200 OK"
	//   "HTTP/1.0 200 OK"
	//   "200 OK"
	//   甚至只包含 "200" 的行
	reader := std_bufio.NewReader(conn)

	// 读取状态行
	statusLine, err := reader.ReadString('\n')
	if err != nil {
		c.logger.InfoContext(ctx, "HTTP CONNECT: read status line FAILED: err=", err)
		conn.Close()
		return nil, E.New("failed to read proxy response: ", err)
	}
	statusLine = strings.TrimSpace(statusLine)
	c.logger.InfoContext(ctx, "HTTP CONNECT: proxy status line: ", statusLine)

	// 统一读取 response headers（在判断状态码之前，避免非 200 路径消费后 200 路径丢失）
	var respHeaders strings.Builder
	for {
		line, readErr := reader.ReadString('\n')
		if line == "\r\n" || line == "\n" || readErr != nil {
			break
		}
		respHeaders.WriteString(line)
	}
	if respHeaders.Len() > 0 {
		c.logger.InfoContext(ctx, "HTTP CONNECT: proxy response headers:\n", respHeaders.String())
	}

	// 精确检查状态码是否为 200 (精确匹配，处理 "HTTP/1.1 200 OK" / "200 OK" / "200")
	hasValidStatus := false
	{
		trimmed := strings.TrimSpace(statusLine)
		// 去掉 HTTP 版本前缀
		if idx := strings.Index(trimmed, " "); idx >= 0 {
			trimmed = trimmed[idx+1:]
		}
		// 现在 trimmed 应以状态码开头，如 "200 OK" 或 "200"
		if strings.HasPrefix(trimmed, "200 ") || trimmed == "200" {
			hasValidStatus = true
		}
	}
	if !hasValidStatus {
		conn.Close()
		return nil, E.New("connect failed: ", statusLine)
	}

	// 连接建立成功
	if reader.Buffered() > 0 {
		buffer := buf.NewSize(reader.Buffered())
		_, err = buffer.ReadFullFrom(reader, buffer.FreeLen())
		if err != nil {
			c.logger.InfoContext(ctx, "HTTP CONNECT: ReadFullFrom FAILED: err=", err)
			conn.Close()
			return nil, err
		}
		conn = bufio.NewCachedConn(conn, buffer)
	}
	return conn, nil
}

func (c *Client) ListenPacket(ctx context.Context, destination M.Socksaddr) (net.PacketConn, error) {
	return nil, os.ErrInvalid
}

