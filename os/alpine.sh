#!/bin/sh

ROOTFS_DIR=$(pwd)
ARCH=$(uname -m)
case $ARCH in
  x86_64) ARCH_ALT=x86_64 ;;
  aarch64) ARCH_ALT=aarch64 ;;
  *)
    echo "Unsupported arch $ARCH"
    exit 1
    ;;
esac

if [ ! -e "$ROOTFS_DIR/.installed" ]; then
  mkdir -p "$ROOTFS_DIR"
  wget -qO- "https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/${ARCH_ALT}/alpine-minirootfs-3.18.3-${ARCH_ALT}.tar.gz" | tar -xz -C "$ROOTFS_DIR"

  wget -O "$ROOTFS_DIR/usr/local/bin/proot" "https://raw.githubusercontent.com/dxomg/vpsfreepterovm/main/proot-${ARCH}"
  chmod 755 "$ROOTFS_DIR/usr/local/bin/proot"

  echo "nameserver 1.1.1.1" > "$ROOTFS_DIR/etc/resolv.conf"
  touch "$ROOTFS_DIR/.installed"
fi

echo "SERVER_TIPAC_VN - ALPINE"
echo "------------------------"

"$ROOTFS_DIR/usr/local/bin/proot" -0 -w /root \
  -b /dev -b /sys -b /proc -b /etc/resolv.conf \
  --rootfs="$ROOTFS_DIR" /bin/sh -c 'su -c "
    apk update &&
    apk add bash coreutils tmate neofetch &&
    tmate -F > /root/ssh.txt &
  "; exec sh'
