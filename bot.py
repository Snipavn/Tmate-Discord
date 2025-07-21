import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import os
import uuid
import psutil
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
    print(f"Bot đã đăng nhập: {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi sync lệnh: {e}")

@tree.command(name="deploy", description="Tạo VPS Debian và gửi SSH tmate về DM")
async def deploy(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Bạn không được phép dùng lệnh này ở đây.", ephemeral=True)
        return

    await interaction.response.send_message("🔧 Đang khởi tạo VPS Debian... Vui lòng chờ...", ephemeral=True)

    session_id = str(uuid.uuid4())[:8]
    workdir = f"vps_{session_id}"
    os.makedirs(workdir, exist_ok=True)
    os.chdir(workdir)

    with open("start.sh", "w") as f:
        f.write("""#!/bin/bash
apt update && apt install -y wget proot tar curl openssh-client tmate
wget -O root.tar.gz https://deb.debian.org/debian/dists/bookworm/main/installer-amd64/current/images/netboot/debian-installer/amd64/root.tar.gz
mkdir -p debian
tar -xf root.tar.gz -C debian
cat > start-debian.sh << 'EOL'
#!/bin/bash
unset LD_PRELOAD
proot -R debian -b /dev -b /proc -b /sys -b /tmp -b /etc/resolv.conf:/etc/resolv.conf -w /root /bin/bash --login
EOL
chmod +x start-debian.sh
cat > debian/root/.bashrc << 'EOL'
apt update
apt install -y curl wget sudo gnupg2 tmate lsb-release
tmate new-session -d
tmate wait tmate-ready
tmate show-messages
tmate display -p '#{tmate_ssh}' > /root/ssh.txt
echo "SSH ready:"
cat /root/ssh.txt
while :; do sleep 60; done
EOL
chmod +x debian/root/.bashrc
./start-debian.sh
        """)

    subprocess.Popen(["bash", "start.sh"])

    embed = discord.Embed(
        title="✅ VPS Debian đang khởi động...",
        description="Sau vài giây, SSH tmate sẽ được gửi về DM của bạn.",
        color=0x00ff00
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="statusvps", description="Xem tình trạng CPU và RAM VPS")
async def statusvps(interaction: discord.Interaction):
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_percent = ram.percent

    embed = discord.Embed(
        title="📊 Trạng thái VPS hiện tại",
        description=f"**CPU:** {cpu_percent}%\n**RAM:** {ram_percent}%",
        color=0x3498db
    )
    embed.set_footer(text="https://dsc.gg/servertipacvn")
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)
