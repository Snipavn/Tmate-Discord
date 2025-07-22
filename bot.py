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

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = app_commands.CommandTree(bot)

@tree.command(name="deploy", description="Deploy VPS Ubuntu Base 20.04")
async def deploy(interaction: discord.Interaction):
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("❌ Lệnh chỉ dùng trong kênh được cho phép!", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    ROOTFS_DIR = f"/root/{user_id}"
    os.makedirs(ROOTFS_DIR, exist_ok=True)

    await interaction.response.send_message("🔧 Đang chuẩn bị VPS...", ephemeral=True)

    arch = os.uname().machine
    arch_alt = "arm64" if arch == "aarch64" else "amd64" if arch == "x86_64" else ""
    if not arch_alt:
        await interaction.followup.send("❌ Kiến trúc không được hỗ trợ.")
        return

    if not os.path.exists(f"{ROOTFS_DIR}/.installed"):
        rootfs_url = f"http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-{arch_alt}.tar.gz"
        tar_path = "/tmp/rootfs.tar.gz"

        await interaction.followup.send("📥 Đang tải Ubuntu Base...")
        os.system(f"wget -q --no-hsts -O {tar_path} {rootfs_url}")
        os.system(f"tar --exclude='dev/*' -xf {tar_path} -C {ROOTFS_DIR}")

        await interaction.followup.send("⚙️ Đang tải proot...")
        proot_url = f"https://raw.githubusercontent.com/dxomg/vpsfreepterovm/main/proot-{arch}"
        proot_path = f"{ROOTFS_DIR}/usr/local/bin/proot"
        os.makedirs(os.path.dirname(proot_path), exist_ok=True)

        while not os.path.exists(proot_path) or os.path.getsize(proot_path) == 0:
            os.system(f"wget -q --no-hsts -O {proot_path} {proot_url}")
            await asyncio.sleep(1)

        os.chmod(proot_path, 0o755)

        with open(f"{ROOTFS_DIR}/etc/resolv.conf", "w") as f:
            f.write("nameserver 1.1.1.1\nnameserver 1.0.0.1")

        os.system(f"echo 'root@servertipacvn' > {ROOTFS_DIR}/etc/hostname")
        open(f"{ROOTFS_DIR}/.installed", "w").close()

        await interaction.followup.send("📦 Đang cài đặt tmate bên trong VPS...")

        install_script = f"""
        #!/bin/bash
        apt update && apt install -y tmate
        tmate -F > /tmp/tmate.log 2>&1 &
        """
        with open(f"{ROOTFS_DIR}/install.sh", "w") as f:
            f.write(install_script)
        os.chmod(f"{ROOTFS_DIR}/install.sh", 0o755)

        subprocess.Popen([
            proot_path,
            "--rootfs", ROOTFS_DIR,
            "-0", "-w", "/root",
            "-b", "/dev", "-b", "/proc", "-b", "/sys", "-b", "/etc/resolv.conf", "--kill-on-exit",
            "/bin/bash", "/install.sh"
        ])

        await asyncio.sleep(5)

    await interaction.followup.send("✅ VPS đã được khởi tạo!")

    try:
        with open(f"{ROOTFS_DIR}/tmp/tmate.log", "r") as log:
            ssh_line = next((line for line in log if "ssh" in line), "Không tìm thấy SSH.")
    except:
        ssh_line = "Không tìm thấy SSH."

    await interaction.user.send(f"🔑 SSH của bạn: `{ssh_line}`")

@tree.command(name="statusvps", description="Xem trạng thái CPU & RAM VPS")
async def statusvps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    ROOTFS_DIR = f"/root/{user_id}"
    proot_bin = f"{ROOTFS_DIR}/usr/local/bin/proot"

    def read_cmd(cmd):
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
            return output
        except:
            return "N/A"

    cpu = read_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8}'")
    ram = read_cmd("free -m | awk '/Mem:/ { print ($3/$2)*100 }'")
    
    embed = discord.Embed(title="📊 VPS Status", color=0x00ff00)
    embed.add_field(name="CPU sử dụng", value=f"{cpu}%", inline=True)
    embed.add_field(name="RAM sử dụng", value=f"{ram}%", inline=True)
    embed.set_footer(text="https://dsc.gg/servertipacvn")

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Start VPS", style=discord.ButtonStyle.green, custom_id="startvps"))
    view.add_item(discord.ui.Button(label="Stop VPS", style=discord.ButtonStyle.danger, custom_id="stopvps"))
    view.add_item(discord.ui.Button(label="Restart VPS", style=discord.ButtonStyle.primary, custom_id="restartvps"))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.type == discord.InteractionType.component:
        return

    custom_id = interaction.data["custom_id"]
    user_id = str(interaction.user.id)
    ROOTFS_DIR = f"/root/{user_id}"
    proot_bin = f"{ROOTFS_DIR}/usr/local/bin/proot"

    if custom_id == "startvps":
        await interaction.response.send_message("🚀 Đang khởi động VPS...", ephemeral=True)
        subprocess.Popen([
            proot_bin, "--rootfs", ROOTFS_DIR,
            "-0", "-w", "/root",
            "-b", "/dev", "-b", "/proc", "-b", "/sys", "-b", "/etc/resolv.conf", "--kill-on-exit",
            "/bin/bash"
        ])
    elif custom_id == "stopvps":
        os.system(f"pkill -f 'proot --rootfs={ROOTFS_DIR}'")
        await interaction.response.send_message("🛑 VPS đã dừng!", ephemeral=True)
    elif custom_id == "restartvps":
        os.system(f"pkill -f 'proot --rootfs={ROOTFS_DIR}'")
        await asyncio.sleep(2)
        subprocess.Popen([
            proot_bin, "--rootfs", ROOTFS_DIR,
            "-0", "-w", "/root",
            "-b", "/dev", "-b", "/proc", "-b", "/sys", "-b", "/etc/resolv.conf", "--kill-on-exit",
            "/bin/bash"
        ])
        await interaction.response.send_message("🔄 VPS đã khởi động lại!", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã sẵn sàng với tên: {bot.user}")

bot.run(TOKEN)
