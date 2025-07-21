import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import asyncio
import uuid
import shutil
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_vps_count = {}

@bot.event
async def on_ready():
    print(f"Bot đã sẵn sàng dưới tên {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi khi sync lệnh: {e}")

@tree.command(name="deploy", description="Tạo VPS Ubuntu bằng proot (giới hạn 2 VPS/ngày)")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("⛔ Không được phép dùng lệnh này ở đây.", ephemeral=True)

    user_id = interaction.user.id
    today = datetime.utcnow().date()
    if user_id not in user_vps_count or user_vps_count[user_id]["date"] != today:
        user_vps_count[user_id] = {"count": 0, "date": today}

    if user_vps_count[user_id]["count"] >= 2:
        return await interaction.response.send_message("❌ Bạn đã tạo tối đa 2 VPS hôm nay.", ephemeral=True)

    user_vps_count[user_id]["count"] += 1
    folder_name = f"vps_{user_id}_{uuid.uuid4().hex[:6]}"
    os.makedirs(folder_name, exist_ok=True)

    await interaction.response.send_message(
        f"🔁 Đang tải Ubuntu cloud image về và chuẩn bị VPS...", ephemeral=False
    )

    ubuntu_url = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64-root.tar.xz"
    rootfs_path = os.path.join(folder_name, "rootfs.tar.xz")

    try:
        subprocess.run(
            ["wget", "-O", rootfs_path, ubuntu_url],
            check=True
        )
    except subprocess.CalledProcessError:
        return await interaction.followup.send("❌ Tải rootfs thất bại.", ephemeral=False)

    start_sh = f"""#!/bin/bash
cd "$(dirname "$0")"
proot -0 -r . -b /dev -b /proc -b /sys -w /root /usr/bin/env -i HOME=/root PATH=/bin:/usr/bin:/sbin:/usr/sbin TERM=xterm bash -c "
apt update &&
apt install -y openssh-server tmate &&
echo 'root:toor' | chpasswd &&
hostnamectl set-hostname root@servertipacvn &&
tmate -F" > ssh.txt 2>&1 &
"""
    with open(os.path.join(folder_name, "start.sh"), "w") as f:
        f.write(start_sh)
    os.chmod(os.path.join(folder_name, "start.sh"), 0o755)

    subprocess.run(
        ["tar", "-xf", rootfs_path, "-C", folder_name],
        check=True
    )

    await interaction.followup.send(
        embed=discord.Embed(
            title="✅ VPS Đã sẵn sàng!",
            description="Tạo VPS thành công, bắt đầu đếm ngược khởi động...",
            color=discord.Color.green(),
        ).set_footer(text="https://dsc.gg/servertipacvn"),
        ephemeral=False
    )

    for i in range(10, 0, -1):
        await interaction.followup.send(f"🕒 Remaining: {i} giây...", ephemeral=False)
        await asyncio.sleep(1)

    subprocess.Popen(["bash", "start.sh"], cwd=folder_name)

    await asyncio.sleep(8)
    ssh_path = os.path.join(folder_name, "ssh.txt")
    ssh_msg = "Không thể đọc SSH"
    if os.path.exists(ssh_path):
        with open(ssh_path, "r") as f:
            ssh_msg = f.read().strip()

    try:
        await interaction.user.send(f"🔐 SSH của bạn:\n```{ssh_msg}```")
    except:
        await interaction.followup.send("⚠️ Không thể gửi tin nhắn riêng. Mở DM để nhận SSH.", ephemeral=False)

@tree.command(name="statusvps", description="Xem tình trạng CPU & RAM VPS")
async def statusvps(interaction: discord.Interaction):
    try:
        cpu = subprocess.check_output("top -bn1 | grep 'Cpu(s)'", shell=True).decode()
        ram = subprocess.check_output("free -m", shell=True).decode()

        cpu_percent = cpu.split("%")[0].split()[-1]
        ram_line = ram.split("\n")[1].split()
        ram_used = ram_line[2]
        ram_total = ram_line[1]

        embed = discord.Embed(
            title="📊 Trạng thái VPS",
            description=f"**<:cpu:1147496245766668338>CPU sử dụng:** {cpu_percent}%\n**<:RAM:1147501868264722442>RAM sử dụng:** {ram_used}/{ram_total} MB",
            color=discord.Color.blue()
        )
        embed.set_footer(text="https://dsc.gg/servertipacvn")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Lỗi khi lấy trạng thái VPS: {e}", ephemeral=True)

@tree.command(name="chat", description="Nói chuyện bố láo")
@app_commands.describe(message="Nội dung chat")
async def chat(interaction: discord.Interaction, message: str):
    response = f"Ơ kìa {interaction.user.name}, mày rảnh quá ha 😏 — tao nghe đây: \"{message}\""
    await interaction.response.send_message(response, ephemeral=False)

bot.run(TOKEN)
