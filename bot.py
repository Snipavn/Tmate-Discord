import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import uuid
from dotenv import load_dotenv
#
load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = 997017581766574230  # Thay bằng ID server
OWNER_ID = 882844895902040104  # Thay bằng ID bạn
ALLOWED_CHANNEL_ID = 1378918272812060742  # Thay bằng ID kênh cho phép lệnh

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

CONFIGS = {
    "1": {"cpu": "20", "ram": "256"},
    "2": {"cpu": "40", "ram": "512"},
    "3": {"cpu": "80", "ram": "1024"},
}

user_configs = {}

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Logged in as {bot.user}")

def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)

@tree.command(name="setcauhinh", description="Chọn cấu hình VPS", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(option="Chọn gói VPS (1/2/3)")
async def setcauhinh(interaction: discord.Interaction, option: str):
    if option not in CONFIGS:
        await interaction.response.send_message("Cấu hình không hợp lệ.", ephemeral=True)
        return
    user_configs[str(interaction.user.id)] = option
    await interaction.response.send_message(f"Đã chọn cấu hình {option}", ephemeral=True)

@tree.command(name="shopping", description="Mua cấu hình VPS", guild=discord.Object(id=GUILD_ID))
async def shopping(interaction: discord.Interaction):
    msg = "**Cấu hình VPS:**\n"
    for k, v in CONFIGS.items():
        msg += f"Gói {k} - CPU: {v['cpu']}%, RAM: {v['ram']}MB\n"
    await interaction.response.send_message(msg, ephemeral=True)

@tree.command(name="deploy", description="Tạo VPS Alpine", guild=discord.Object(id=GUILD_ID))
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message("Lệnh này không được phép ở đây.", ephemeral=True)

    uid = str(interaction.user.id)
    if uid not in user_configs:
        return await interaction.response.send_message("Hãy dùng lệnh /setcauhinh trước.", ephemeral=True)

    config = CONFIGS[user_configs[uid]]
    user_dir = f"/tmp/vps_{uid}"
    os.makedirs(user_dir, exist_ok=True)

    await interaction.response.send_message("Đang tạo VPS, vui lòng chờ...", ephemeral=True)

    # Download Alpine rootfs
    alpine_url = "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-minirootfs-3.20.0-x86_64.tar.gz"
    run(f"wget -qO {user_dir}/alpine.tar.gz {alpine_url}")
    run(f"proot -0 -r {user_dir}/rootfs tar -xzf {user_dir}/alpine.tar.gz --strip-components=1")

    # Set hostname
    with open(f"{user_dir}/rootfs/etc/hostname", "w") as f:
        f.write("servertipacvn")

    # Prepare tmate install script inside Alpine
    with open(f"{user_dir}/rootfs/root/start.sh", "w") as f:
        f.write("""#!/bin/sh
apk update && apk add openssh tmate curl
tmate -S /tmp/tmate.sock new-session -d
tmate -S /tmp/tmate.sock wait tmate-ready
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /tmp/ssh_link
while true; do sleep 60; done
""")

    run(f"chmod +x {user_dir}/rootfs/root/start.sh")

    # Start proot with CPU + RAM limit
    proot_cmd = (
        f"proot -0 -r {user_dir}/rootfs -b /dev -b /proc -b /sys -w /root "
        f"/bin/sh -c \"ulimit -v {int(config['ram']) * 1024}; nice -n {config['cpu']} ./start.sh\""
    )

    # Spawn proot in background
    subprocess.Popen(proot_cmd, shell=True)

    await interaction.followup.send("Đang khởi động tmate, vui lòng chờ SSH...", ephemeral=True)

    # Wait & read SSH
    ssh_link = None
    for _ in range(20):
        try:
            with open(f"{user_dir}/rootfs/tmp/ssh_link") as f:
                ssh_link = f.read().strip()
            break
        except:
            import time; time.sleep(2)

    if ssh_link:
        try:
            await interaction.user.send(f"🔐 SSH VPS của bạn:\n```{ssh_link}```")
        except:
            await interaction.followup.send("Không thể gửi DM. Vui lòng bật tin nhắn riêng.", ephemeral=True)
    else:
        await interaction.followup.send("❌ Không thể lấy SSH. Vui lòng thử lại sau.", ephemeral=True)

@tree.command(name="stopvps", description="Dừng VPS của bạn", guild=discord.Object(id=GUILD_ID))
async def stopvps(interaction: discord.Interaction):
    user_dir = f"/tmp/vps_{interaction.user.id}"
    run(f"rm -rf {user_dir}")
    await interaction.response.send_message("Đã xóa VPS.", ephemeral=True)

@tree.command(name="renew", description="Khởi động lại VPS", guild=discord.Object(id=GUILD_ID))
async def renew(interaction: discord.Interaction):
    await stopvps(interaction)
    await deploy(interaction)

bot.run(TOKEN)
