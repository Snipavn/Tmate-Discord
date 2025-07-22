import os
import discord
import asyncio
import uuid
import time
from discord import app_commands
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

bot = MyBot()

user_states = {}
database_file = "database.txt"
os.makedirs("vps", exist_ok=True)
if not os.path.exists(database_file):
    open(database_file, "w").close()

USER_VPS_LIMIT = 2

def count_user_vps(user_id):
    with open(database_file, "r") as f:
        return sum(1 for line in f if line.startswith(str(user_id)))

def register_user_vps(user_id, folder):
    with open(database_file, "a") as f:
        f.write(f"{user_id},{folder}\n")

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
./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf --rootfs=. /bin/bash -c 'su -c "
apt update &&
apt install sudo curl openssh-client neofetch -y &&
curl -s https://sshx.io/get | sh &&
sleep 10 &&
/root/.sshx/bin/sshx serve > /root/ssh.txt
"; exec bash'
"""
    else:
        rootfs_url = f"https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/{arch}/alpine-minirootfs-3.18.3-{arch}.tar.gz"
        commands = f"""
wget -qO- "{rootfs_url}" | tar -xz
wget -O usr/local/bin/proot "{proot_url}" && chmod 755 usr/local/bin/proot
echo "nameserver 1.1.1.1" > etc/resolv.conf
./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf --rootfs=. /bin/sh -c 'su -c "
apk update &&
apk add bash curl openssh-client coreutils neofetch &&
curl -s https://sshx.io/get | sh &&
sleep 10 &&
/root/.sshx/bin/sshx serve > /root/ssh.txt
"; exec sh'
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

@bot.tree.command(name="deploy", description="Khởi tạo VPS dùng sshx.io")
@app_commands.describe(os_type="Hệ điều hành muốn dùng: ubuntu hoặc alpine")
async def deploy(interaction: discord.Interaction, os_type: str = "ubuntu"):
    await interaction.response.defer(ephemeral=True)

    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.followup.send("❌ Bạn không thể dùng lệnh này ở đây.", ephemeral=True)
        return

    user = interaction.user
    user_id = user.id

    if user_id != OWNER_ID and count_user_vps(user_id) >= USER_VPS_LIMIT:
        await interaction.followup.send("🚫 Bạn đã đạt giới hạn VPS hôm nay.", ephemeral=True)
        return

    if user_id in user_states:
        await interaction.followup.send("⚠️ Bạn đang deploy VPS khác, vui lòng đợi.", ephemeral=True)
        return

    os_type = os_type.lower()
    if os_type not in ["ubuntu", "alpine"]:
        await interaction.followup.send("❌ OS không hợp lệ. Dùng `ubuntu` hoặc `alpine`.", ephemeral=True)
        return

    try:
        dm = await user.create_dm()
        await dm.send(f"🚀 Đang cài VPS `{os_type}` của m... Xem log ở DM.")
    except discord.Forbidden:
        await interaction.followup.send("❌ Không thể gửi DM. Vui lòng bật tin nhắn riêng.", ephemeral=True)
        return

    folder = f"vps/{user_id}_{uuid.uuid4().hex[:6]}"
    user_states[user_id] = True
    register_user_vps(user_id, folder)

    log_msg = await dm.send("📦 Đang xử lý VPS...")

    create_script(folder, os_type)
    process = await asyncio.create_subprocess_shell(
        "./start.sh",
        cwd=folder,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    log_buffer = ""
    ssh_url = ""

    async def stream_output():
        nonlocal log_buffer, ssh_url
        last_update = 0

        while True:
            line = await process.stdout.readline()
            if not line:
                break

            decoded = line.decode(errors="ignore").strip()
            log_buffer += decoded + "\n"

            if "sshx.io" in decoded and not ssh_url:
                ssh_url = decoded
                await dm.send(f"🔗 SSH Link: `{ssh_url}`")

            now = time.time()
            if now - last_update > 0.5:
                try:
                    await log_msg.edit(content=f"📦 Log:\n```{log_buffer[-1900:]}```")
                    last_update = now
                except discord.HTTPException:
                    pass

    await asyncio.gather(stream_output(), process.wait())

    if not ssh_url:
        ssh_url = await wait_for_ssh(folder)
        await dm.send(f"🔗 SSH Link: `{ssh_url}`")

    await dm.send("✅ VPS đã sẵn sàng!")
    user_states.pop(user_id, None)

    await interaction.followup.send("✅ VPS đã được tạo! Kiểm tra DM của bạn.", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot đã sẵn sàng. Đăng nhập với {bot.user}")

bot.run(TOKEN)
