import os
import asyncio
import uuid
import time
import shutil
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)

load_dotenv()
BOT_TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895  # Telegram ID (chỉ phần số nguyên)
USER_VPS_LIMIT = 2

user_states = {}
deploy_cooldowns = {}
database_file = "database.txt"
os.makedirs("vps", exist_ok=True)
if not os.path.exists(database_file):
    open(database_file, "w").close()

def count_user_vps(user_id):
    with open(database_file, "r") as f:
        return sum(1 for line in f if line.startswith(str(user_id)))

def register_user_vps(user_id, folder):
    with open(database_file, "a") as f:
        f.write(f"{user_id},{folder}\n")

def get_latest_user_vps(user_id):
    with open(database_file, "r") as f:
        for line in reversed(f.readlines()):
            parts = line.strip().split(",")
            if len(parts) == 2 and str(user_id) == parts[0]:
                return parts[1]
    return None

def count_active_vps():
    count = 0
    with open(database_file, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 2:
                folder = parts[1]
                if os.path.exists(os.path.join(folder, "root/ssh.txt")):
                    count += 1
    return count

def create_script(folder, os_type):
    arch = os.uname().machine
    arch_alt = "arm64" if arch == "aarch64" else "amd64"
    proot_url = f"https://raw.githubusercontent.com/dxomg/vpsfreepterovm/main/proot-{arch}"
    os.makedirs(folder, exist_ok=True)
    script_path = os.path.join(folder, "start.sh")

    if os_type == "ubuntu":
        rootfs_url = f"http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-{arch_alt}.tar.gz"
        commands = f"""
wget -qO- "{rootfs_url}" | tar -xz
wget -O usr/local/bin/proot "{proot_url}" && chmod 755 usr/local/bin/proot
echo "nameserver 1.1.1.1" > etc/resolv.conf
./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf --rootfs=. /bin/bash -c '
apt update &&
apt install curl openssh-client -y &&
curl -sSf https://sshx.io/get | sh -s download &&
mv sshx /root/sshx &&
chmod +x /root/sshx
'
"""
    else:
        rootfs_url = f"https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/{arch}/alpine-minirootfs-3.18.3-{arch}.tar.gz"
        commands = f"""
wget -qO- "{rootfs_url}" | tar -xz
wget -O usr/local/bin/proot "{proot_url}" && chmod 755 usr/local/bin/proot
echo "nameserver 1.1.1.1" > etc/resolv.conf
./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf --rootfs=. /bin/sh -c '
apk update &&
apk add curl openssh-client &&
curl -sSf https://sshx.io/get | sh -s download &&
mv sshx /root/sshx &&
chmod +x /root/sshx
'
"""

    with open(script_path, "w") as f:
        f.write(f"""#!/bin/bash
cd "$(dirname "$0")"
{commands}""")
    os.chmod(script_path, 0o755)
    return script_path

async def wait_for_ssh(folder):
    ssh_file = os.path.join(folder, "root/ssh.txt")
    for _ in range(60):
        if os.path.exists(ssh_file):
            with open(ssh_file, "r") as f:
                return f.read()
        await asyncio.sleep(2)
    return "❌ Không tìm thấy SSH Link sau 2 phút."

async def deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    os_type = context.args[0] if context.args else "ubuntu"

    if os_type not in ["ubuntu", "alpine"]:
        await update.message.reply_text("❌ OS không hợp lệ. Dùng `/deploy ubuntu` hoặc `/deploy alpine`.")
        return

    now = time.time()
    last_used = deploy_cooldowns.get(user_id, 0)
    if now - last_used < 60:
        remaining = int(60 - (now - last_used))
        await update.message.reply_text(f"⏱️ Vui lòng đợi {remaining}s trước khi dùng lại.")
        return

    if user_id != OWNER_ID and count_user_vps(user_id) >= USER_VPS_LIMIT:
        await update.message.reply_text("🚫 Bạn đã đạt giới hạn VPS hôm nay.")
        return

    if user_id in user_states:
        await update.message.reply_text("⚠️ Bạn đang deploy VPS khác, vui lòng đợi.")
        return

    folder = f"vps/{user_id}_{uuid.uuid4().hex[:6]}"
    user_states[user_id] = True
    register_user_vps(user_id, folder)
    deploy_cooldowns[user_id] = time.time()

    msg = await update.message.reply_text(f"🚀 Đang cài VPS `{os_type}`...\n⏳ Đợi log...")

    create_script(folder, os_type)
    process = await asyncio.create_subprocess_shell(
        "./start.sh",
        cwd=folder,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    log_buffer = ""

    async def stream_output():
        nonlocal log_buffer
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded = line.decode(errors="ignore").strip()
            log_buffer += decoded + "\n"
            if len(log_buffer) > 1900:
                log_buffer = log_buffer[-1900:]
            try:
                await msg.edit_text(f"📦 Log:\n```{log_buffer}```", parse_mode="Markdown")
            except:
                pass

    await asyncio.gather(stream_output(), process.wait())

    sshx_cmd = """./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf --rootfs=. /bin/sh -c '/root/sshx > /root/ssh.txt &'"""
    await asyncio.create_subprocess_shell(sshx_cmd, cwd=folder)

    ssh_url = await wait_for_ssh(folder)
    await context.bot.send_message(chat_id=user_id, text=f"🔗 SSH Link:\n`{ssh_url}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=user_id, text="✅ VPS đã sẵn sàng!")

    user_states.pop(user_id, None)

async def deletevps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    deleted = 0
    with open(database_file, "r") as f:
        lines = f.readlines()

    remaining_lines = []
    for line in lines:
        if line.startswith(user_id):
            parts = line.strip().split(",")
            if len(parts) == 2:
                folder = parts[1]
                if os.path.exists(folder):
                    try:
                        shutil.rmtree(folder)
                        deleted += 1
                    except Exception as e:
                        print(f"❌ Không thể xóa {folder}: {e}")
                continue
        remaining_lines.append(line)

    with open(database_file, "w") as f:
        f.writelines(remaining_lines)

    await update.message.reply_text(f"🗑️ Đã xóa `{deleted}` VPS của bạn.")

async def statusvps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    folder = get_latest_user_vps(user_id)

    if not folder or not os.path.exists(folder):
        await update.message.reply_text("❌ Bạn chưa có VPS nào đang chạy.")
        return

    cmd = f"""./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf --rootfs=. /bin/sh -c 'top -b -n1 | head -n 10'"""
    process = await asyncio.create_subprocess_shell(
        cmd,
        cwd=folder,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
        output = stdout.decode(errors="ignore").strip()
    except asyncio.TimeoutError:
        output = "⏱️ VPS phản hồi quá lâu hoặc không phản hồi."

    await update.message.reply_text(f"📊 **Trạng thái VPS:**\n```{output}```", parse_mode="Markdown")

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("deploy", deploy))
    app.add_handler(CommandHandler("deletevps", deletevps))
    app.add_handler(CommandHandler("statusvps", statusvps))
    print("✅ Telegram bot đang chạy...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
