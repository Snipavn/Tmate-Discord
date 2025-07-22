import os
import discord
import asyncio
import uuid
import time
import shutil
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

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

    bin_dir = os.path.join(folder, "sshx_bin")
    os.makedirs(bin_dir, exist_ok=True)

    commands = ""
    if os_type == "ubuntu":
        rootfs_url = f"http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-{arch_alt}.tar.gz"
        commands = f"""
wget -qO- "{rootfs_url}" | tar -xz
wget -O usr/local/bin/proot "{proot_url}" && chmod 755 usr/local/bin/proot
echo "nameserver 1.1.1.1" > etc/resolv.conf
cd root || exit
curl -s https://sshx.io/get | sh
cd ..
./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf -b sshx_bin:/root/.sshx:ro --rootfs=. /bin/bash -c '
apt update &&
apt install curl openssh-client -y &&
/root/.sshx/bin/sshx serve > /root/ssh.txt
'
"""
    else:
        rootfs_url = f"https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/{arch}/alpine-minirootfs-3.18.3-{arch}.tar.gz"
        commands = f"""
wget -qO- "{rootfs_url}" | tar -xz
wget -O usr/local/bin/proot "{proot_url}" && chmod 755 usr/local/bin/proot
echo "nameserver 1.1.1.1" > etc/resolv.conf
cd root || exit
curl -s https://sshx.io/get | sh
cd ..
./usr/local/bin/proot -0 -w /root -b /dev -b /proc -b /sys -b /etc/resolv.conf -b sshx_bin:/root/.sshx:ro --rootfs=. /bin/sh -c '
apk update &&
apk add curl openssh-client &&
/root/.sshx/bin/sshx serve > /root/ssh.txt
'
"""

    with open(script_path, "w") as f:
        f.write(f"""#!/bin/bash
cd "$(dirname "$0")"
{commands}
""")
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

@tree.command(name="deploy", description="Khởi tạo VPS dùng sshx.io")
@app_commands.describe(os_type="Hệ điều hành muốn dùng: ubuntu hoặc alpine")
async def deploy(interaction: discord.Interaction, os_type: str = "ubuntu"):
    await interaction.response.defer(ephemeral=False)

    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.followup.send("❌ Bạn không thể dùng lệnh này ở đây.")
        return

    user = interaction.user
    user_id = user.id

    now = time.time()
    last_used = deploy_cooldowns.get(user_id, 0)
    if now - last_used < 60:
        remaining = int(60 - (now - last_used))
        await interaction.followup.send(f"⏱️ Vui lòng đợi {remaining}s trước khi dùng lại.")
        return

    if user_id != OWNER_ID and count_user_vps(user_id) >= USER_VPS_LIMIT:
        await interaction.followup.send("🚫 Bạn đã đạt giới hạn VPS.")
        return

    if user_id in user_states:
        await interaction.followup.send("⚠️ Bạn đang deploy VPS khác, vui lòng đợi.")
        return

    os_type = os_type.lower()
    if os_type not in ["ubuntu", "alpine"]:
        await interaction.followup.send("❌ OS không hợp lệ. Dùng `ubuntu` hoặc `alpine`.")
        return

    folder = f"vps/{user_id}_{uuid.uuid4().hex[:6]}"
    user_states[user_id] = True
    register_user_vps(user_id, folder)
    deploy_cooldowns[user_id] = time.time()

    msg = await interaction.followup.send("📦 Đang xử lý VPS...")

    create_script(folder, os_type)
    process = await asyncio.create_subprocess_shell(
        "./start.sh",
        cwd=folder,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    ssh_url = ""
    buffer = ""
    last_update = 0

    async def stream_output():
        nonlocal ssh_url, buffer, last_update
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded = line.decode(errors="ignore").strip()
            buffer += decoded + "\n"

            if "sshx.io" in decoded and not ssh_url:
                ssh_url = decoded
                await interaction.followup.send(f"🔗 SSH: `{ssh_url}`")

            now = time.time()
            if now - last_update > 0.0000002:
                try:
                    await interaction.followup.send(f"🧾 {decoded}")
                    last_update = now
                except:
                    pass

    await asyncio.gather(stream_output(), process.wait())

    if not ssh_url:
        ssh_url = await wait_for_ssh(folder)
        await interaction.followup.send(f"🔗 SSH: `{ssh_url}`")

    await interaction.followup.send("✅ VPS đã sẵn sàng.")
    user_states.pop(user_id, None)

@tree.command(name="deletevps", description="Xóa toàn bộ VPS bạn đã tạo")
async def deletevps(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    deleted = 0

    with open(database_file, "r") as f:
        lines = f.readlines()

    remaining = []
    for line in lines:
        if line.startswith(user_id):
            folder = line.strip().split(",")[1]
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder)
                    deleted += 1
                except:
                    pass
        else:
            remaining.append(line)

    with open(database_file, "w") as f:
        f.writelines(remaining)

    await interaction.followup.send(f"🗑️ Đã xóa `{deleted}` VPS.")

@tree.command(name="statusvps", description="Xem trạng thái CPU, RAM VPS của bạn")
async def statusvps(interaction: discord.Interaction):
    await interaction.response.defer()

    folder = get_latest_user_vps(interaction.user.id)
    if not folder or not os.path.exists(folder):
        await interaction.followup.send("❌ Không có VPS.")
        return

    proot_path = os.path.join(folder, "usr/local/bin/proot")
    if not os.path.exists(proot_path):
        await interaction.followup.send("⚠️ VPS chưa hoàn tất.")
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

    await interaction.followup.send(f"📊 VPS:\n{output}")

async def update_status_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        count = count_active_vps()
        await bot.change_presence(activity=discord.Game(name=f"💖 {count} VPS đang chạy"))
        await asyncio.sleep(60)

@bot.event
async def on_ready():
    await tree.sync()
    bot.loop.create_task(update_status_task())
    print(f"✅ Bot online: {bot.user}")

bot.run(TOKEN)
