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

OS_OPTIONS = {
    "alpine": "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/aarch64/alpine-minirootfs-3.19.1-aarch64.tar.gz",
    "ubuntu": "http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-arm64.tar.gz",
    "debian": "http://deb.debian.org/debian/dists/bookworm/main/installer-arm64/current/images/netboot/debian-installer/arm64/root.tar.gz"
}

SCRIPT_CONTENT = {
    "alpine": """#!/bin/sh
apk update
apk add openssh tmate libutempter
# Ensure tmate can connect to its servers by retrying
for i in $(seq 1 10); do
    tmate -S /tmp/tmate.sock new-session -d && break
    echo "Tmate session creation failed, retrying in 2 seconds..."
    sleep 2
done
tmate -S /tmp/tmate.sock wait tmate-ready || { echo "Tmate not ready after timeout."; exit 1; }
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /root/ssh.txt
# Check if ssh.txt is empty, if so, write an an error
[ -s /root/ssh.txt ] || echo "ERROR: SSH string not generated." > /root/ssh.txt
sleep 999999
""",
    "ubuntu": """#!/bin/bash
apt update
apt install -y openssh-client tmate libutempter0 libevent-2.1-7 ncurses-bin
# Ensure tmate can connect to its servers by retrying
for i in $(seq 1 10); do
    tmate -S /tmp/tmate.sock new-session -d && break
    echo "Tmate session creation failed, retrying in 2 seconds..."
    sleep 2
done
tmate -S /tmp/tmate.sock wait tmate-ready || { echo "Tmate not ready after timeout."; exit 1; }
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /root/ssh.txt
# Check if ssh.txt is empty, if so, write an an error
[ -s /root/ssh.txt ] || echo "ERROR: SSH string not generated." > /root/ssh.txt
sleep 999999
""",
    "debian": """#!/bin/bash
apt update
apt install -y openssh-client tmate libutempter0 libevent-2.1-7 ncurses-bin
# Ensure tmate can connect to its servers by retrying
for i in $(seq 1 10); do
    tmate -S /tmp/tmate.sock new-session -d && break
    echo "Tmate session creation failed, retrying in 2 seconds..."
    sleep 2
done
tmate -S /tmp/tmate.sock wait tmate-ready || { echo "Tmate not ready after timeout."; exit 1; }
tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /root/ssh.txt
# Check if ssh.txt is empty, if so, write an an error
[ -s /root/ssh.txt ] || echo "ERROR: SSH string not generated." > /root/ssh.txt
sleep 999999
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
        try:
            # Use asyncio.subprocess for cleaner handling
            process = await asyncio.create_subprocess_shell(
                f"curl -L {OS_OPTIONS[os_name]} -o {tarball}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                print(f"Error downloading rootfs: {stderr.decode()}")
                await user.send(f"❌ Lỗi khi tải rootfs: {stderr.decode()}")
                return
        except Exception as e:
            print(f"Curl command failed: {e}")
            await user.send(f"❌ Lỗi khi tải rootfs: {e}")
            return

    os.makedirs(f"{user_dir}/rootfs", exist_ok=True)
    try:
        # Use asyncio.subprocess for cleaner handling
        process = await asyncio.create_subprocess_shell(
            f"tar -xf {tarball} -C {user_dir}/rootfs --exclude='dev/*'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            print(f"Error extracting rootfs: {stderr.decode()}")
            await user.send(f"❌ Lỗi khi giải nén rootfs: {stderr.decode()}")
            return
    except Exception as e:
        print(f"Tar command failed: {e}")
        await user.send(f"❌ Lỗi khi giải nén rootfs: {e}")
        return

    # Start the proot process
    # It's better to store the process object if you need to manage it later
    proot_process = subprocess.Popen(
        f"proot -0 -r {user_dir}/rootfs -b /dev -b /proc -b /sys -b /etc/resolv.conf -b {user_dir}:/root -w /root /bin/sh start.sh",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    ssh_path = os.path.join(user_dir, "ssh.txt")
    for _ in range(45): # Increased timeout to 45 seconds for tmate to connect
        if os.path.exists(ssh_path):
            with open(ssh_path) as f:
                ssh = f.read().strip()
                if ssh.startswith("ssh"):
                    try:
                        await user.send(f"🔗 SSH của bạn: `{ssh}`\nHost: `root@servertipacvn`")
                    except Exception as e:
                        print(f"Could not send SSH message to user: {e}")
                    return
                elif ssh.startswith("ERROR"):
                    print(f"Tmate script reported an error: {ssh}")
                    try:
                        await user.send("❌ Tmate gặp lỗi khi tạo SSH. Vui lòng thử lại sau.")
                    except Exception as e:
                        print(f"Could not send error message to user: {e}")
                    return # Exit if an explicit error is reported
        await asyncio.sleep(1)

    # If loop finishes without getting SSH
    try:
        await user.send("❌ Không thể lấy SSH. Tmate có thể không khởi động được hoặc có lỗi mạng. Vui lòng thử lại sau.")
    except Exception as e:
        print(f"Could not send final error message to user: {e}")

@bot.tree.command(name="deploy", description="Khởi tạo VPS bằng proot")
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

    # Pass the selected OS to run_proot
    await run_proot(user_dir, interaction.user, os_name.value)

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="🔁 Restart VPS", style=discord.ButtonStyle.primary, custom_id="restart"))
    view.add_item(discord.ui.Button(label="🛑 Stop VPS", style=discord.ButtonStyle.danger, custom_id="stop"))
    view.add_item(discord.ui.Button(label="🚀 Start VPS", style=discord.ButtonStyle.success, custom_id="start"))
    # You might want to update this message to reflect if SSH was successfully retrieved
    await interaction.followup.send("🎉 Yêu cầu khởi tạo VPS đã được xử lý! Kiểm tra tin nhắn riêng để lấy SSH nếu có.", ephemeral=True, view=view)


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type.name == "component":
        user_id = interaction.user.id
        user_dir = f"/root/vps_{user_id}"

        def kill_vps():
            # Iterate through processes and kill those whose command line contains the user's VPS directory
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmd = " ".join(proc.info['cmdline'])
                    if user_dir in cmd:
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass # Ignore errors if process is gone or cannot be accessed

            # Also, attempt to kill any tmate processes directly associated with the user's directory
            # (though proot processes should encompass these)
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'tmate' and user_dir in " ".join(proc.info['cmdline']):
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

        cid = interaction.data['custom_id']
        if cid == "stop":
            await interaction.response.send_message("🛑 Đang dừng VPS...", ephemeral=True)
            kill_vps()
            await interaction.followup.send("🛑 VPS đã dừng.", ephemeral=True)
        elif cid == "restart":
            await interaction.response.send_message("🔁 Đang khởi động lại VPS...", ephemeral=True)
            kill_vps()
            await asyncio.sleep(2) # Give a moment for processes to terminate
            # When restarting, you need to know which OS was originally deployed.
            # This would require storing the chosen OS, e.g., in a dictionary or database.
            # For now, it defaults to Alpine, which might not be desired.
            # Consider adding state management for user's chosen OS.
            await run_proot(user_dir, interaction.user, "alpine") # Defaulting to alpine for restart/start
            await interaction.followup.send("🔁 VPS đã được khởi động lại. Kiểm tra tin nhắn riêng để lấy SSH mới.", ephemeral=True)
        elif cid == "start":
            await interaction.response.send_message("🚀 Đang khởi động VPS...", ephemeral=True)
            # Same issue as restart: need to know the original OS or default.
            await run_proot(user_dir, interaction.user, "alpine") # Defaulting to alpine for restart/start
            await interaction.followup.send("🚀 VPS đã được khởi động. Kiểm tra tin nhắn riêng để lấy SSH.", ephemeral=True)

@bot.tree.command(name="statusvps", description="Xem trạng thái VPS")
async def status(interaction: discord.Interaction):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent

    embed = discord.Embed(
        title="📊 Trạng thái VPS",
        description=f"**CPU Usage:** {cpu}%\n**RAM Usage:** {ram}%",
        color=0x00ff00
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot đã đăng nhập: {bot.user}")

bot.run(TOKEN)

