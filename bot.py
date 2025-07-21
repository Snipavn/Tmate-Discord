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
# Config cố định không dùng .env
TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

MAX_VPS_PER_DAY = 2
VPS_FOLDER = "vps_data"
IMAGE_LINK = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64-root.tar.xz"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_vps_count = {}

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
    now = datetime.utcnow().date()
    user_folder = os.path.join(VPS_FOLDER, user_id)
    os.makedirs(user_folder, exist_ok=True)

    counter_file = os.path.join(user_folder, "counter.txt")
    if os.path.exists(counter_file):
        with open(counter_file, "r") as f:
            date_str, count_str = f.read().split(",")
            if date_str == str(now) and int(count_str) >= MAX_VPS_PER_DAY:
                await interaction.response.send_message("❌ Bạn đã tạo tối đa 2 VPS hôm nay.", ephemeral=True)
                return

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
        subprocess.run(["tar", "-xJf", tar_path, "-C", rootfs_path], check=True)

        # Tạo hostname
        with open(os.path.join(rootfs_path, "etc/hostname"), "w") as f:
            f.write("servertipacvn")

        # Ghi đè DNS bên trong proot
        resolv = os.path.join(rootfs_path, "etc/resolv.conf")
        with open(resolv, "w") as f:
            f.write("nameserver 1.1.1.1\n")

        # Script khởi chạy bên trong VPS
        start_sh = f"""#!/bin/bash
apt update
apt install -y tmate
tmate -F > /root/tmate.log 2>&1 &
sleep 5
cat /root/tmate.log | grep 'ssh ' > /root/tmate_ssh.txt
"""
        with open(os.path.join(rootfs_path, "start.sh"), "w") as f:
            f.write(start_sh)

        os.chmod(os.path.join(rootfs_path, "start.sh"), 0o755)

        # Khởi chạy VPS
        subprocess.Popen([
            "proot", "-S", rootfs_path,
            "-b", "/dev", "-b", "/proc", "-b", "/sys",
            "/bin/bash", "-c", "bash /start.sh"
        ])

        await asyncio.sleep(10)

        # Lấy SSH URL
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

        # Cập nhật đếm VPS theo ngày
        if os.path.exists(counter_file):
            if date_str == str(now):
                new_count = int(count_str) + 1
            else:
                new_count = 1
        else:
            new_count = 1
        with open(counter_file, "w") as f:
            f.write(f"{now},{new_count}")

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi tạo VPS: {e}")

@tree.command(name="statusvps", description="Xem CPU và RAM đang sử dụng")
async def statusvps(interaction: discord.Interaction):
    try:
        cpu = subprocess.check_output(["grep", "cpu ", "/proc/stat"]).decode()
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
