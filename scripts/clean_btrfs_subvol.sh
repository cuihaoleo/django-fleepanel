#!/bin/bash

# 在 LXC 容器中创建 btrfs subvolume 会导致无法正常删除容器：
# https://github.com/lxc/lxc/issues/210
# 可以把这个脚本加入 lxc.hook.post-stop 中
# 或 lxc.hook.destroy 中（需要很新的 lxc 版本）。

set -e
LC_ALL=C

btrfs subvol list -o /var/lib/lxd/lxc/bt1 \
| cut -d@ -f2 \
| while read path; do
    if [[ "$path" == "$LXC_ROOTFS_PATH"?* ]]; then
        btrfs subvol delete $path
    fi
done
