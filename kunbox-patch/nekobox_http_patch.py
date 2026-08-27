#!/usr/bin/env python3
"""
NekoBox HTTP 精简补丁 — delHost + path
基于 KunBox 补丁提取，只保留 delHost 和 path 功能

用法:
  python3 nekobox_http_patch.py <sing-box-dir> <local-sing-dir>
  python3 nekobox_http_patch.py --dry-run <sing-box-dir> <local-sing-dir>

执行顺序:
  1. option/simple.go  — HTTPOutboundOptions 加 DelHost 字段
  2. outbound.go       — 传递 DelHost 给 Client
  3. client.go         — raw TCP CONNECT + delHost + path + 宽松响应解析
"""

import sys
import re
import os

DRY_RUN = '--dry-run' in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith('--')]

if len(args) < 2:
    print("用法: python3 nekobox_http_patch.py <sing-box-dir> <local-sing-dir>")
    print("      python3 nekobox_http_patch.py --dry-run <sing-box-dir> <local-sing-dir>")
    sys.exit(1)

SING_BOX_DIR = args[0]
SING_DIR = args[1]

OPTS_PATH = os.path.join(SING_BOX_DIR, "option", "simple.go")
OUTBOUND_PATH = os.path.join(SING_BOX_DIR, "protocol", "http", "outbound.go")
CLIENT_PATH = os.path.join(SING_DIR, "protocol", "http", "client.go")


def read_file(path):
    with open(path, 'r') as f:
        return f.read()


def write_file(path, content):
    if DRY_RUN:
        print(f"  [dry-run] would write {path}")
        return
    with open(path, 'w') as f:
        f.write(content)
    print(f"  ✅ wrote {path}")


def ensure_import(content, pkg, import_line):
    """确保 import 块中包含指定包（真正添加，避免 undefined 编译失败）"""
    if import_line not in content:
        lines = content.split('\n')
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if not inserted and line.strip() == 'import (':
                new_lines.append('\t' + import_line)
                inserted = True
        if inserted:
            content = '\n'.join(new_lines)
            print(f"  + import {pkg}")
        else:
            print(f"  ⚠️  未找到 import ( 块，跳过 {pkg} import")
    return content


def check_file(path, label):
    if not os.path.exists(path):
        print(f"  ❌ {label} not found: {path}")
        return False
    print(f"  ✓ {label}: {path}")
    return True


# ============================================================
#  1. option/simple.go — 注入 DelHost 字段
# ============================================================

def patch_options():
    print("\n=== 1. option/simple.go ===")
    if not check_file(OPTS_PATH, "options"):
        return False

    content = read_file(OPTS_PATH)

    # 检查是否已打过补丁
    if 'DelHost' in content and 'json:"del_host"' in content:
        print("  ⏭️  DelHost 已存在，跳过")
        return True

    # 在 HTTPOutboundOptions 的 Headers 字段后面注入 DelHost
    # 匹配: Headers badoption.HTTPHeader `json:"headers,omitempty"`
    anchor = re.search(
        r'Headers\s+badoption\.HTTPHeader\s+`json:"headers,omitempty"`',
        content
    )
    if not anchor:
        print("  ❌ 找不到 Headers 字段锚点")
        return False

    field_line = '\tDelHost   bool                 `json:"del_host,omitempty"`'
    insert_pos = anchor.end()
    content = content[:insert_pos] + '\n' + field_line + content[insert_pos:]
    print("  + DelHost 字段")

    write_file(OPTS_PATH, content)
    return True


# ============================================================
#  2. outbound.go — 传递 DelHost 给 Client
# ============================================================

def patch_outbound():
    print("\n=== 2. protocol/http/outbound.go ===")
    if not check_file(OUTBOUND_PATH, "outbound"):
        return False

    content = read_file(OUTBOUND_PATH)

    if 'DelHost' in content and 'options.DelHost' in content:
        print("  ⏭️  DelHost 传递已存在，跳过")
        return True

    # 在 Headers: options.Headers.Build(), 后面加 DelHost
    anchor = re.search(
        r'Headers:\s+options\.Headers\.Build\(\),',
        content
    )
    if not anchor:
        print("  ❌ 找不到 Headers 传递锚点")
        return False

    field_line = '\t\t\tDelHost:  options.DelHost,'
    insert_pos = anchor.end()
    content = content[:insert_pos] + '\n' + field_line + content[insert_pos:]
    print("  + DelHost 传递")

    write_file(OUTBOUND_PATH, content)
    return True


# ============================================================
#  3. client.go — raw TCP CONNECT + delHost + path
# ============================================================

def patch_client():
    print("\n=== 3. sing/protocol/http/client.go ===")
    if not check_file(CLIENT_PATH, "client"):
        return False

    content = read_file(CLIENT_PATH)

    # --- 3a. Client struct 加 delHost 字段 ---
    if 'delHost' not in content:
        # 在 host 字段后面加 delHost
        anchor = re.search(r'host\s+string\n', content)
        if anchor:
            field_line = '\tdelHost    bool\n'
            insert_pos = anchor.end()
            content = content[:insert_pos] + field_line + content[insert_pos:]
            print("  + Client.delHost 字段")
        else:
            print("  ⚠️  找不到 host 字段，跳过 struct 注入")

    # --- 3b. Options struct 加 DelHost 字段 ---
    if 'DelHost' not in content or 'DelHost\tbool' not in content:
        # 在 Password string 后面加 DelHost
        anchor = re.search(r'Password\s+string\n', content)
        if anchor:
            field_line = '\tDelHost    bool\n'
            insert_pos = anchor.end()
            content = content[:insert_pos] + field_line + content[insert_pos:]
            print("  + Options.DelHost 字段")
        else:
            print("  ⚠️  找不到 Password 字段，跳过 Options 注入")

    # --- 3c. NewClient 赋值 ---
    if 'options.DelHost' not in content:
        # 在 password 赋值后面加 delHost
        anchor = re.search(r'password:\s+options\.Password,?\n', content)
        if anchor:
            assign_line = '\t\tdelHost:    options.DelHost,\n'
            insert_pos = anchor.end()
            content = content[:insert_pos] + assign_line + content[insert_pos:]
            print("  + NewClient DelHost 赋值")
        else:
            print("  ⚠️  找不到 password 赋值锚点")

    # --- 3d. 替换 DialContext 方法 ---
    # 找到 func (c *Client) DialContext 开始位置
    dial_start = re.search(r'func \(c \*Client\) DialContext\(', content)
    if not dial_start:
        print("  ❌ 找不到 DialContext 方法")
        return False

    # 找到方法结束 (下一个 func 开始或文件结束)
    # 从 DialContext 开始搜索下一个顶级 func
    remaining = content[dial_start.start():]
    # 匹配下一个以 "func " 开头的行（不在缩进内的）
    next_func = re.search(r'\nfunc ', remaining[1:])
    if next_func:
        dial_end = dial_start.start() + 1 + next_func.start()
    else:
        dial_end = len(content)

    old_dial = content[dial_start.start():dial_end]

    # 检查是否已经是 patched 版本
    if 'raw TCP CONNECT' in old_dial or 'CONNECT %s HTTP/1.1' in old_dial:
        print("  ⏭️  DialContext 已被替换，跳过")
        return True

    new_dial = '''func (c *Client) DialContext(ctx context.Context, network string, destination M.Socksaddr) (net.Conn, error) {
\tnetwork = N.NetworkName(network)
\tswitch network {
\tcase N.NetworkTCP:
\tcase N.NetworkUDP:
\t\treturn nil, os.ErrInvalid
\tdefault:
\t\treturn nil, E.Extend(N.ErrUnknownNetwork, network)
\t}

\tconn, err := c.dialer.DialContext(ctx, N.NetworkTCP, c.serverAddr)
\tif err != nil {
\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy FAILED: %s err=%v\\n", c.serverAddr, err)
\t\treturn nil, err
\t}
\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy OK: %s\\n", c.serverAddr)

\t// ================================================================
\t// raw TCP CONNECT (替换 Go http.Request.Write)
\t// ================================================================

\t// --- 构建 CONNECT 目标 ---
\tvar target string
\ttarget = destination.String()
\tif c.path != "" {
\t\ttarget += c.path
\t}

\tvar raw strings.Builder
\tfmt.Fprintf(&raw, "CONNECT %s HTTP/1.1\\r\\n", target)

\t// --- Host header ---
\tif !c.delHost {
\t\tvar hostValue string
\t\tif c.host != "" {
\t\t\thostValue = c.host
\t\t} else {
\t\t\thostValue = destination.String()
\t\t}
\t\tfmt.Fprintf(&raw, "Host: %s\\r\\n", hostValue)
\t}

\t// User-Agent
\tfmt.Fprintf(&raw, "User-Agent: Go-http-client/1.1\\r\\n")

\t// 自定义 headers
\thasProxyConnection := false
\tif c.headers != nil {
\t\tfor key, values := range c.headers {
\t\t\tif strings.ToLower(key) == "proxy-connection" {
\t\t\t\thasProxyConnection = true
\t\t\t}
\t\t\tfor _, value := range values {
\t\t\t\tfmt.Fprintf(&raw, "%s: %s\\r\\n", key, value)
\t\t\t}
\t\t}
\t}

\t// Proxy-Connection
\tif !hasProxyConnection {
\t\tfmt.Fprintf(&raw, "Proxy-Connection: Keep-Alive\\r\\n")
\t}

\t// Proxy-Authorization
\tif c.username != "" {
\t\tauth := c.username + ":" + c.password
\t\tfmt.Fprintf(&raw, "Proxy-Authorization: Basic %s\\r\\n", base64.StdEncoding.EncodeToString([]byte(auth)))
\t}

\traw.WriteString("\\r\\n")

\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT >>> %s", raw.String())
\t_, err = conn.Write([]byte(raw.String()))
\tif err != nil {
\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT write FAILED: err=%v\\n", err)
\t\tconn.Close()
\t\treturn nil, err
\t}

\t// ================================================================
\t// 宽松响应解析 (接受非标准格式)
\t// ================================================================
\treader := std_bufio.NewReader(conn)

\t// 读取状态行
\tstatusLine, err := reader.ReadString('\\n')
\tif err != nil {
\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] read status line FAILED: err=%v\\n", err)
\t\tconn.Close()
\t\treturn nil, E.New("failed to read proxy response: ", err)
\t}
\tstatusLine = strings.TrimSpace(statusLine)
\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy status line: %q\\n", statusLine)

\t// 读取 response headers
\tfor {
\t\tline, readErr := reader.ReadString('\\n')
\t\tif line == "\\r\\n" || line == "\\n" || readErr != nil {
\t\t\tbreak
\t\t}
\t}

\t// 检查状态码是否为 200
\t// 接受: "HTTP/1.1 200 OK", "HTTP/1.0 200 OK", "200 OK", "200"
\thasValidStatus := false
\t{
\t\ttrimmed := strings.TrimSpace(statusLine)
\t\tif idx := strings.Index(trimmed, " "); idx >= 0 {
\t\t\ttrimmed = trimmed[idx+1:]
\t\t}
\t\tif strings.HasPrefix(trimmed, "200 ") || trimmed == "200" {
\t\t\thasValidStatus = true
\t\t}
\t}
\tif !hasValidStatus {
\t\tconn.Close()
\t\treturn nil, E.New("connect failed: ", statusLine)
\t}

\t// 连接建立成功
\tif reader.Buffered() > 0 {
\t\tbuffer := buf.NewSize(reader.Buffered())
\t\t_, err = buffer.ReadFullFrom(reader, buffer.FreeLen())
\t\tif err != nil {
\t\t\tconn.Close()
\t\t\treturn nil, err
\t\t}
\t\tconn = bufio.NewCachedConn(conn, buffer)
\t}
\treturn conn, nil
}

'''

    content = content[:dial_start.start()] + new_dial + content[dial_end:]
    print("  + DialContext 替换为 raw TCP CONNECT 版本")

    # --- 3e. 确保 import 包含必要包（真正添加，避免 undefined 编译失败）---
    needed_imports = {
        '"strings"': 'strings',
        '"fmt"': 'fmt',
        '"os"': 'os',
        '"encoding/base64"': 'base64',
        'std_bufio "bufio"': 'std_bufio',
    }
    for import_line, pkg in needed_imports.items():
        if import_line not in content:
            content = ensure_import(content, pkg, import_line)

    # --- 3f. 清理不再使用的 import（补丁替换 DialContext 后 net/url 可能不再使用）---
    if 'url.URL' not in content and 'url.' not in content.replace('net/url', ''):
        if '"net/url"' in content:
            content = re.sub(r'\t"net/url"\n', '', content)
            print("  - 移除未使用的 net/url import")

    write_file(CLIENT_PATH, content)
    return True


# ============================================================
#  主流程
# ============================================================

def main():
    print("=" * 50)
    print("NekoBox HTTP 精简补丁 — delHost + path")
    print("=" * 50)

    if DRY_RUN:
        print("🔍 dry-run 模式，不会修改文件\n")

    ok = True
    ok = patch_options() and ok
    ok = patch_outbound() and ok
    ok = patch_client() and ok

    print("\n" + "=" * 50)
    if ok:
        print("🎉 补丁完成！")
        print("\n下一步:")
        print("  1. 检查修改是否正确")
        print("  2. 重新编译 libbox.aar")
        print("  3. 在自定义配置里使用:")
        print('     {"type":"http","del_host":true,"path":"@gw.alicdn.com",...}')
    else:
        print("❌ 部分补丁失败，请检查输出")
    print("=" * 50)


if __name__ == "__main__":
    main()
