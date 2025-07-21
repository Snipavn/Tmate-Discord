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

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Sync error: {e}")

@tree.command(name="deploy", description="Tạo VPS Ubuntu")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("⛔ Không được phép ở kênh này!", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    folder = f"vps_data/{user_id}_{uuid.uuid4().hex[:6]}"
    os.makedirs(folder, exist_ok=True)

    await interaction.response.send_message(f"📦 Đang tải Ubuntu Cloud Image...")

    ubuntu_url = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64-root.tar.xz"
    ubuntu_tar = f"{folder}/ubuntu.tar.xz"

    try:
        subprocess.run(f"curl -L '{ubuntu_url}' -o '{ubuntu_tar}'", shell=True, check=True)
        subprocess.run(f"tar -xf '{ubuntu_tar}' -C '{folder}'", shell=True, check=True)
    except subprocess.CalledProcessError:
        await interaction.followup.send("❌ Lỗi khi tải hoặc giải nén Ubuntu!", ephemeral=True)
        return

    await interaction.followup.send("🛠️ Đang khởi động VPS, vui lòng chờ 10–20s...")

    start_sh = """#!/bin/bash
echo "deb http://archive.ubuntu.com/ubuntu jammy universe" >> /etc/apt/sources.list
apt update -y
apt install -y tmate curl unzip neofetch openssh-client
tmate new-session -d
tmate wait tmate-ready
tmate display -p "SSH: %{tmate_ssh}" > /root/tmate_link.txt
"""
    with open(f"{folder}/start.sh", "w") as f:
        f.write(start_sh)
    os.chmod(f"{folder}/start.sh", 0o755)

    # Đổi hostname
    with open(f"{folder}/etc/hostname", "w") as f:
        f.write("root@servertipacvn")

    # Chạy start.sh trong nền
    subprocess.Popen(f"proot -R {folder} -0 /start.sh", shell=True)

    # Đợi tmate_link.txt xuất hiện
    ssh_path = f"{folder}/root/tmate_link.txt"
    for _ in range(30):
        if os.path.exists(ssh_path):
            break
        await asyncio.sleep(1)

    if os.path.exists(ssh_path):
        with open(ssh_path) as f:
            ssh_link = f.read().strip()
        try:
            await interaction.user.send(f"✅ VPS của bạn đã sẵn sàng:\n```{ssh_link}```")
        except:
            await interaction.followup.send("❌ Không thể gửi DM, hãy bật tin nhắn riêng!", ephemeral=True)
    else:
        await interaction.followup.send("❌ Lỗi khi lấy SSH, VPS có thể không khởi động được.", ephemeral=True)

@tree.command(name="deletevps", description="Xoá toàn bộ VPS đã tạo")
async def deletevps(interaction: discord.Interaction):
    shutil.rmtree("vps_data", ignore_errors=True)
    await interaction.response.send_message("🗑️ Đã xoá toàn bộ VPS!", ephemeral=True)

@tree.command(name="statusvps", description="Xem CPU và RAM VPS")
async def statusvps(interaction: discord.Interaction):
    try:
        cpu = subprocess.check_output("top -bn1 | grep 'Cpu(s)'", shell=True).decode()
        mem = subprocess.check_output("free -m", shell=True).decode()

        embed = discord.Embed(title="📊 VPS Status", color=0x00ff99)
        embed.add_field(name="🧠 RAM", value=f"```{mem}```", inline=False)
        embed.add_field(name="💻 CPU", value=f"```{cpu}```", inline=False)
        embed.set_footer(text="https://dsc.gg/servertipacvn")

        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ VPS chưa chạy hoặc không thể truy cập.", ephemeral=True)

bot.run(TOKEN)
