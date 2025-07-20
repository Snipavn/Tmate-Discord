import discord
from discord.ext import commands
from discord import app_commands
import os
import subprocess
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104  # thay ID owner tại đây
ALLOWED_CHANNEL_ID = 1378918272812060742  # thay ID kênh tại đây
ALLOWED_ROLE_ID = 997017581766574234  # thay ID role tại đây

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

users_config = {}
active_sessions = {}

ALPINE_URL = "https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/alpine-minirootfs-latest-x86_64.tar.gz"

def get_user_folder(uid):
    return f"/tmp/vps_{uid}"

async def download_and_extract(alpine_tar, folder):
    await asyncio.create_subprocess_shell(f"curl -L {ALPINE_URL} -o {alpine_tar}",
                                          stdout=asyncio.subprocess.DEVNULL)
    os.makedirs(f"{folder}/alpine", exist_ok=True)
    await asyncio.create_subprocess_shell(f"tar -xzf {alpine_tar} -C {folder}/alpine --strip-components=1",
                                          stdout=asyncio.subprocess.DEVNULL)

async def create_vps(uid):
    folder = get_user_folder(uid)
    alpine_tar = f"{folder}/alpine.tar.gz"
    if not os.path.exists(alpine_tar):
        await download_and_extract(alpine_tar, folder)

    # set hostname
    hostname_file = f"{folder}/alpine/etc/hostname"
    os.makedirs(os.path.dirname(hostname_file), exist_ok=True)
    with open(hostname_file, "w") as f:
        f.write("servertipacvn")

    # start script
    start_sh = f"{folder}/alpine/root/start.sh"
    os.makedirs(os.path.dirname(start_sh), exist_ok=True)
    with open(start_sh, "w") as f:
        f.write("#!/bin/sh\n")
        f.write("apk update && apk add tmate openssh curl bash\n")
        f.write("tmate -S /tmp/tmate.sock new-session -d\n")
        f.write("tmate -S /tmp/tmate.sock wait tmate-ready\n")
        f.write("tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}' > /tmp/ssh_link\n")
        f.write("sleep 3600\n")
    os.chmod(start_sh, 0o755)

    cfg = users_config[uid]
    cpu_nice = int(cfg["cpu"])
    ram_limit = int(cfg["ram"]) * 1024

    proot_cmd = (
        f"proot -0 -r {folder}/alpine -b /dev -b /proc -b /sys -w /root /bin/sh -c "
        f"\"ulimit -v {ram_limit}; nice -n {cpu_nice} /root/start.sh\""
    )

    session = subprocess.Popen(proot_cmd, shell=True)
    active_sessions[uid] = session

    for _ in range(20):
        try:
            with open(f"{folder}/alpine/tmp/ssh_link") as f:
                return f.read().strip()
        except:
            await asyncio.sleep(2)
    return None

def is_allowed(inter):
    if inter.channel.id != ALLOWED_CHANNEL_ID:
        return False
    if inter.user.id == OWNER_ID:
        return True
    for r in inter.user.roles:
        if r.id == ALLOWED_ROLE_ID:
            return True
    return False

@bot.event
async def on_ready():
    await tree.sync()
    print("Bot is ready.")

@tree.command(name="shopping")
@app_commands.describe(ram="Chọn dung lượng RAM: 2, 4, 8, 12, 16 (GB)")
async def shopping(inter: discord.Interaction, ram: app_commands.Range[int, 2, 16]):
    if not is_allowed(inter):
        return await inter.response.send_message("Bạn không có quyền.", ephemeral=True)
    await inter.response.send_message(f"Gói {ram}GB RAM (CPU nice {ram*10}) đã có sẵn để chọn qua /setcauhinh", ephemeral=True)

@tree.command(name="setcauhinh")
@app_commands.describe(ram="Chọn dung lượng RAM đã mua")
async def setcauhinh(inter: discord.Interaction, ram: app_commands.Range[int, 2, 16]):
    if not is_allowed(inter):
        return await inter.response.send_message("Bạn không có quyền.", ephemeral=True)
    users_config[str(inter.user.id)] = {"ram": ram, "cpu": ram * 10}
    await inter.response.send_message(f"Đã cấu hình: {ram}GB RAM, CPU nice {ram*10}", ephemeral=True)

@tree.command(name="deploy")
async def deploy(inter: discord.Interaction):
    if not is_allowed(inter):
        return await inter.response.send_message("Bạn không có quyền.", ephemeral=True)
    uid = str(inter.user.id)
    if uid not in users_config:
        return await inter.response.send_message("Hãy dùng lệnh /setcauhinh trước.", ephemeral=True)
    await inter.response.send_message("Đang khởi tạo VPS...", ephemeral=True)
    ssh = await create_vps(uid)
    if ssh:
        try:
            await inter.user.send(f"🔐 SSH VPS của bạn: `{ssh}`")
        except:
            await inter.followup.send("Không gửi được DM, hãy bật tin nhắn riêng.", ephemeral=True)
    else:
        await inter.followup.send("Không thể lấy liên kết SSH.", ephemeral=True)

@tree.command(name="stopvps")
async def stopvps(inter: discord.Interaction):
    uid = str(inter.user.id)
    sess = active_sessions.get(uid)
    if sess:
        sess.terminate()
        del active_sessions[uid]
        return await inter.response.send_message("Đã dừng VPS của bạn.", ephemeral=True)
    await inter.response.send_message("Bạn chưa có VPS nào đang chạy.", ephemeral=True)

@tree.command(name="renew")
async def renew(inter: discord.Interaction):
    await stopvps(inter)
    await deploy(inter)

bot.run(TOKEN)
