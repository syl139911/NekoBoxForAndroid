#!/usr/bin/env python3
"""
KunBox Unified Patch — 一次读、顺序改、一次写

合并自 14 个独立 patch，消除跨进程锚点依赖。
每个子函数基于当前文件实际状态判断，不假设上游 patch 输出。

用法:
  python3 kunbox_patch.py <sing-box-dir> <local-sing-dir>
  python3 kunbox_patch.py --dry-run <sing-box-dir> <local-sing-dir>

执行顺序:
  1. option/simple.go  — 注入所有 Options 字段
  2. outbound.go       — 传递所有字段给 Client
  3. client.go         — 注入字段 + 代码替换 + 日志
"""
import sys
import re
import os

# ============================================================
#  工具函数
# ============================================================

DRY_RUN = '--dry-run' in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith('--')]

if len(args) < 2:
    print("用法: python3 kunbox_patch.py <sing-box-dir> <local-sing-dir>")
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


def ensure_import(content, pkg, import_line):
    """确保 import 块中包含指定包"""
    if import_line not in content:
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if line.strip() == 'import (':
                new_lines.append('\t' + import_line)
        content = '\n'.join(new_lines)
        print(f"    + import {pkg}")
    return content


def inject_field_after(content, anchor_pattern, field_line, field_name, context=""):
    """在锚点行之后注入字段，如果字段不存在的话"""
    # 用 \b 精确匹配字段名，避免子串误匹配
    if re.search(rf'\b{re.escape(field_name)}\b', content):
        print(f"    ~ {field_name} already exists {context}")
        return content
    match = re.search(anchor_pattern, content, re.MULTILINE)
    if match:
        insert_pos = match.end()
        content = content[:insert_pos] + '\n' + field_line + content[insert_pos:]
        print(f"    + {field_name} {context}")
    else:
        print(f"    ! anchor not found for {field_name} {context}")
    return content


# ============================================================
#  1. option/simple.go — 注入所有 Options 字段
# ============================================================

def patch_options(content):
    """合并: 01-options + 05-httpfirst-option + 08-httpsfirst-option + 12-removeport-option"""

    # 定义所有需要注入的字段 (名称, JSON tag, 类型, 锚点正则)
    fields = [
        # 01: Path + DelHost
        ('Path', 'path', 'string',
         r'Headers\s+badoption\.HTTPHeader\s+`[^`]+`'),
        ('DelHost', 'del_host', 'bool',
         r'Path\s+string\s+`[^`]+`'),
        # 05: HttpFirst
        ('HttpFirst', 'http_first', 'string',
         r'DelHost\s+bool\s+`[^`]+`'),
        # 08: HttpsFirst + HttpDel + HttpsDel
        ('HttpsFirst', 'https_first', 'string',
         r'HttpFirst\s+string\s+`[^`]+`'),
        ('HttpDel', 'http_del', '[]string',
         r'HttpsFirst\s+string\s+`[^`]+`'),
        ('HttpsDel', 'https_del', '[]string',
         r'HttpDel\s+\[\]string\s+`[^`]+`'),
        # 12: RemovePort + Host
        ('RemovePort', 'remove_port', 'bool',
         r'HttpsDel\s+\[\]string\s+`[^`]+`'),
        ('Host', 'host', 'string',
         r'RemovePort\s+bool\s+`[^`]+`'),
    ]

    for name, tag, typ, anchor in fields:
        if re.search(rf'\b{re.escape(name)}\b.*json:"{re.escape(tag)}', content):
            print(f"  ~ Options.{name} already exists")
            continue
        match = re.search(anchor, content, re.MULTILINE)
        if match:
            # 计算缩进对齐
            pad = max(1, 20 - len(name) - len(typ))
            field_line = f'\t{name}{" " * pad}{typ} `json:"{tag},omitempty"`'
            insert_pos = match.end()
            content = content[:insert_pos] + '\n' + field_line + content[insert_pos:]
            print(f"  + Options.{name}")
        else:
            print(f"  ! anchor not found for Options.{name}")

    return content


# ============================================================
#  2. outbound.go — 传递所有字段给 Client
# ============================================================

def patch_outbound(content):
    """合并: 02-outbound + 06-httpfirst-outbound + 09-httpsfirst-outbound + 13-removeport-outbound"""

    # 所有需要传递的赋值 (字段名, 值, 锚点正则)
    assignments = [
        # 02: Path + DelHost
        ('Path', 'options.Path',
         r'Headers:\s+options\.Headers\.Build\(\),'),
        ('DelHost', 'options.DelHost',
         r'Path:\s+options\.Path,'),
        # 06: HttpFirst
        ('HttpFirst', 'options.HttpFirst',
         r'DelHost:\s+options\.DelHost,'),
        # 09: HttpsFirst + HttpDel + HttpsDel
        ('HttpsFirst', 'options.HttpsFirst',
         r'HttpFirst:\s+options\.HttpFirst,'),
        ('HttpDel', 'options.HttpDel',
         r'HttpsFirst:\s+options\.HttpsFirst,'),
        ('HttpsDel', 'options.HttpsDel',
         r'HttpDel:\s+options\.HttpDel,'),
        # 13: RemovePort + Host
        ('RemovePort', 'options.RemovePort',
         r'HttpsDel:\s+options\.HttpsDel,'),
        ('Host', 'options.Host',
         r'RemovePort:\s+options\.RemovePort,'),
    ]

    for name, val, anchor in assignments:
        if re.search(rf'{re.escape(name)}:', content):
            print(f"  ~ outbound.{name} already passed")
            continue
        match = re.search(anchor, content, re.MULTILINE)
        if match:
            pad = max(1, 12 - len(name))
            line = f'\t\t\t\t{name}:{" " * pad}{val},'
            insert_pos = match.end()
            content = content[:insert_pos] + '\n' + line + content[insert_pos:]
            print(f"  + outbound.{name}")
        else:
            print(f"  ! anchor not found for outbound.{name}")

    # 传递 logger (来自 outbound 自身)
    if 'Logger:' not in content:
        # 在 Client 初始化块末尾添加
        match = re.search(r'(Host:\s+options\.Host,)', content)
        if match:
            line = '\t\t\t\tLogger:     logger,'
            content = content[:match.end()] + '\n' + line + content[match.end():]
            print(f"  + outbound.Logger")
        else:
            print(f"  ! anchor not found for outbound.Logger")
    else:
        print(f"  ~ outbound.Logger already passed")

    # stderr → logger 替换 (patch 15 Part A)
    if 'fmt.Fprintf(os.Stderr, "[KunBox-OUT]' in content:
        # 确保 logger import
        if '"github.com/sagernet/sing/common/logger"' not in content:
            content = ensure_import(content, 'logger', '"github.com/sagernet/sing/common/logger"')
        # 替换 stderr 为 logger.InfoContext
        old_out_log = re.search(
            r'\tfmt\.Fprintf\(os\.Stderr, "\[KunBox-OUT\].*?\n.*?\n',
            content
        )
        if old_out_log:
            content = content[:old_out_log.start()] + \
                '\th.logger.InfoContext(ctx, "HTTP outbound: dial ", network, ' \
                '" -> server=", h.client.ServerAddr(),\n' \
                '\t\t" delHost=", h.client.DelHost(), " removePort=", h.client.RemovePort(),\n' \
                '\t\t" path=", h.client.Path(), " host=", h.client.Host())\n' + \
                content[old_out_log.end():]
            print("  ~ outbound.stderr → logger.InfoContext")
    # 清理 outbound.go 中不再使用的 os import
    # 注意: ListenPacket 使用 os.ErrInvalid, 不能移除
    has_os_usage = 'os.Stderr' in content or 'os.ErrInvalid' in content or 'os.ErrInvalid' in content
    if not has_os_usage and '"os"' in content:
        content = ensure_import(content, 'os', '"os"')
        print("  ~ ensured os import in outbound.go (ListenPacket needs it)")
    elif not has_os_usage:
        # 真的不需要 os, 安全移除
        content = content.replace('\t"os"\n', '')
        print("  - removed unused os import from outbound.go")

    return content


# ============================================================
#  3. client.go — 最复杂，严格按依赖顺序
# ============================================================

def patch_client(content):
    """合并: 03 + 07 + 10 + 11 + 14 + 15"""

    # ---- Phase A: 注入所有 struct 字段 (03 + 07 + 10 + 14) ----
    content = inject_client_fields(content)

    # ---- Phase B: 注入 Options 字段 (03 + 07 + 10 + 14) ----
    content = inject_client_options_fields(content)

    # ---- Phase C: 注入 getter 方法 (14) ----
    content = inject_getters(content)

    # ---- Phase D: NewClient 赋值 (03 + 07 + 10 + 14) ----
    content = inject_newclient_assignments(content)

    # ---- Phase E: 确保 imports ----
    content = ensure_import(content, 'fmt', '"fmt"')
    content = ensure_import(content, 'strings', '"strings"')
    content = ensure_import(content, 'os', '"os"')
    content = ensure_import(content, 'encoding/base64', '"encoding/base64"')
    content = ensure_import(content, 'logger', '"github.com/sagernet/sing/common/logger"')

    # ---- Phase F: 代码替换 (03 raw TCP → 07 httpFirst → 10 httpsFirst → 14 removePort) ----
    content = replace_raw_tcp_connect(content)
    content = inject_http_first_preface(content)
    content = upgrade_to_port_aware_preface(content)
    content = upgrade_to_dynamic_del_headers(content)
    content = rewrite_connect_target(content)
    content = rewrite_host_header(content)
    content = rewrite_response_parsing(content)

    # ---- Phase G: Debug 日志 (11) ----
    content = inject_debug_logging(content)

    # ---- Phase H: Logger 替换 stderr (15, 必须最后!) ----
    content = replace_stderr_with_logger(content)

    # ---- Phase I: 清理无用 import ----
    content = cleanup_imports(content)

    return content


# ============================================================
#  Phase A: 注入 Client struct 字段
# ============================================================

def inject_client_fields(content):
    """往 Client struct 注入所有 KunBox 字段"""

    # 原始 sing 已有: host, path
    # 需要注入: delHost, httpFirst, httpsFirst, httpDel, httpsDel, removePort, hostOption, logger

    fields = [
        ('delHost', 'bool', r'host\s+string'),
        ('httpFirst', 'string', r'delHost\s+bool'),
        ('httpsFirst', 'string', r'httpFirst\s+string'),
        ('httpDel', '[]string', r'httpsFirst\s+string'),
        ('httpsDel', '[]string', r'httpDel\s+\[\]string'),
        ('removePort', 'bool', r'httpsDel\s+\[\]string'),
        ('hostOption', 'string', r'removePort\s+bool'),
        ('logger', 'logger.ContextLogger', r'hostOption\s+string'),
    ]

    for name, typ, anchor in fields:
        if name in content:
            print(f"    ~ Client.{name} already exists")
            continue
        match = re.search(anchor, content, re.MULTILINE)
        if match:
            pad = max(1, 12 - len(name))
            line = f'\t{name}{" " * pad}{typ}'
            content = content[:match.end()] + '\n' + line + content[match.end():]
            print(f"    + Client.{name}")
        else:
            print(f"    ! anchor not found for Client.{name}")

    return content


# ============================================================
#  Phase B: 注入 Client Options 字段
# ============================================================

def inject_client_options_fields(content):
    """往 Client 的 Options struct 注入所有 KunBox 字段"""

    fields = [
        ('Path', 'string', r'Headers\s+http\.Header'),
        ('DelHost', 'bool', r'Path\s+string'),
        ('HttpFirst', 'string', r'DelHost\s+bool'),
        ('HttpsFirst', 'string', r'HttpFirst\s+string'),
        ('HttpDel', '[]string', r'HttpsFirst\s+string'),
        ('HttpsDel', '[]string', r'HttpDel\s+\[\]string'),
        ('RemovePort', 'bool', r'HttpsDel\s+\[\]string'),
        ('Host', 'string', r'RemovePort\s+bool'),
        ('Logger', 'logger.ContextLogger', r'Host\s+string'),
    ]

    for name, typ, anchor in fields:
        # 精确检查：字段名 + 类型 都要匹配
        if re.search(rf'\b{re.escape(name)}\b.*\b{re.escape(typ)}\b', content):
            print(f"    ~ Options.{name} already exists")
            continue
        match = re.search(anchor, content, re.MULTILINE)
        if match:
            pad = max(1, 12 - len(name))
            line = f'\t{name}{" " * pad}{typ}'
            content = content[:match.end()] + '\n' + line + content[match.end():]
            print(f"    + Options.{name}")
        else:
            print(f"    ! anchor not found for Options.{name}")

    return content


# ============================================================
#  Phase C: getter 方法 (patch 14)
# ============================================================

def inject_getters(content):
    """添加 RemovePort() 和 Host() getter"""

    if 'func (c *Client) RemovePort()' in content:
        print("    ~ getters already exist")
        return content

    anchor = r'func \(c \*Client\) HttpsFirst\(\) string\s+\{ return c\.httpsFirst \}'
    match = re.search(anchor, content)
    if match:
        getters = (
            '\nfunc (c *Client) RemovePort() bool         { return c.removePort }'
            '\nfunc (c *Client) Host() string             { return c.hostOption }'
        )
        content = content[:match.end()] + getters + content[match.end():]
        print("    + RemovePort() + Host() getters")
    else:
        print("    ! HttpsFirst getter not found as anchor")

    return content


# ============================================================
#  Phase D: NewClient 赋值
# ============================================================

def inject_newclient_assignments(content):
    """往 NewClient 函数注入所有字段赋值"""

    assignments = [
        ('path', 'options.Path', r'headers:\s+options\.Headers,'),
        ('delHost', 'options.DelHost', r'path:\s+options\.Path,'),
        ('httpFirst', 'options.HttpFirst', r'delHost:\s+options\.DelHost,'),
        ('httpsFirst', 'options.HttpsFirst', r'httpFirst:\s+options\.HttpFirst,'),
        ('httpDel', 'options.HttpDel', r'httpsFirst:\s+options\.HttpsFirst,'),
        ('httpsDel', 'options.HttpsDel', r'httpDel:\s+options\.HttpDel,'),
        ('removePort', 'options.RemovePort', r'httpsDel:\s+options\.HttpsDel,'),
        ('hostOption', 'options.Host', r'removePort:\s+options\.RemovePort,'),
        ('logger', 'options.Logger', r'hostOption:\s+options\.Host,'),
    ]

    for name, val, anchor in assignments:
        if re.search(rf'{re.escape(name)}:\s*{re.escape(val)}', content):
            print(f"    ~ NewClient.{name} already assigned")
            continue
        match = re.search(anchor, content, re.MULTILINE)
        if match:
            pad = max(1, 12 - len(name))
            line = f'\t\t\t{name}:{" " * (pad if pad > 1 else 1)}{val},'
            content = content[:match.end()] + '\n' + line + content[match.end():]
            print(f"    + NewClient.{name}")
        else:
            print(f"    ! anchor not found for NewClient.{name}")

    # No extra fix needed here — nil guards are in Phase H replacements

    return content


# ============================================================
#  Phase F-1: Raw TCP CONNECT 替换 (patch 03)
# ============================================================

def replace_raw_tcp_connect(content):
    """用 raw TCP write 替换 Go http.Request.Write()"""

    if '// === KunBox raw TCP CONNECT ===' in content:
        print("    ~ raw TCP CONNECT already injected")
        return content

    # 查找 request := &http.Request{ ... request.Write(conn) 块
    old_pattern = (
        r'\tvar request http\.Request\n'
        r'\trequest\.Method = http\.MethodConnect\n'
        r'\trequest\.Host = destination\.Address\.String\(\)\n'
        r'(?:.*\n)*?'
        r'\terr = request\.Write\(conn\)\n'
        r'\tif err != nil \{\n'
        r'\t\treturn nil, err\n'
        r'\t\}'
    )

    # 精确匹配原始 sing 的 request 块
    old_block = None
    for candidate in [
        'var request http.Request',
        'request := &http.Request{',
    ]:
        idx = content.find(candidate)
        if idx >= 0:
            # 找到 request.Write(conn)
            write_idx = content.find('request.Write(conn)', idx)
            if write_idx >= 0:
                # 找到块的结束位置 (匹配大括号)
                end_idx = content.find('\n\t}', write_idx)
                if end_idx >= 0:
                    end_idx += 3  # 包含 \n\t}
                    old_block = content[idx:end_idx]
                    break

    if old_block is None:
        print("    ! request block not found for raw TCP replacement")
        return content

    # 动态检测缩进：取 old_block 所在行的缩进
    # content[:idx] 已包含缩进，所以 new_block 不需要再加
    line_start = content.rfind('\n', 0, idx) + 1
    base_indent = content[line_start:idx]
    indent = ''  # 缩进由 content[:idx] 提供

    new_block = (
        f'{indent}// === KunBox raw TCP CONNECT ===\n'
        f'{indent}// Bypass Go http.Request.Write() normalization for TPBox\n'
        f'{indent}target := destination.String()\n'
        f'{indent}if c.path != "" {{\n'
        f'{indent}\ttarget += c.path\n'
        f'{indent}}}\n'
        f'{indent}\n'
        f'{indent}var raw strings.Builder\n'
        f'{indent}fmt.Fprintf(&raw, "CONNECT %s HTTP/1.1\\r\\n", target)\n'
        f'{indent}\n'
        f'{indent}// Host header: c.host 优先，否则用 destination\n'
        f'{indent}if c.host != "" {{\n'
        f'{indent}\tfmt.Fprintf(&raw, "Host: %s\\r\\n", c.host)\n'
        f'{indent}}} else if !c.delHost {{\n'
        f'{indent}\tfmt.Fprintf(&raw, "Host: %s\\r\\n", destination.String())\n'
        f'{indent}}}\n'
        f'{indent}\n'
        f'{indent}skipHeaders := map[string]bool{{\n'
        f'{indent}\t"host": true,\n'
        f'{indent}}}\n'
        f'{indent}if c.headers != nil {{\n'
        f'{indent}\tfor key, values := range c.headers {{\n'
        f'{indent}\t\tif skipHeaders[strings.ToLower(key)] {{\n'
        f'{indent}\t\t\tcontinue\n'
        f'{indent}\t\t}}\n'
        f'{indent}\t\tfor _, value := range values {{\n'
        f'{indent}\t\t\tfmt.Fprintf(&raw, "%s: %s\\r\\n", key, value)\n'
        f'{indent}\t\t}}\n'
        f'{indent}\t}}\n'
        f'{indent}}}\n'
        f'{indent}\n'
        f'{indent}if c.username != "" {{\n'
        f'{indent}\tauth := c.username + ":" + c.password\n'
        f'{indent}\tfmt.Fprintf(&raw, "Proxy-Authorization: Basic %s\\r\\n", base64.StdEncoding.EncodeToString([]byte(auth)))\n'
        f'{indent}}}\n'
        f'{indent}\n'
        f'{indent}raw.WriteString("\\r\\n")\n'
        f'{indent}\n'
        f'{indent}_, err = conn.Write([]byte(raw.String()))\n'
        f'{indent}if err != nil {{\n'
        f'{indent}\tconn.Close()\n'
        f'{indent}\treturn nil, err\n'
        f'{indent}}}\n'
        f'{indent}\n'
        f'{indent}// Minimal request for http.ReadResponse\n'
        f'{indent}request := &http.Request{{\n'
        f'{indent}\tMethod: http.MethodConnect,\n'
        f'{indent}\tURL:    &url.URL{{Host: destination.String()}},\n'
        f'{indent}}}\n'
        f'{indent}\n'
    )

    content = content.replace(old_block, new_block, 1)
    print("    + raw TCP CONNECT injected")
    return content


# ============================================================
#  Phase F-2: HttpFirst preface (patch 07)
# ============================================================

def inject_http_first_preface(content):
    """在 raw TCP CONNECT 块前插入 http_first 写入"""

    if '// === KunBox http_first' in content or '// === KunBox http_first / https_first' in content:
        print("    ~ httpFirst preface already injected")
        return content

    marker = '// === KunBox raw TCP CONNECT ==='
    idx = content.find(marker)
    if idx < 0:
        print("    ! KunBox raw TCP CONNECT marker not found")
        return content

    # 缩进由 content[:idx] 提供，block 内部用相对缩进
    indent = ''
    block = (
        f'{indent}// === KunBox http_first (HTTP preface) ===\n'
        f'{indent}// conn 是原始 TCP 连接，Write 直接进内核 socket buffer，无需 flush\n'
        f'{indent}if c.httpFirst != "" {{\n'
        f'{indent}\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] http_first >>> %q\\n", c.httpFirst)\n'
        f'{indent}\t_, err = conn.Write([]byte(c.httpFirst))\n'
        f'{indent}\tif err != nil {{\n'
        f'{indent}\t\tconn.Close()\n'
        f'{indent}\t\treturn nil, err\n'
        f'{indent}\t}}\n'
        f'{indent}}}\n'
        f'{indent}\n'
    )

    content = content[:idx] + block + content[idx:]
    print("    + httpFirst preface block")
    return content


# ============================================================
#  Phase F-3: 升级为端口感知 preface (patch 10)
# ============================================================

def upgrade_to_port_aware_preface(content):
    """将 http_first 升级为 http_first/https_first 端口感知版本"""

    if 'isHttps' in content:
        print("    ~ port-aware preface already upgraded")
        return content

    old_first = (
        '\t// === KunBox http_first (HTTP preface) ===\n'
        '\t// conn 是原始 TCP 连接，Write 直接进内核 socket buffer，无需 flush\n'
        '\tif c.httpFirst != "" {\n'
        '\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] http_first >>> %q\\n", c.httpFirst)\n'
        '\t\t_, err = conn.Write([]byte(c.httpFirst))\n'
        '\t\tif err != nil {\n'
        '\t\t\tconn.Close()\n'
        '\t\t\treturn nil, err\n'
        '\t\t}\n'
        '\t}\n'
    )

    new_first = (
        '\t// 判断目标是否为 HTTPS (端口 443)\n'
        '\tisHttps := destination.Port == 443 || c.httpsFirst != ""\n'
        '\n'
        '\t// === KunBox http_first / https_first (preface) ===\n'
        '\t// HTTP 和 HTTPS 各自独立的 preface，互不 fallback\n'
        '\tvar firstContent string\n'
        '\tif isHttps {\n'
        '\t\tfirstContent = c.httpsFirst\n'
        '\t} else {\n'
        '\t\tfirstContent = c.httpFirst\n'
        '\t}\n'
        '\tif firstContent != "" {\n'
        '\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] first >>> %q\\n", firstContent)\n'
        '\t\t_, err = conn.Write([]byte(firstContent))\n'
        '\t\tif err != nil {\n'
        '\t\t\tconn.Close()\n'
        '\t\t\treturn nil, err\n'
        '\t\t}\n'
        '\t}\n'
    )

    if old_first in content:
        content = content.replace(old_first, new_first, 1)
        print("    + upgraded to port-aware preface")
    else:
        print("    ! http_first block not found for upgrade")

    return content


# ============================================================
#  Phase F-4: 动态 del headers (patch 10)
# ============================================================

def upgrade_to_dynamic_del_headers(content):
    """将静态 skipHeaders 升级为动态 delHeaders (HTTP/HTTPS 分离)"""

    if 'delHeaders' in content:
        print("    ~ dynamic del headers already upgraded")
        return content

    old_skip = (
        '\tskipHeaders := map[string]bool{\n'
        '\t\t"proxy-connection": true,\n'
        '\t\t"host":             true,\n'
        '\t}\n'
        '\tif c.headers != nil {\n'
        '\t\tfor key, values := range c.headers {\n'
        '\t\t\tif skipHeaders[strings.ToLower(key)] {\n'
        '\t\t\t\tcontinue\n'
        '\t\t\t}\n'
        '\t\t\tfor _, value := range values {\n'
        '\t\t\t\tfmt.Fprintf(&raw, "%s: %s\\r\\n", key, value)\n'
        '\t\t\t}\n'
        '\t\t}\n'
        '\t}\n'
    )

    new_skip = (
        '\t// === KunBox: 构建 del headers 集合 ===\n'
        '\t// 根据 HTTP/HTTPS 选择不同的 del 列表\n'
        '\tdelHeaders := make(map[string]bool)\n'
        '\tdelHeaders["host"] = true\n'
        '\tif isHttps {\n'
        '\t\tfor _, h := range c.httpsDel {\n'
        '\t\t\tdelHeaders[strings.ToLower(h)] = true\n'
        '\t\t}\n'
        '\t} else {\n'
        '\t\tfor _, h := range c.httpDel {\n'
        '\t\t\tdelHeaders[strings.ToLower(h)] = true\n'
        '\t\t}\n'
        '\t}\n'
        '\n'
        '\t// 默认 header（可通过 http_del/https_del 删除）\n'
        '\tif !delHeaders["user-agent"] {\n'
        '\t\tfmt.Fprintf(&raw, "User-Agent: Go-http-client/1.1\\r\\n")\n'
        '\t}\n'
        '\tif !delHeaders["proxy-connection"] {\n'
        '\t\tfmt.Fprintf(&raw, "Proxy-Connection: Keep-Alive\\r\\n")\n'
        '\t}\n'
        '\n'
        '\t// 用户自定义 headers（过滤 delHeaders 中的）\n'
        '\tif c.headers != nil {\n'
        '\t\tfor key, values := range c.headers {\n'
        '\t\t\tif delHeaders[strings.ToLower(key)] {\n'
        '\t\t\t\tcontinue\n'
        '\t\t\t}\n'
        '\t\t\tfor _, value := range values {\n'
        '\t\t\t\tfmt.Fprintf(&raw, "%s: %s\\r\\n", key, value)\n'
        '\t\t\t}\n'
        '\t\t}\n'
        '\t}\n'
    )

    if old_skip in content:
        content = content.replace(old_skip, new_skip, 1)
        print("    + upgraded to dynamic del headers")
    else:
        print("    ! skipHeaders block not found for upgrade")

    return content


# ============================================================
#  Phase F-5: 重写 CONNECT 目标构建 (patch 14)
# ============================================================

def rewrite_connect_target(content):
    """重写 CONNECT 目标: removePort + path 拼接"""

    if 'c.removePort' in content:
        print("    ~ CONNECT target already rewritten")
        return content

    old_target = (
        '\ttarget := destination.String()\n'
        '\tif c.path != "" {\n'
        '\t\ttarget += c.path\n'
        '\t}\n'
    )

    new_target = (
        '\t// --- 构建 CONNECT 目标 ---\n'
        '\t// path 特性: 拼在 host:port 后面 (如 "host:port@gw.alicdn.com")\n'
        '\t// removePort: 去掉端口 (如 "host" 而不是 "host:443")\n'
        '\t// del_host: 不改变 CONNECT 行，只删除 Host header\n'
        '\tvar target string\n'
        '\tif c.removePort {\n'
        '\t\ttarget = destination.Fqdn\n'
        '\t} else {\n'
        '\t\ttarget = destination.String()\n'
        '\t}\n'
        '\tif c.path != "" {\n'
        '\t\ttarget += c.path\n'
        '\t}\n'
    )

    if old_target in content:
        content = content.replace(old_target, new_target, 1)
        print("    + CONNECT target rewritten (removePort + path)")
    else:
        print("    ! CONNECT target block not found")

    return content


# ============================================================
#  Phase F-6: 重写 Host header 构建 (patch 14)
# ============================================================

def rewrite_host_header(content):
    """重写 Host header: del_host + hostOption"""

    if 'hostValue' in content:
        print("    ~ Host header already rewritten")
        return content

    old_host = (
        '\tif c.host != "" {\n'
        '\t\tfmt.Fprintf(&raw, "Host: %s\\r\\n", c.host)\n'
        '\t} else if !c.delHost {\n'
        '\t\tfmt.Fprintf(&raw, "Host: %s\\r\\n", destination.String())\n'
        '\t}\n'
    )

    new_host = (
        '\t// --- Host header ---\n'
        '\t// del_host=true: 完全不发 Host header\n'
        '\t// hostOption: 强制替换 Host 值\n'
        '\t// 默认: Host = destination\n'
        '\tif !c.delHost {\n'
        '\t\tvar hostValue string\n'
        '\t\tif c.hostOption != "" {\n'
        '\t\t\thostValue = c.hostOption\n'
        '\t\t} else if c.host != "" {\n'
        '\t\t\thostValue = c.host\n'
        '\t\t} else {\n'
        '\t\t\thostValue = destination.String()\n'
        '\t\t}\n'
        '\t\tfmt.Fprintf(&raw, "Host: %s\\r\\n", hostValue)\n'
        '\t}\n'
    )

    if old_host in content:
        content = content.replace(old_host, new_host, 1)
        print("    + Host header rewritten (del_host + hostOption)")
    else:
        print("    ! Host header block not found")

    return content


# ============================================================
#  Phase F-7: 重写响应解析 (patch 14)
# ============================================================

def rewrite_response_parsing(content):
    """替换 http.ReadResponse 为手动 ReadString 宽松解析"""

    if 'statusLine, err := reader.ReadString' in content:
        print("    ~ response parsing already rewritten")
        return content

    old_response = (
        '\trequest := &http.Request{\n'
        '\t\tMethod: http.MethodConnect,\n'
        '\t\tURL:    &url.URL{Host: destination.String()},\n'
        '\t}\n'
        '\n'
        '\treader := std_bufio.NewReader(conn)\n'
        '\tresponse, err := http.ReadResponse(reader, request)\n'
        '\tif err != nil {\n'
        '\t\tconn.Close()\n'
        '\t\treturn nil, err\n'
        '\t}\n'
    )

    # 查找并替换整个响应处理块
    if old_response not in content:
        print("    ! old response block not found")
        return content

    # 找到整个 if response.StatusCode == http.StatusOK 块的结束
    start_idx = content.find(old_response)
    # 从 old_response 结束位置开始，找到整个 if-else 块
    search_from = start_idx + len(old_response)

    # 找到 return conn, nil 的最后出现位置（在 else 块中）
    # 简化处理：替换从 old_response 开始到函数 return 的所有内容
    # 查找 else 块的结束
    block_end = content.find('\treturn conn, nil', search_from)
    if block_end >= 0:
        block_end = content.find('\n', block_end) + 1
        old_full = content[start_idx:block_end]
    else:
        old_full = old_response

    new_response = (
        '\t// === Step 3: 宽松响应解析 ===\n'
        '\t// 替换 http.ReadResponse()，接受非标准响应\n'
        '\treader := std_bufio.NewReader(conn)\n'
        '\n'
        '\t// 读取状态行\n'
        '\tstatusLine, err := reader.ReadString(\'\\n\')\n'
        '\tif err != nil {\n'
        '\t\tconn.Close()\n'
        '\t\treturn nil, E.New("failed to read proxy response: ", err)\n'
        '\t}\n'
        '\tstatusLine = strings.TrimSpace(statusLine)\n'
        '\n'
        '\t// 读取 response headers\n'
        '\tvar respHeaders strings.Builder\n'
        '\tfor {\n'
        '\t\tline, readErr := reader.ReadString(\'\\n\')\n'
        '\t\tif line == "\\r\\n" || line == "\\n" || readErr != nil {\n'
        '\t\t\tbreak\n'
        '\t\t}\n'
        '\t\trespHeaders.WriteString(line)\n'
        '\t}\n'
        '\n'
        '\t// 精确检查状态码是否为 200\n'
        '\thasValidStatus := false\n'
        '\t{\n'
        '\t\ttrimmed := strings.TrimSpace(statusLine)\n'
        '\t\tif idx := strings.Index(trimmed, " "); idx >= 0 {\n'
        '\t\t\ttrimmed = trimmed[idx+1:]\n'
        '\t\t}\n'
        '\t\tif strings.HasPrefix(trimmed, "200 ") || trimmed == "200" {\n'
        '\t\t\thasValidStatus = true\n'
        '\t\t}\n'
        '\t}\n'
        '\tif !hasValidStatus {\n'
        '\t\tif respHeaders.Len() > 0 {\n'
        '\t\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy response headers:\\n%s", respHeaders.String())\n'
        '\t\t}\n'
        '\t\tconn.Close()\n'
        '\t\treturn nil, E.New("connect failed: ", statusLine)\n'
        '\t}\n'
        '\n'
        '\t// 连接建立成功\n'
        '\tif respHeaders.Len() > 0 {\n'
        '\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy response headers:\\n%s", respHeaders.String())\n'
        '\t}\n'
        '\n'
        '\tif reader.Buffered() > 0 {\n'
        '\t\tbuffer := buf.NewSize(reader.Buffered())\n'
        '\t\t_, err = buffer.ReadFullFrom(reader, buffer.FreeLen())\n'
        '\t\tif err != nil {\n'
        '\t\t\tconn.Close()\n'
        '\t\t\treturn nil, err\n'
        '\t\t}\n'
        '\t\tconn = bufio.NewCachedConn(conn, buffer)\n'
        '\t}\n'
        '\treturn conn, nil'
    )

    content = content[:start_idx] + new_response + content[block_end:]
    print("    + response parsing rewritten (lenient ReadString)")

    return content


# ============================================================
#  Phase G: Debug 日志 (patch 11)
# ============================================================

def inject_debug_logging(content):
    """在关键路径添加 stderr 日志"""

    changes = 0

    # 1. dial 失败日志
    old_dial = (
        'conn, err := c.dialer.DialContext(ctx, N.NetworkTCP, c.serverAddr)\n'
        '\tif err != nil {\n'
        '\t\treturn nil, err\n'
        '\t}'
    )
    new_dial = (
        'conn, err := c.dialer.DialContext(ctx, N.NetworkTCP, c.serverAddr)\n'
        '\tif err != nil {\n'
        '\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy FAILED: %s err=%v\\n", c.serverAddr, err)\n'
        '\t\treturn nil, err\n'
        '\t}\n'
        '\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy OK: %s\\n", c.serverAddr)'
    )
    if old_dial in content and '[KunBox-HTTP] dial to proxy FAILED' not in content:
        content = content.replace(old_dial, new_dial, 1)
        changes += 1
        print("    + dial log")

    # 2. httpFirst/httpsFirst 写入失败日志 (端口感知版本)
    old_first_err = (
        '\t\t_, err = conn.Write([]byte(firstContent))\n'
        '\t\tif err != nil {\n'
        '\t\t\tconn.Close()\n'
        '\t\t\treturn nil, err\n'
        '\t\t}'
    )
    new_first_err = (
        '\t\t_, err = conn.Write([]byte(firstContent))\n'
        '\t\tif err != nil {\n'
        '\t\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] first write FAILED: err=%v\\n", err)\n'
        '\t\t\tconn.Close()\n'
        '\t\t\treturn nil, err\n'
        '\t\t}'
    )
    if old_first_err in content and 'first write FAILED' not in content:
        content = content.replace(old_first_err, new_first_err, 1)
        changes += 1
        print("    + first write error log")

    # 3. CONNECT 写入日志
    old_connect = (
        '\t_, err = conn.Write([]byte(raw.String()))\n'
        '\tif err != nil {\n'
        '\t\tconn.Close()\n'
        '\t\treturn nil, err\n'
        '\t}'
    )
    new_connect = (
        '\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT >>> %s", raw.String())\n'
        '\t_, err = conn.Write([]byte(raw.String()))\n'
        '\tif err != nil {\n'
        '\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT write FAILED: err=%v\\n", err)\n'
        '\t\tconn.Close()\n'
        '\t\treturn nil, err\n'
        '\t}'
    )
    if old_connect in content and 'CONNECT >>>' not in content:
        content = content.replace(old_connect, new_connect, 1)
        changes += 1
        print("    + CONNECT write log")

    # 4. ReadFullFrom 失败日志 (在宽松解析后的 buffer 块中)
    old_full = (
        '\t\t_, err = buffer.ReadFullFrom(reader, buffer.FreeLen())\n'
        '\t\tif err != nil {\n'
        '\t\t\tconn.Close()\n'
        '\t\t\treturn nil, err\n'
        '\t\t}'
    )
    new_full = (
        '\t\t_, err = buffer.ReadFullFrom(reader, buffer.FreeLen())\n'
        '\t\tif err != nil {\n'
        '\t\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] ReadFullFrom FAILED: err=%v\\n", err)\n'
        '\t\t\tconn.Close()\n'
        '\t\t\treturn nil, err\n'
        '\t\t}'
    )
    if old_full in content and 'ReadFullFrom FAILED' not in content:
        content = content.replace(old_full, new_full, 1)
        changes += 1
        print("    + ReadFullFrom log")

    # 5. 宽松解析的状态行日志 (F-7 之后才存在)
    if 'statusLine = strings.TrimSpace(statusLine)' in content and 'proxy status line' not in content:
        old_status = '\tstatusLine = strings.TrimSpace(statusLine)'
        new_status = (
            '\tstatusLine = strings.TrimSpace(statusLine)\n'
            '\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy status line: %q\\n", statusLine)'
        )
        content = content.replace(old_status, new_status, 1)
        changes += 1
        print("    + status line log")

    if changes == 0:
        print("    ~ debug logging already present or blocks not found")
    else:
        print(f"    + {changes} debug log points added")

    # 6. TLS 握手日志 (在 TLS ConnectionState 之后)
    if 'state := tlsConn.ConnectionState()' in content and 'TLS:' not in content:
        old_tls = '\t\tstate := tlsConn.ConnectionState()'
        new_tls = (
            '\t\tstate := tlsConn.ConnectionState()\n'
            '\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] TLS: version=%x cipher=%x server=%q\\n",\n'
            '\t\t\tstate.Version, state.CipherSuite, state.ServerName)'
        )
        content = content.replace(old_tls, new_tls, 1)
        changes += 1
        print("    + TLS handshake log")

    return content


# ============================================================
#  Phase H: Logger 替换 stderr (patch 15, 必须最后!)
# ============================================================

def replace_stderr_with_logger(content):
    """所有 fmt.Fprintf(os.Stderr, ...) → if c.logger != nil { c.logger.xxx() } else { fmt.Fprintf(os.Stderr, ...) }"""

    # 精确替换对: (old, new)
    # 每个替换加 nil check：logger 可用时走 logger，否则 fallback 到 stderr
    replacements = [
        # dial FAILED
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy FAILED: %s err=%v\\n", c.serverAddr, err)',
            'if c.logger != nil { c.logger.ErrorContext(ctx, "HTTP CONNECT: dial to proxy FAILED: ", c.serverAddr, " err=", err) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy FAILED: %s err=%v\\n", c.serverAddr, err) }'
        ),
        # dial OK
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy OK: %s\\n", c.serverAddr)',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: dial to proxy OK: ", c.serverAddr) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] dial to proxy OK: %s\\n", c.serverAddr) }'
        ),
        # TLS handshake
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] TLS: version=%x cipher=%x server=%q\\n",\n\t\t\tstate.Version, state.CipherSuite, state.ServerName)',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: TLS version=", fmt.Sprintf("%x", state.Version), " cipher=", fmt.Sprintf("%x", state.CipherSuite), " server=", state.ServerName) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] TLS: version=%x cipher=%x server=%q\\n", state.Version, state.CipherSuite, state.ServerName) }'
        ),
        # first write FAILED
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] first write FAILED: err=%v\\n", err)',
            'if c.logger != nil { c.logger.ErrorContext(ctx, "HTTP CONNECT: first write FAILED: err=", err) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] first write FAILED: err=%v\\n", err) }'
        ),
        # first >>> log
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] first >>> %q\\n", firstContent)',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: first >>> ", firstContent) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] first >>> %q\\n", firstContent) }'
        ),
        # CONNECT >>> + write FAILED (matches Phase G injection order: log → write → err)
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT >>> %s", raw.String())\n'
            '\t_, err = conn.Write([]byte(raw.String()))\n'
            '\tif err != nil {\n'
            '\t\tfmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT write FAILED: err=%v\\n", err)',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: >>> ", strings.TrimRight(raw.String(), "\\r\\n")) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT >>> %s", raw.String()) }\n'
            '\t_, err = conn.Write([]byte(raw.String()))\n'
            '\tif err != nil {\n'
            '\t\tif c.logger != nil { c.logger.ErrorContext(ctx, "HTTP CONNECT: write FAILED: err=", err) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT write FAILED: err=%v\\n", err) }'
        ),
        # CONNECT >>> (standalone, if no Phase G injection)
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT >>> %s", raw.String())',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: >>> ", strings.TrimRight(raw.String(), "\\r\\n")) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT >>> %s", raw.String()) }'
        ),
        # CONNECT write FAILED (standalone, original order)
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT write FAILED: err=%v\\n", err)',
            'if c.logger != nil { c.logger.ErrorContext(ctx, "HTTP CONNECT: write FAILED: err=", err) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] CONNECT write FAILED: err=%v\\n", err) }'
        ),
        # read status line FAILED
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] read status line FAILED: err=%v\\n", err)',
            'if c.logger != nil { c.logger.ErrorContext(ctx, "HTTP CONNECT: read status FAILED: err=", err) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] read status line FAILED: err=%v\\n", err) }'
        ),
        # proxy status line
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy status line: %q\\n", statusLine)',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: status: ", statusLine) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy status line: %q\\n", statusLine) }'
        ),
        # proxy response (old ReadResponse version, if somehow present)
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy response: %d %s\\n", response.StatusCode, response.Status)',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: response: ", response.StatusCode, " ", response.Status) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy response: %d %s\\n", response.StatusCode, response.Status) }'
        ),
        # ReadFullFrom FAILED
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] ReadFullFrom FAILED: err=%v\\n", err)',
            'if c.logger != nil { c.logger.ErrorContext(ctx, "HTTP CONNECT: ReadFullFrom FAILED: err=", err) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] ReadFullFrom FAILED: err=%v\\n", err) }'
        ),
        # httpFirst write FAILED (旧版本)
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] httpFirst write FAILED: err=%v\\n", err)',
            'if c.logger != nil { c.logger.ErrorContext(ctx, "HTTP CONNECT: httpFirst write FAILED: err=", err) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] httpFirst write FAILED: err=%v\\n", err) }'
        ),
        # proxy response headers (respHeaders)
        (
            'fmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy response headers:\\n%s", respHeaders.String())',
            'if c.logger != nil { c.logger.InfoContext(ctx, "HTTP CONNECT: response headers:\\n", respHeaders.String()) } else { fmt.Fprintf(os.Stderr, "[KunBox-HTTP] proxy response headers:\\n%s", respHeaders.String()) }'
        ),
    ]

    changes = 0
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changes += 1

    # outbound.go 中的 stderr (如果 content 是 outbound.go 的话)
    # 这个在 patch_outbound 中已处理

    if changes > 0:
        print(f"    + {changes} stderr → logger replacements")
    else:
        print("    ~ no stderr to replace (already done or not found)")

    return content


# ============================================================
#  Phase I: 清理无用 import
# ============================================================

def cleanup_imports(content):
    """移除不再使用的 import"""

    # os — 检查是否还有 os.Stderr / os.ErrInvalid 等
    # 注意: ListenPacket 方法使用 os.ErrInvalid, 必须保留 os 导入
    has_os_usage = 'os.Stderr' in content or 'os.ErrInvalid' in content
    if not has_os_usage:
        # 确保 ListenPacket 需要的 os 导入存在
        content = ensure_import(content, 'os', '"os"')
        print("    ~ ensured os import (ListenPacket needs os.ErrInvalid)")

    # net/url — 检查是否还有 url.URL
    if 'url.URL' not in content and '"net/url"' in content:
        content = content.replace('\t"net/url"\n', '')
        print("    - removed unused net/url import")

    return content


# ============================================================
#  主入口
# ============================================================

def main():
    print("=" * 60)
    print("KunBox Unified Patch")
    print("=" * 60)

    # 验证文件存在
    for path, desc in [(OPTS_PATH, 'option/simple.go'),
                        (OUTBOUND_PATH, 'outbound.go'),
                        (CLIENT_PATH, 'client.go')]:
        if not os.path.exists(path):
            print(f"ERROR: {desc} not found: {path}")
            sys.exit(1)
        print(f"  ✓ {desc}")

    print()

    # ---- 1. option/simple.go ----
    print("--- [1/3] option/simple.go ---")
    content = read_file(OPTS_PATH)
    content = patch_options(content)
    write_file(OPTS_PATH, content)
    print()

    # ---- 2. outbound.go ----
    print("--- [2/3] outbound.go ---")
    content = read_file(OUTBOUND_PATH)
    content = patch_outbound(content)
    write_file(OUTBOUND_PATH, content)
    print()

    # ---- 3. client.go ----
    print("--- [3/3] client.go ---")
    content = read_file(CLIENT_PATH)
    content = patch_client(content)
    write_file(CLIENT_PATH, content)
    print()

    print("=" * 60)
    print("Done! All patches applied.")
    print("=" * 60)


if __name__ == '__main__':
    main()
