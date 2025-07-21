import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import os
import uuid
import shutil
import time
from dotenv import load_dotenv
import psutil
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
    print(f"Bot đã đăng nhập thành công dưới tên {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Đã đồng bộ {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi khi sync lệnh: {e}")

@tree.command(name="deploy", description="Tạo VPS Ubuntu trong proot")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("Lệnh này chỉ dùng trong kênh cho phép.", ephemeral=True)

    user_id = str(interaction.user.id)
    user_folder = f"vps_{user_id}"
    if not os.path.exists("vps_data"):
        os.mkdir("vps_data")
    user_path = os.path.join("vps_data", user_folder)
    os.makedirs(user_path, exist_ok=True)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    if key not in user_vps_count:
        user_vps_count[key] = 0
    if user_vps_count[key] >= 2:
        return await interaction.response.send_message("Bạn chỉ được tạo tối đa 2 VPS mỗi ngày!", ephemeral=True)

    await interaction.response.send_message(embed=discord.Embed(
        title="🔧 Đang tải Ubuntu Cloud Image...",
        description="Chờ tí, đang tải rootfs Ubuntu chính chủ...",
        color=0x00ff00
    ).set_footer(text="https://dsc.gg/servertipacvn"))

    image_url = "https://cloud-images.ubuntu.com/releases/current/arm64/ubuntu-22.04-server-cloudimg-arm64-root.tar.xz"
    rootfs_path = os.path.join(user_path, "ubuntu.tar.xz")

    try:
        subprocess.run(["wget", "-O", rootfs_path, image_url], check=True)
    except subprocess.CalledProcessError:
        return await interaction.followup.send("❌ Tải rootfs thất bại.")

    for i in range(5, 0, -1):
        await interaction.followup.send(f"⏳ Đang chuẩn bị VPS... `{i}` giây nữa bắt đầu.", ephemeral=True)
        time.sleep(1)

    start_sh = f"""#!/bin/bash
proot -0 -r ubuntu -b /dev -b /proc -b /sys -w /root /usr/bin/env -i \\
HOME=/root TERM=$TERM PATH=/usr/bin:/usr/sbin:/bin:/sbin:/usr/local/bin:/usr/local/sbin \\
hostname=root@servertipacvn \\
/bin/bash --login -c "apt update && apt install -y tmate && tmate -F"
"""
    with open(os.path.join(user_path, "start.sh"), "w") as f:
        f.write(start_sh)

    subprocess.run(["tar", "-xf", rootfs_path, "-C", user_path, "--exclude=dev"], check=True)

    tmate_log = os.path.join(user_path, "tmate.log")
    os.chmod(os.path.join(user_path, "start.sh"), 0o755)
    proc = subprocess.Popen(["bash", "start.sh"], cwd=user_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Đợi tmate khởi chạy
    await asyncio.sleep(10)

    try:
        out = subprocess.check_output("pgrep tmate", shell=True)
    except:
        return await interaction.followup.send("❌ Tmate không khởi động được.")

    try:
        ssh = subprocess.check_output("tmate display -p '#{tmate_ssh}'", shell=True).decode().strip()
    except:
        ssh = "Không lấy được link SSH."

    user_vps_count[key] += 1

    await interaction.user.send(embed=discord.Embed(
        title="✅ VPS của bạn đã sẵn sàng!",
        description=f"SSH tmate:\n```{ssh}```",
        color=0x00ff00
    ).set_footer(text="https://dsc.gg/servertipacvn"))

@tree.command(name="statusvps", description="Xem tình trạng CPU & RAM VPS")
async def statusvps(interaction: discord.Interaction):
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_usage = ram.used // (1024 * 1024)
    ram_total = ram.total // (1024 * 1024)

    embed = discord.Embed(
        title="📊 Trạng thái VPS",
        description=f"**CPU:** {cpu_percent}%\n**RAM:** {ram_usage}MB / {ram_total}MB",
        color=0x3498db
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed)

# Bot nói chuyện bố láo 😈
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if "bot" in message.content.lower():
        await message.channel.send("Gọi gì th cha nội 😡?")
    elif "ngu" in message.content.lower():
        await message.channel.send("M nói ai ngu? Tao bật đấy 😤")
    await bot.process_commands(message)

bot.run(TOKEN)
