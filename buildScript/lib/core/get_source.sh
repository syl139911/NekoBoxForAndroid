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
# aed32ee 的 go.mod 该行原为 "// replace github.com/sagernet/sing => ../sing" (// 后有空格)。
# 关键坑：CI 中 get_source.sh 与真正的 gomobile 编译 cwd 嵌套层级不同，
# 相对路径 "../sing" 在编译时解析不到被打补丁的 sing -> 仍用原版 -> unknown field DelHost。
# 因此改成【绝对路径】，彻底消除 cwd 歧义。
SING_ABS="$(pwd)/sing"
if [ ! -f "$SING_ABS/go.mod" ]; then echo "SING NOT CLONED at $SING_ABS"; exit 1; fi
sed -i "s|^//[[:space:]]*replace github.com/sagernet/sing => .*|replace github.com/sagernet/sing => $SING_ABS|" sing-box/go.mod
sed -i "s|^replace github.com/sagernet/sing => .*|replace github.com/sagernet/sing => $SING_ABS|" sing-box/go.mod
if ! grep -q "^replace github.com/sagernet/sing => $SING_ABS" sing-box/go.mod; then echo "REPLACE UNCOMMENT FAILED -> 无法指向本地补丁 sing"; exit 1; fi
echo "go.mod replace 已解开 ✓ (绝对路径: $SING_ABS)"
echo "  校验补丁 sing 的 Options 含 DelHost: $(grep -c 'DelHost' "$SING_ABS/protocol/http/client.go" 2>/dev/null || echo 0) 处"

# 应用 del_host 补丁：直接复制 old-main 验证过的补丁后源码
PATCHED="$NB4A_REPO/kunbox-patch/patched-source"
[ -f "$PATCHED/option/simple.go" ] || { echo "PATCHED SOURCE MISSING: $PATCHED/option/simple.go"; exit 1; }
[ -f "$PATCHED/protocol/http/outbound.go" ] || { echo "PATCHED SOURCE MISSING: $PATCHED/protocol/http/outbound.go"; exit 1; }
[ -f "$PATCHED/protocol/http/client.go" ] || { echo "PATCHED SOURCE MISSING: $PATCHED/protocol/http/client.go"; exit 1; }
cp "$PATCHED/option/simple.go" sing-box/option/simple.go
cp "$PATCHED/protocol/http/outbound.go" sing-box/protocol/http/outbound.go
cp "$PATCHED/protocol/http/client.go" sing/protocol/http/client.go
echo "补丁文件已复制 ✓"

# 校验补丁确实生效
grep -q "DelHost" sing-box/option/simple.go || { echo "PATCH FAILED: simple.go 未包含 DelHost"; exit 1; }
grep -q "delHost" sing/protocol/http/client.go || { echo "PATCH FAILED: client.go 未包含 delHost"; exit 1; }
echo "del_host 补丁已应用 ✓"

# 修改 libcore/go.mod 的 replace sing 为绝对路径（gomobile 会在 .build/src-android-* 里 copy，相对路径会错）
LIBCORE_MOD="$NB4A_REPO/libcore/go.mod"
if [ -f "$LIBCORE_MOD" ]; then
  sed -i "s|^replace github.com/sagernet/sing => .*|replace github.com/sagernet/sing => $SING_ABS|" "$LIBCORE_MOD"
  echo "libcore/go.mod replace sing => $SING_ABS ✓"
else
  echo "libcore/go.mod not found at $LIBCORE_MOD"
fi

####

popd
