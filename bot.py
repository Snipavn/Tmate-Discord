import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import asyncio
import uuid
import shutil
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

VPS_DIR = "vps_data"
os.makedirs(VPS_DIR, exist_ok=True)

@bot.event
async def on_ready():
    print(f"Bot đã sẵn sàng dưới tên: {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi sync: {e}")

@tree.command(name="deploy", description="Tạo VPS Ubuntu cloud image")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong kênh được phép.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    vps_path = os.path.join(VPS_DIR, user_id)

    if os.path.exists(vps_path):
        await interaction.response.send_message("❌ Bạn đã có VPS đang chạy. Hãy xóa bằng lệnh /deletevps trước.", ephemeral=True)
        return

    os.makedirs(vps_path, exist_ok=True)
    await interaction.response.send_message("🚀 Đang tải Ubuntu cloud image và khởi tạo VPS...")

    ubuntu_url = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64-root.tar.xz"
    ubuntu_tar = os.path.join(vps_path, "ubuntu.tar.xz")
    rootfs_path = os.path.join(vps_path, "ubuntu-fs")
    start_sh = os.path.join(vps_path, "start.sh")

    try:
        subprocess.run(["wget", "-O", ubuntu_tar, ubuntu_url], check=True)
        os.makedirs(rootfs_path, exist_ok=True)
        subprocess.run(["proot", "--link2symlink", "-0", "-r", rootfs_path, "--", "true"], check=False)
        subprocess.run(["tar", "-xJf", ubuntu_tar, "-C", rootfs_path, "--exclude=dev"], check=True)

        with open(start_sh, "w") as f:
            f.write("""#!/bin/bash
mkdir -p /run/resolvconf && echo "nameserver 1.1.1.1" > /run/resolvconf/resolv.conf
apt-get update --allow-unauthenticated || true
DEBIAN_FRONTEND=noninteractive apt-get install -y curl gnupg lsb-release
curl -Lo /tmp/tmate.deb https://github.com/tmate-io/tmate/releases/download/2.4.0/tmate_2.4.0-1_amd64.deb
apt-get install -y /tmp/tmate.deb
tmate -F > /root/tmate.log 2>&1 &
sleep 5
grep -m 1 "ssh " /root/tmate.log | grep -v "tmate.io" > /root/tmate_ssh.txt
""")
        os.chmod(start_sh, 0o755)

        subprocess.Popen(["proot", "-0", "-r", rootfs_path, "-b", "/dev", "-b", "/proc", "-w", "/root", "/bin/bash", start_sh])

        await asyncio.sleep(3)
        ssh_url = None
        for _ in range(30):
            ssh_path = os.path.join(rootfs_path, "root", "tmate_ssh.txt")
            if os.path.exists(ssh_path):
                with open(ssh_path, "r") as f:
                    ssh_url = f.read().strip()
                if ssh_url.startswith("ssh"):
                    break
            await asyncio.sleep(1)

        if not ssh_url:
            await interaction.followup.send("❌ Không thể lấy SSH. Tmate chưa khởi động xong.")
            return

        embed = discord.Embed(
            title="✅ VPS đã sẵn sàng!",
            description=f"🔗 SSH: `{ssh_url}`",
            color=discord.Color.green()
        )
        embed.set_footer(text="https://dsc.gg/servertipacvn")
        await interaction.user.send(embed=embed)
        await interaction.followup.send("📩 SSH VPS đã được gửi vào tin nhắn riêng.")
    except Exception as e:
        await interaction.followup.send(f"❌ Đã xảy ra lỗi: `{str(e)}`")

@tree.command(name="statusvps", description="Xem CPU và RAM VPS")
async def statusvps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    rootfs_path = os.path.join(VPS_DIR, user_id, "ubuntu-fs")

    if not os.path.exists(rootfs_path):
        await interaction.response.send_message("❌ Bạn chưa deploy VPS nào.")
        return

    try:
        cpu = subprocess.check_output(["proot", "-r", rootfs_path, "sh", "-c", "top -bn1 | grep '%Cpu'"], text=True)
        ram = subprocess.check_output(["proot", "-r", rootfs_path, "sh", "-c", "free -m"], text=True)

        embed = discord.Embed(
            title="📊 Trạng thái VPS",
            description=f"**CPU:**\n```\n{cpu.strip()}```\n**RAM:**\n```\n{ram.strip()}```",
            color=discord.Color.blue()
        )
        embed.set_footer(text="https://dsc.gg/servertipacvn")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Không thể lấy trạng thái VPS: `{str(e)}`")

@tree.command(name="deletevps", description="Xóa VPS hiện tại")
async def deletevps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    vps_path = os.path.join(VPS_DIR, user_id)

    if not os.path.exists(vps_path):
        await interaction.response.send_message("❌ Bạn không có VPS nào để xóa.")
        return

    try:
        shutil.rmtree(vps_path)
        await interaction.response.send_message("🗑️ VPS của bạn đã được xóa.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Lỗi khi xóa VPS: `{str(e)}`")

bot.run(TOKEN)
