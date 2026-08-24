#!/bin/bash
set -e

source "buildScript/init/env.sh"
ENV_NB4A=1
source "buildScript/lib/core/get_source_env.sh"
# 记下仓库根目录：get_source.sh 后续会 pushd .. 到仓库父目录，
# 而 kunbox-patch/ 在仓库内，必须用仓库根绝对路径引用补丁脚本
NB4A_REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../../.." && pwd)"
pushd ..

####

if [ ! -d "sing-box" ]; then
  git clone --no-checkout https://github.com/MatsuriDayo/sing-box.git
fi
pushd sing-box
git checkout "$COMMIT_SING_BOX"
popd

####

if [ ! -d "libneko" ]; then
  git clone --no-checkout https://github.com/MatsuriDayo/libneko.git
fi
pushd libneko
git checkout "$COMMIT_LIBNEKO"
popd

####

# KunBox del_host 补丁：克隆打补丁所需的 sagernet/sing (v0.7.18) 到 ../sing
if [ ! -d "sing" ]; then
  git clone --no-checkout https://github.com/sagernet/sing.git sing
fi
pushd sing
git checkout "v0.7.18"
popd

# 启用 go.mod 里的 replace，指向本地打过补丁的 sing
# (kunbox-patch/ 下的补丁由 nekobox_http_patch.py 应用)
sed -i 's|^//replace github.com/sagernet/sing => ../sing|replace github.com/sagernet/sing => ../sing|' sing-box/go.mod

# 应用 del_host 补丁：sing-box 两处(option/simple.go + protocol/http/outbound.go) + sing 一处(protocol/http/client.go)
[ -f "$NB4A_REPO/kunbox-patch/nekobox_http_patch.py" ] || { echo "PATCH SCRIPT MISSING at $NB4A_REPO/kunbox-patch/"; exit 1; }
python3 "$NB4A_REPO/kunbox-patch/nekobox_http_patch.py" sing-box sing

# 补丁脚本只警告、不自动修 import：补丁用 strings.Builder/fmt.Fprintf（需加 strings/fmt），
# 且不再使用 net/url（不删会 imported and not used 编译失败）
python3 - <<'PY'
p = "sing/protocol/http/client.go"
s = open(p).read(); ch = False
if '"strings"' not in s:
    s = s.replace('\t"context"\n', '\t"context"\n\t"strings"\n', 1); ch = True
if '"fmt"' not in s:
    s = s.replace('\t"encoding/base64"\n', '\t"encoding/base64"\n\t"fmt"\n', 1); ch = True
if 'net/url' in s:
    s = s.replace('\t"net/url"\n', '', 1); ch = True
open(p, 'w').write(s)
print("sing client.go imports:", "updated" if ch else "ok")
PY

# 校验补丁确实生效，否则让构建失败（脚本自身不返回非零）
grep -q "DelHost" sing-box/option/simple.go || { echo "PATCH FAILED: simple.go 未注入 DelHost"; exit 1; }
grep -q "raw TCP CONNECT" sing/protocol/http/client.go || { echo "PATCH FAILED: client.go 未替换 DialContext"; exit 1; }
echo "del_host 补丁已应用 ✓"

####

popd
