import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import asyncio
import uuid
import psutil
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742
USER_VPS_LIMIT = 2

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = app_commands.CommandTree(bot)

# Tạo thư mục nếu chưa có
os.makedirs("vps", exist_ok=True)
database_file = "database.txt"
if not os.path.exists(database_file):
    open(database_file, "w").close()

def count_user_vps(user_id):
    with open(database_file, "r") as f:
        return sum(1 for line in f if line.startswith(str(user_id)))

def register_user_vps(user_id, folder):
    with open(database_file, "a") as f:
        f.write(f"{user_id},{folder}\n")

async def run_script(script_path, folder):
    proc = await asyncio.create_subprocess_exec("bash", script_path, cwd=folder)
    await proc.wait()

async def wait_for_ssh(folder):
    ssh_path = os.path.join(folder, "root", "ssh.txt")
    for _ in range(60):
        if os.path.exists(ssh_path):
            with open(ssh_path) as f:
                ssh = f.read().strip()
            if "ssh" in ssh:
                return ssh
        await asyncio.sleep(1)
    return None

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
apt install sudo neofetch systemctl tmate -y &&
tmate -F > /root/ssh.txt &
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
apk add bash coreutils tmate neofetch &&
tmate -F > /root/ssh.txt &
"; exec sh'
"""

    with open(script_path, "w") as f:
        f.write(f"#!/bin/bash\ncd {folder}\n" + commands)
    os.chmod(script_path, 0o755)
    return script_path

@tree.command(name="deploy", description="Deploy VPS với OS tùy chọn")
@app_commands.describe(os_type="Chọn hệ điều hành để deploy")
@app_commands.choices(os_type=[
    app_commands.Choice(name="Ubuntu", value="ubuntu"),
    app_commands.Choice(name="Alpine", value="alpine")
])
async def deploy(interaction: discord.Interaction, os_type: app_commands.Choice[str]):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Bạn không thể dùng lệnh này ở đây.", ephemeral=True)
        return

    if count_user_vps(interaction.user.id) >= USER_VPS_LIMIT:
        await interaction.response.send_message("Bạn đã đạt giới hạn VPS hôm nay.", ephemeral=True)
        return

    await interaction.response.send_message(f"Đang khởi tạo VPS {os_type.name}...", ephemeral=True)

    folder = f"vps/{interaction.user.id}_{uuid.uuid4().hex[:6]}"
    script_path = create_script(folder, os_type.value)
    register_user_vps(interaction.user.id, folder)

    proc = await asyncio.create_subprocess_shell(f"bash {script_path}", cwd=folder)
    await asyncio.sleep(30)

    ssh = await wait_for_ssh(os.path.join(folder))
    if ssh:
        embed = discord.Embed(
            title="✅ VPS của bạn đã sẵn sàng!",
            description=f"```{ssh}```",
            color=0x2ecc71
        )
    else:
        embed = discord.Embed(
            title="❌ Lỗi khi tạo VPS",
            description="Không thể lấy SSH tmate. Vui lòng thử lại.",
            color=0xe74c3c
        )
    embed.set_footer(text="https://dsc.gg/servertipacvn")

    try:
        await interaction.user.send(embed=embed)
        await interaction.followup.send("SSH VPS đã được gửi vào DM của bạn ✅", ephemeral=True)
    except:
        await interaction.followup.send("Không thể gửi DM. Vui lòng mở tin nhắn trực tiếp.", ephemeral=True)

@tree.command(name="statusvps", description="Xem tình trạng CPU & RAM VPS")
async def statusvps(interaction: discord.Interaction):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_used = round(ram.used / 1024 / 1024)
    ram_total = round(ram.total / 1024 / 1024)

    embed = discord.Embed(
        title="📊 Trạng thái VPS",
        description=f"**CPU:** {cpu}%\n**RAM:** {ram_used}MB / {ram_total}MB",
        color=0x3498db
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="stopvps", description="Dừng VPS")
async def stopvps(interaction: discord.Interaction):
    os.system("pkill proot")
    await interaction.response.send_message("🛑 VPS đã được dừng.", ephemeral=True)

@tree.command(name="restartvps", description="Khởi động lại VPS")
async def restartvps(interaction: discord.Interaction):
    await interaction.response.send_message("🔁 VPS đang được khởi động lại...", ephemeral=True)
    os.system("pkill proot")
    await asyncio.sleep(3)
    await interaction.followup.send("✅ VPS đã khởi động lại thành công.", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã sẵn sàng. Đăng nhập với {bot.user}")

bot.run(TOKEN)
