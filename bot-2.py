import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import asyncio
import uuid
import shutil
from dotenv import load_dotenv
import psutil
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742
BASE_DIR = "vps_data"
LIMIT_PER_USER = 2
OS_OPTIONS = {
    "alpine": "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/aarch64/alpine-minirootfs-3.20.0-aarch64.tar.gz",
    "ubuntu": "http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-arm64.tar.gz",
    "debian": "https://ftp.debian.org/debian/dists/bookworm/main/installer-arm64/current/images/netboot/debian-installer/arm64/root.tar.gz"
}

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = app_commands.CommandTree(bot)

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

def get_user_count(user_id):
    count = 0
    if not os.path.exists("database.txt"):
        return 0
    with open("database.txt", "r") as f:
        for line in f:
            if line.startswith(str(user_id)):
                count += 1
    return count

def write_database(user_id, os_name, folder):
    with open("database.txt", "a") as f:
        f.write(f"{user_id},{os_name},{folder},{datetime.utcnow().isoformat()}\n")

async def send_ssh_dm(user, ssh_content):
    embed = discord.Embed(
        title="🎯 SSH VPS của bạn đây!",
        description=f"```{ssh_content}```",
        color=discord.Color.green()
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    try:
        await user.send(embed=embed)
    except:
        pass

async def setup_vps(user_id, os_name):
    uid = str(uuid.uuid4())[:8]
    folder = f"{BASE_DIR}/{user_id}_{uid}_{os_name}"
    os.makedirs(folder, exist_ok=True)
    os.chdir(folder)
    url = OS_OPTIONS[os_name]

    await asyncio.create_subprocess_shell(f"curl -L {url} -o rootfs.tar.gz && proot --mkdir root && tar -xzf rootfs.tar.gz -C root --exclude='dev/*'")
    
    with open("start.sh", "w") as f:
        f.write(f"""#!/bin/bash
cd "$(dirname "$0")"
proot -R root -0 -b /dev -b /proc -b /sys -w /root /usr/bin/env -i HOME=/root TERM=xterm-256color PATH=/bin:/usr/bin:/sbin:/usr/sbin hostname=root@servertipacvn /bin/sh -c "
( (apk update && apk add openssh tmate) || (apt update && apt install -y openssh-server tmate) || (apt-get update && apt-get install -y openssh-server tmate) || (apt-get install -y openssh-server tmate) || (yes | pacman -Syu tmate openssh) );
tmate -F > /root/ssh.txt & sleep 15;
cat /root/ssh.txt;
tail -f /dev/null
"
""")
    os.chmod("start.sh", 0o755)
    process = await asyncio.create_subprocess_shell("./start.sh", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await asyncio.sleep(25)

    ssh_path = f"{folder}/root/root/ssh.txt"
    ssh_content = "Không lấy được SSH!"
    if os.path.exists(ssh_path):
        with open(ssh_path, "r") as f:
            ssh_content = f.read().strip().splitlines()[0] if f.read() else "Không có nội dung SSH"

    write_database(user_id, os_name, folder)
    return ssh_content

@tree.command(name="deploy", description="🚀 Deploy VPS với OS Alpine, Ubuntu hoặc Debian")
@app_commands.describe(os="Chọn hệ điều hành: alpine, ubuntu, debian")
async def deploy(interaction: discord.Interaction, os: str):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("⛔ Chỉ được dùng lệnh trong kênh chỉ định.", ephemeral=True)
        return
    if os not in OS_OPTIONS:
        await interaction.response.send_message("❌ OS không hợp lệ. Chọn: alpine, ubuntu, debian", ephemeral=True)
        return
    if get_user_count(interaction.user.id) >= LIMIT_PER_USER:
        await interaction.response.send_message("❌ Bạn đã đạt giới hạn 2 VPS/ngày!", ephemeral=True)
        return
    await interaction.response.send_message(f"🔧 Đang deploy VPS `{os}`... Vui lòng chờ 30s", ephemeral=True)
    ssh = await setup_vps(interaction.user.id, os)
    await send_ssh_dm(interaction.user, ssh)
    await interaction.followup.send("✅ VPS đã khởi động và SSH đã gửi qua DM!", ephemeral=True)

@tree.command(name="statusvps", description="📊 Xem CPU và RAM VPS bot đang sử dụng")
async def statusvps(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        return
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    embed = discord.Embed(
        title="📈 Trạng thái VPS",
        description=f"**CPU:** {cpu}%\n**RAM:** {ram}%",
        color=discord.Color.blurple()
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed)

async def control_vps(interaction, action):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        return
    user_id = str(interaction.user.id)
    found = False
    if not os.path.exists("database.txt"):
        await interaction.response.send_message("Bạn chưa có VPS nào.", ephemeral=True)
        return
    with open("database.txt", "r") as f:
        for line in f:
            if line.startswith(user_id):
                _, _, folder, _ = line.strip().split(",")
                script = os.path.abspath(f"{folder}/start.sh")
                if action == "stop":
                    subprocess.call(["pkill", "-f", script])
                elif action == "start":
                    subprocess.Popen([script])
                elif action == "restart":
                    subprocess.call(["pkill", "-f", script])
                    await asyncio.sleep(3)
                    subprocess.Popen([script])
                found = True
    if not found:
        await interaction.response.send_message("Không tìm thấy VPS để thao tác.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Đã thực hiện `{action}` VPS của bạn.", ephemeral=True)

@tree.command(name="stopvps", description="🛑 Tắt VPS của bạn")
async def stopvps(interaction: discord.Interaction):
    await control_vps(interaction, "stop")

@tree.command(name="startvps", description="▶️ Bật lại VPS của bạn")
async def startvps(interaction: discord.Interaction):
    await control_vps(interaction, "start")

@tree.command(name="restartvps", description="♻️ Khởi động lại VPS")
async def restartvps(interaction: discord.Interaction):
    await control_vps(interaction, "restart")

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã sẵn sàng: {bot.user.name}")

bot.run(TOKEN)
