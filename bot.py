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

load_dotenv()
TOKEN = os.getenv("TOKEN")

OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = app_commands.CommandTree(bot)

OS_OPTIONS = {
    "alpine": "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/aarch64/alpine-minirootfs-3.19.1-aarch64.tar.gz",
    "ubuntu": "http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-arm64.tar.gz",
    "debian": "http://deb.debian.org/debian/dists/bookworm/main/installer-arm64/current/images/netboot/debian-installer/arm64/root.tar.gz"
}

SCRIPT_CONTENT = {
    "alpine": """#!/bin/sh
apk update
apk add openssh tmate libutempter
tmate -S /tmp/tmate.sock new-session -d
sleep 2
tmate -S /tmp/tmate.sock wait tmate-ready
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /root/ssh.txt
tail -f /dev/null
""",
    "ubuntu": """#!/bin/bash
apt update
apt install -y openssh-client tmate libutempter0 libevent-2.1-7 ncurses-bin
tmate -S /tmp/tmate.sock new-session -d
sleep 2
tmate -S /tmp/tmate.sock wait tmate-ready
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /root/ssh.txt
tail -f /dev/null
""",
    "debian": """#!/bin/bash
apt update
apt install -y openssh-client tmate libutempter0 libevent-2.1-7 ncurses-bin
tmate -S /tmp/tmate.sock new-session -d
sleep 2
tmate -S /tmp/tmate.sock wait tmate-ready
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /root/ssh.txt
tail -f /dev/null
"""
}

async def run_proot(user_dir, user, os_name):
    os.makedirs(user_dir, exist_ok=True)
    os.chdir(user_dir)

    script_path = os.path.join(user_dir, "start.sh")
    with open(script_path, "w") as f:
        f.write(SCRIPT_CONTENT[os_name])
    os.chmod(script_path, 0o755)

    tarball = os.path.join(user_dir, "rootfs.tar.gz")
    if not os.path.exists(tarball):
        os.system(f"curl -L {OS_OPTIONS[os_name]} -o {tarball}")

    extract_cmd = f"proot --link2symlink -0 -r {user_dir}/rootfs -b /dev -b /proc -b /sys -b {user_dir}:/root /bin/sh /root/start.sh"
    os.makedirs(f"{user_dir}/rootfs", exist_ok=True)
    subprocess.run(f"tar -xf {tarball} -C {user_dir}/rootfs --exclude='dev/*'", shell=True)

    process = subprocess.Popen(
        f"proot -0 -r {user_dir}/rootfs -b /dev -b /proc -b /sys -b {user_dir}:/root -w /root /bin/sh start.sh",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    ssh_path = os.path.join(user_dir, "ssh.txt")
    for _ in range(30):  # chờ tối đa 30s để lấy SSH
        if os.path.exists(ssh_path):
            with open(ssh_path) as f:
                ssh = f.read().strip()
                if ssh.startswith("ssh"):
                    try:
                        await user.send(f"🔗 SSH của bạn: `{ssh}`\nHost: `root@servertipacvn`")
                    except:
                        pass
                    return
        await asyncio.sleep(1)
    try:
        await user.send("❌ Không thể lấy SSH. Vui lòng thử lại sau.")
    except:
        pass

@tree.command(name="deploy", description="Khởi tạo VPS bằng proot")
@app_commands.describe(os_name="Chọn hệ điều hành để deploy")
@app_commands.choices(os_name=[
    app_commands.Choice(name="🧊 Alpine", value="alpine"),
    app_commands.Choice(name="🐧 Ubuntu", value="ubuntu"),
    app_commands.Choice(name="🎯 Debian", value="debian")
])
async def deploy(interaction: discord.Interaction, os_name: app_commands.Choice[str]):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Lệnh này chỉ được sử dụng trong kênh <#1378918272812060742>", ephemeral=True)
        return

    user_dir = f"/root/vps_{interaction.user.id}"
    await interaction.response.send_message("🛠️ Đang khởi tạo VPS, vui lòng chờ...", ephemeral=True)

    await run_proot(user_dir, interaction.user, os_name.value)

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="🔁 Restart VPS", style=discord.ButtonStyle.primary, custom_id="restart"))
    view.add_item(discord.ui.Button(label="🛑 Stop VPS", style=discord.ButtonStyle.danger, custom_id="stop"))
    view.add_item(discord.ui.Button(label="🚀 Start VPS", style=discord.ButtonStyle.success, custom_id="start"))
    await interaction.followup.send("🎉 VPS của bạn đã được khởi chạy!", ephemeral=True, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type.name == "component":
        user_id = interaction.user.id
        user_dir = f"/root/vps_{user_id}"

        def kill_vps():
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmd = " ".join(proc.info['cmdline'])
                    if user_dir in cmd:
                        proc.kill()
                except:
                    pass

        cid = interaction.data['custom_id']
        if cid == "stop":
            kill_vps()
            await interaction.response.send_message("🛑 VPS đã dừng.", ephemeral=True)
        elif cid == "restart":
            kill_vps()
            await asyncio.sleep(2)
            await run_proot(user_dir, interaction.user, "alpine")
            await interaction.response.send_message("🔁 VPS đã được khởi động lại.", ephemeral=True)
        elif cid == "start":
            await run_proot(user_dir, interaction.user, "alpine")
            await interaction.response.send_message("🚀 VPS đã được khởi động.", ephemeral=True)

@tree.command(name="statusvps", description="Xem trạng thái VPS")
async def status(interaction: discord.Interaction):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent

    embed = discord.Embed(
        title="📊 Trạng thái VPS",
        description=f"**CPU Usage:** {cpu}%\n**RAM Usage:** {ram}%",
        color=0x00ff00
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã đăng nhập: {bot.user}")

bot.run(TOKEN)
