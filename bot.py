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

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Bot đã đăng nhập với tên: {bot.user}')

def get_arch():
    arch = os.uname().machine
    if arch == "x86_64":
        return "amd64", "x86_64"
    elif arch == "aarch64":
        return "arm64", "aarch64"
    else:
        return None, None

async def install_rootfs(user_id: int, os_choice: str):
    arch_alt, arch = get_arch()
    user_dir = f"/root/vps_{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    os.chdir(user_dir)

    if os.path.exists(".installed"):
        return user_dir

    if os_choice == "debian":
        url = f"https://github.com/termux/proot-distro/releases/download/v3.10.0/debian-{arch}-pd-v3.10.0.tar.xz"
        subprocess.run(["wget", "-O", "rootfs.tar.xz", url])
        subprocess.run(["apt", "download", "xz-utils"])
        deb_file = next((f for f in os.listdir() if f.endswith(".deb")), None)
        if deb_file:
            subprocess.run(["dpkg", "-x", deb_file, "/root/.local/"])
            os.remove(deb_file)
        subprocess.run(["tar", "-xJf", "rootfs.tar.xz", "-C", user_dir, "--exclude=dev/*"])
    elif os_choice == "ubuntu":
        url = f"http://cdimage.ubuntu.com/ubuntu-base/releases/20.04/release/ubuntu-base-20.04.4-base-{arch_alt}.tar.gz"
        subprocess.run(["wget", "-O", "rootfs.tar.gz", url])
        subprocess.run(["tar", "-xf", "rootfs.tar.gz", "-C", user_dir, "--exclude=dev/*"])
    elif os_choice == "alpine":
        url = f"https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/{arch}/alpine-minirootfs-3.18.3-{arch}.tar.gz"
        subprocess.run(["wget", "-O", "rootfs.tar.gz", url])
        subprocess.run(["tar", "-xf", "rootfs.tar.gz", "-C", user_dir, "--exclude=dev/*"])
    else:
        raise ValueError("Invalid OS")

    proot_url = f"https://raw.githubusercontent.com/dxomg/vpsfreepterovm/main/proot-{arch}"
    proot_path = os.path.join(user_dir, "usr/local/bin/proot")
    os.makedirs(os.path.dirname(proot_path), exist_ok=True)

    while True:
        subprocess.run(["wget", "-O", proot_path, proot_url])
        if os.path.exists(proot_path) and os.path.getsize(proot_path) > 0:
            os.chmod(proot_path, 0o755)
            break
        await asyncio.sleep(1)

    os.makedirs(f"{user_dir}/etc", exist_ok=True)
    with open(f"{user_dir}/etc/resolv.conf", "w") as f:
        f.write("nameserver 1.1.1.1\nnameserver 1.0.0.1")

    with open(".installed", "w") as f:
        f.write("ok")

    return user_dir

async def run_proot(user_dir: str, user: discord.User):
    start_cmd = f"""{user_dir}/usr/local/bin/proot \
--rootfs={user_dir} -0 -w /root \
-b /dev -b /sys -b /proc -b /etc/resolv.conf \
--kill-on-exit /bin/sh -c "apk update && apk add openssh tmate || apt update && apt install -y openssh-client tmate; \
tmate -S /tmp/tmate.sock new-session -d && \
tmate -S /tmp/tmate.sock wait tmate-ready && \
tmate -S /tmp/tmate.sock display -p '#{{tmate_ssh}}' > ssh.txt"
"""
    script_file = f"{user_dir}/start_vps.sh"
    with open(script_file, "w") as f:
        f.write(start_cmd)
    os.chmod(script_file, 0o755)

    proc = await asyncio.create_subprocess_shell(f"bash {script_file}", cwd=user_dir)
    await proc.wait()

    ssh_path = os.path.join(user_dir, "ssh.txt")
    if os.path.exists(ssh_path):
        with open(ssh_path) as f:
            ssh = f.read().strip()
        await user.send(f"🔑 SSH VPS của bạn:\n```{ssh}```")
    else:
        await user.send("❌ Không thể lấy SSH VPS.")

@bot.tree.command(name="deploy", description="Khởi tạo VPS miễn phí")
@app_commands.describe(os="Chọn hệ điều hành VPS")
@app_commands.choices(os=[
    app_commands.Choice(name="Ubuntu", value="ubuntu"),
    app_commands.Choice(name="Debian", value="debian"),
    app_commands.Choice(name="Alpine", value="alpine"),
])
async def deploy(interaction: discord.Interaction, os: app_commands.Choice[str]):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("❌ Lệnh này không dùng ở đây.", ephemeral=True)
        return
    await interaction.response.send_message("🚀 Đang khởi tạo VPS...")
    user_id = interaction.user.id
    user_dir = await install_rootfs(user_id, os.value)
    await run_proot(user_dir, interaction.user)

@bot.tree.command(name="statusvps", description="Xem tình trạng VPS")
async def statusvps(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_dir = f"/root/vps_{user_id}"
    vps_running = "start_vps.sh" in os.listdir(user_dir)

    embed = discord.Embed(title="📊 Trạng thái VPS", color=0x00ff00)
    embed.add_field(name="CPU Usage", value=f"{psutil.cpu_percent()}%", inline=True)
    embed.add_field(name="RAM Usage", value=f"{psutil.virtual_memory().percent}%", inline=True)
    embed.set_footer(text="https://dsc.gg/servertipacvn")

    view = discord.ui.View()
    for name in ["start", "stop", "restart"]:
        view.add_item(discord.ui.Button(label=f"{name.capitalize()} VPS", style=discord.ButtonStyle.primary, custom_id=name))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type.name == "component":
        user_id = interaction.user.id
        user_dir = f"/root/vps_{user_id}"
        if interaction.data["custom_id"] == "start":
            await run_proot(user_dir, interaction.user)
            await interaction.response.send_message("✅ VPS đã được khởi động lại.", ephemeral=True)
        elif interaction.data["custom_id"] == "stop":
            subprocess.run(["pkill", "-f", f"vps_{user_id}"])
            await interaction.response.send_message("🛑 VPS đã được dừng.", ephemeral=True)
        elif interaction.data["custom_id"] == "restart":
            subprocess.run(["pkill", "-f", f"vps_{user_id}"])
            await run_proot(user_dir, interaction.user)
            await interaction.response.send_message("🔁 VPS đã khởi động lại.", ephemeral=True)

bot.run(TOKEN)
