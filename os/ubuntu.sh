#!/bin/sh

ROOTFS_DIR=$(pwd)
ARCH=$(uname -m)
case $ARCH in
  x86_64) ARCH_ALT=amd64 ;;
  aarch64) ARCH_ALT=arm64 ;;
  *)
    echo "Unsupported arch $ARCH"
    exit 1
    ;;
esac

if [ ! -e "$ROOTFS_DIR/.installed" ]; then
  mkdir -p "$ROOTFS_DIR"
  wget -qO- "http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-${ARCH_ALT}.tar.gz" | tar -xz -C "$ROOTFS_DIR"

  wget -O "$ROOTFS_DIR/usr/local/bin/proot" "https://raw.githubusercontent.com/dxomg/vpsfreepterovm/main/proot-${ARCH}"
  chmod 755 "$ROOTFS_DIR/usr/local/bin/proot"

  echo "nameserver 1.1.1.1" > "$ROOTFS_DIR/etc/resolv.conf"
  touch "$ROOTFS_DIR/.installed"
fi

echo "SERVER_TIPAC_VN - UBUNTU"
echo "------------------------"

"$ROOTFS_DIR/usr/local/bin/proot" -0 -w /root \
  -b /dev -b /sys -b /proc -b /etc/resolv.conf \
  --rootfs="$ROOTFS_DIR" /bin/bash -c 'su -c "
    apt update &&
    apt install sudo neofetch systemctl tmate -y &&
    tmate -F > /root/ssh.txt &
  "; exec bash'
