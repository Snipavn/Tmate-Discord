import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import os
import uuid
import shutil
import time
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")

def get_user_folder(user_id):
    return f"alpine_{user_id}"

@tree.command(name="deploy", description="Tạo VPS Alpine Linux qua proot")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Lệnh này không được phép ở đây.", ephemeral=True)
        return

    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    rootfs = "alpine-minirootfs.tar.gz"
    alpine_url = "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-3.19.1-x86_64.tar.gz"

    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder, exist_ok=True)

    await interaction.response.send_message("🔧 Đang cài đặt VPS Alpine...")

    try:
        if not os.path.exists(rootfs):
            subprocess.run(["curl", "-Lo", rootfs, alpine_url], check=True)

        result = subprocess.run(["tar", "-tzf", rootfs], capture_output=True)
        if result.returncode != 0:
            raise Exception("❌ File tar.gz bị lỗi hoặc tải sai!")

        subprocess.run(["tar", "-xzf", rootfs, "-C", folder], check=True)

        # hostname
        hostname_script = f"echo 'root@servertipacvn' > {folder}/etc/hostname"
        subprocess.run(hostname_script, shell=True)

        # start.sh
        startup_script = """
echo "http://dl-cdn.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories
apk add tmate openssh sudo neofetch
tmate -S /tmp/tmate.sock new-session -d
tmate -S /tmp/tmate.sock wait tmate-ready
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /tmp/ssh.txt
tail -f /dev/null
"""
        with open(f"{folder}/start.sh", "w") as f:
            f.write(startup_script)
        os.chmod(f"{folder}/start.sh", 0o755)

        session_id = str(uuid.uuid4())[:8]
        with open(f"{folder}/.session_id", "w") as f:
            f.write(session_id)

        # Run VPS
        command = f"proot -r {folder} -b /dev -b /proc -b /sys -w /root /bin/sh /start.sh"
        subprocess.Popen(command, shell=True)

        # Chờ ssh.txt được tạo
        ssh_path = f"{folder}/tmp/ssh.txt"
        for _ in range(30):  # chờ tối đa 30 giây
            if os.path.exists(ssh_path):
                time.sleep(1)
                break
            time.sleep(1)

        if os.path.exists(ssh_path):
            with open(ssh_path) as f:
                ssh_link = f.read().strip()

            try:
                await interaction.user.send(f"🔐 VPS của bạn đã sẵn sàng!\nSSH tmate:\n```{ssh_link}```")
                await interaction.followup.send(f"✅ VPS Alpine đã khởi chạy!\n🆔 ID VPS: `{session_id}`\n📬 SSH đã gửi vào DM.")
            except discord.Forbidden:
                await interaction.followup.send(f"✅ VPS Alpine đã khởi chạy!\n🆔 ID VPS: `{session_id}`\n⚠️ Không thể gửi DM. Hãy bật tin nhắn riêng!")
        else:
            await interaction.followup.send("✅ VPS đã chạy nhưng chưa có SSH. Hãy thử lại sau vài giây.")

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi tạo VPS: {e}")

@tree.command(name="stopvps", description="Dừng VPS đã tạo")
async def stopvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    if os.path.exists(folder):
        shutil.rmtree(folder)
        await interaction.response.send_message("🛑 VPS đã bị xoá.")
    else:
        await interaction.response.send_message("❗ Bạn chưa có VPS đang chạy.")

@tree.command(name="renewvps", description="Gia hạn VPS nếu bị lỗi")
async def renewvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    folder = get_user_folder(user_id)
    start_script = f"{folder}/start.sh"
    if os.path.exists(start_script):
        command = f"proot -r {folder} -b /dev -b /proc -b /sys -w /root /bin/sh /start.sh"
        subprocess.Popen(command, shell=True)
        await interaction.response.send_message("🔁 VPS đã được khởi chạy lại.")
    else:
        await interaction.response.send_message("❗ Không tìm thấy VPS để restart.")

bot.run(TOKEN)
