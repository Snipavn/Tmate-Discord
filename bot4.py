import os
import discord
import asyncio
import uuid
import time
import shutil
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
deploy_cooldowns = {}
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

def get_latest_user_vps(user_id):
    latest_folder = None
    with open(database_file, "r") as f:
        for line in reversed(f.readlines()):
            parts = line.strip().split(",")
            if len(parts) == 2 and str(user_id) == parts[0]:
                latest_folder = parts[1]
                break
    return latest_folder

def count_active_vps():
    if not os.path.exists(database_file):
        return 0
    count = 0
    with open(database_file, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 2:
                folder = parts[1]
                ssh_file = os.path.join(folder, "root/ssh.txt")
                if os.path.exists(ssh_file):
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
curl -s https://sshx.io/get | sh &&
/root/.sshx/bin/sshx serve > /root/ssh.txt
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
curl -s https://sshx.io/get | sh &&
/root/.sshx/bin/sshx serve > /root/ssh.txt
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

@bot.tree.command(name="deploy", description="Khởi tạo VPS dùng sshx.io")
@app_commands.describe(os_type="Hệ điều hành muốn dùng: ubuntu hoặc alpine")
async def deploy(interaction: discord.Interaction, os_type: str = "ubuntu"):
    await interaction.response.defer(ephemeral=True)

    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.followup.send("❌ Bạn không thể dùng lệnh này ở đây.", ephemeral=True)
        return

    user = interaction.user
    user_id = user.id

    now = time.time()
    last_used = deploy_cooldowns.get(user_id, 0)
    if now - last_used < 60:
        remaining = int(60 - (now - last_used))
        await interaction.followup.send(f"⏱️ Vui lòng đợi {remaining}s trước khi dùng lại lệnh `/deploy`.", ephemeral=True)
        return

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
        await dm.send(f"🚀 Đang cài VPS `{os_type}`... Xem log ở đây.")
    except discord.Forbidden:
        await interaction.followup.send("❌ Không thể gửi DM. Vui lòng bật tin nhắn riêng.", ephemeral=True)
        return

    folder = f"vps/{user_id}_{uuid.uuid4().hex[:6]}"
    user_states[user_id] = True
    register_user_vps(user_id, folder)
    deploy_cooldowns[user_id] = time.time()

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
            if now - last_update > 0.0001:
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

@bot.tree.command(name="deletevps", description="Xóa toàn bộ VPS bạn đã tạo")
async def deletevps(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user = interaction.user
    user_id = str(user.id)
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

    await interaction.followup.send(f"🗑️ Đã xóa `{deleted}` VPS của bạn.", ephemeral=True)

@bot.tree.command(name="statusvps", description="Xem trạng thái CPU, RAM VPS của bạn")
async def statusvps(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user = interaction.user
    folder = get_latest_user_vps(user.id)

    if not folder or not os.path.exists(folder):
        await interaction.followup.send("❌ Bạn chưa có VPS nào đang chạy.", ephemeral=True)
        return

    proot_path = os.path.join(folder, "usr/local/bin/proot")
    if not os.path.exists(proot_path):
        await interaction.followup.send("⚠️ VPS không đầy đủ hoặc chưa cài xong.", ephemeral=True)
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

    await interaction.followup.send(f"📊 **Trạng thái VPS:**\n```{output}```", ephemeral=True)

async def update_status_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        count = count_active_vps()
        await bot.change_presence(activity=discord.Game(name=f"💖 {count}VPS SSHX"))
        await asyncio.sleep(60)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot đã sẵn sàng. Đăng nhập với {bot.user}")
    bot.loop.create_task(update_status_task())

bot.run(TOKEN)
