import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import asyncio
import uuid
import shutil
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

VPS_FOLDER = "vps_data"
IMAGE_LINK = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-amd64-root.tar.xz"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

async def countdown(interaction, seconds):
    message = await interaction.followup.send(f"🕒 Đang khởi tạo VPS ({seconds} giây)...", ephemeral=False)
    for remaining in range(seconds, 0, -1):
        await message.edit(content=f"🕒 Đang khởi tạo VPS ({remaining} giây)...")
        await asyncio.sleep(1)
    await message.edit(content="✅ Đang chạy VPS...")

@tree.command(name="deploy", description="Tạo VPS Ubuntu cloud image")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("❌ Lệnh này chỉ dùng trong kênh được cho phép.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    user_folder = os.path.join(VPS_FOLDER, user_id)
    os.makedirs(user_folder, exist_ok=True)

    await interaction.response.send_message("🔧 Bắt đầu tạo VPS...", ephemeral=False)
    await countdown(interaction, 15)

    vps_id = str(uuid.uuid4())[:8]
    vps_path = os.path.join(user_folder, vps_id)
    os.makedirs(vps_path, exist_ok=True)

    tar_path = os.path.join(vps_path, "ubuntu.tar.xz")
    rootfs_path = os.path.join(vps_path, "ubuntu")

    try:
        await interaction.followup.send("📥 Đang tải Ubuntu cloud image...")
        subprocess.run(["wget", IMAGE_LINK, "-O", tar_path, "--no-check-certificate"], check=True)
        subprocess.run(["mkdir", "-p", rootfs_path], check=True)
        subprocess.run(["tar", "--exclude=dev/*", "-xJf", tar_path, "-C", rootfs_path], check=True)

        with open(os.path.join(rootfs_path, "etc/hostname"), "w") as f:
            f.write("servertipacvn")

        start_sh = """#!/bin/bash
mkdir -p /run/resolvconf && echo "nameserver 1.1.1.1" > /run/resolvconf/resolv.conf
apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 871920D1991BC93C || true
apt-get update
apt install -y gnupg
apt install -y tmate
tmate -F > /root/tmate.log 2>&1 &
sleep 5
grep -m 1 "ssh " /root/tmate.log | grep -v "tmate.io" > /root/tmate_ssh.txt
"""
        with open(os.path.join(rootfs_path, "start.sh"), "w") as f:
            f.write(start_sh)
        os.chmod(os.path.join(rootfs_path, "start.sh"), 0o755)

        subprocess.Popen([
            "proot", "-S", rootfs_path,
            "-b", "/dev", "-b", "/proc", "-b", "/sys",
            "/bin/bash", "-c", "bash /start.sh"
        ])

        await asyncio.sleep(10)

        ssh_path = os.path.join(rootfs_path, "root/tmate_ssh.txt")
        ssh_url = "Không lấy được SSH."

        if os.path.exists(ssh_path):
            with open(ssh_path, "r") as f:
                ssh_url = f.read().strip()

        embed = discord.Embed(
            title="🔗 SSH VPS đã sẵn sàng!",
            description=f"```{ssh_url}```",
            color=discord.Color.green()
        )
        embed.set_footer(text="https://dsc.gg/servertipacvn")

        await interaction.user.send(embed=embed)
        await interaction.followup.send("📨 VPS đã gửi SSH vào tin nhắn riêng!", ephemeral=False)

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi tạo VPS: {e}")

@tree.command(name="deletevps", description="Xoá toàn bộ VPS bạn đã tạo")
async def deletevps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_folder = os.path.join(VPS_FOLDER, user_id)
    if os.path.exists(user_folder):
        shutil.rmtree(user_folder)
        await interaction.response.send_message("🗑️ Đã xoá toàn bộ VPS của bạn.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Bạn chưa có VPS nào để xoá.", ephemeral=True)

@tree.command(name="statusvps", description="Xem CPU và RAM đang sử dụng")
async def statusvps(interaction: discord.Interaction):
    try:
        ram = subprocess.check_output(["free", "-m"]).decode()
        total_ram = int(ram.splitlines()[1].split()[1])
        used_ram = int(ram.splitlines()[1].split()[2])
        ram_percent = int((used_ram / total_ram) * 100)

        embed = discord.Embed(
            title="📊 Trạng thái VPS",
            description=f"**RAM**: {used_ram}/{total_ram} MB ({ram_percent}%)\n**CPU**: Không đo trực tiếp",
            color=discord.Color.blue()
        )
        embed.set_footer(text="https://dsc.gg/servertipacvn")

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Lỗi khi lấy trạng thái VPS: {e}", ephemeral=True)

@bot.event
async def on_ready():
    try:
        synced = await tree.sync()
        print(f"✅ Đã sync {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi khi sync lệnh: {e}")
    print(f"Bot đang chạy với tên: {bot.user}")

bot.run(TOKEN)
