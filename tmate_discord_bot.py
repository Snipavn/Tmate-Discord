import discord
from discord.ext import commands
from discord import app_commands
import subprocess, os, json, asyncio, random
from dotenv import load_dotenv
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

load_dotenv()
TOKEN= os.getenv("TOKEN")
OWNER_ID = 882844895902040104  # Thay ID owner
ALLOWED_CHANNEL_ID = 1378918272812060742  # Thay channel cho phép
DB_PATH = "db.json"
ROOTFS_URL = "https://partner-images.canonical.com/core/jammy/current/ubuntu-jammy-core-cloudimg-amd64-root.tar.gz"
ROOTFS_FILE = "ubuntu22.04-rootfs.tar.gz"

# ===== Database =====
def load_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w") as f: json.dump({"users": {}, "sessions": {}, "credits": {}, "configs": {}}, f, indent=4)
    with open(DB_PATH) as f: return json.load(f)

def save_db(data):
    with open(DB_PATH, "w") as f: json.dump(data, f, indent=4)

db = load_db()

# ===== Util =====
def ensure_rootfs():
    if not os.path.exists(ROOTFS_FILE):
        subprocess.run(["wget", "-O", ROOTFS_FILE, ROOTFS_URL])

def get_user_folder(uid):
    folder = f"sessions/{uid}"
    os.makedirs(folder, exist_ok=True)
    return folder

def has_session(uid):
    return str(uid) in db["sessions"]

def check_credit(uid, required):
    return db["credits"].get(str(uid), 0) >= required

def add_credit(uid, amount):
    uid = str(uid)
    db["credits"][uid] = db["credits"].get(uid, 0) + amount
    save_db(db)

# ===== Commands =====
@tree.command(name="deploy", description="Tạo VPS (tốn 10 credit/ngày)")
async def deploy(interaction: discord.Interaction):
    await interaction.response.defer()
    uid = str(interaction.user.id)

    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        return await interaction.followup.send("Cút về channel chính làm đi thg ngu!", ephemeral=True)

    if not db["configs"].get(uid):
        return await interaction.followup.send("Mày chưa set cấu hình. Dùng /setcauhinh trước đã!", ephemeral=True)

    if not check_credit(uid, 10):
        return await interaction.followup.send("Mày nghèo bỏ mẹ, thiếu credit!", ephemeral=True)

    ensure_rootfs()
    folder = get_user_folder(uid)
    os.makedirs(f"{folder}/ubuntu", exist_ok=True)
    subprocess.run(f"tar -xf {ROOTFS_FILE} -C {folder}/ubuntu", shell=True)

    sock_path = f"{folder}/tmate.sock"
    subprocess.Popen(
        f"tmate -S {sock_path} new-session -d && "
        f"tmate -S {sock_path} wait tmate-ready && "
        f"tmate -S {sock_path} display -p '#{{tmate_ssh}}' > {folder}/ssh.txt",
        shell=True
    )
    db["sessions"][uid] = {"folder": folder}
    add_credit(uid, -10)
    save_db(db)

    await asyncio.sleep(5)
    with open(f"{folder}/ssh.txt") as f:
        ssh = f.read().strip()
    await interaction.user.send(f"🖥️ VPS của mày nè: `{ssh}`")
    await interaction.followup.send("Tao gửi link ssh riêng cho mày rồi đó, đọc đi!", ephemeral=True)

@tree.command(name="stopvps", description="Dừng VPS đang chạy")
async def stopvps(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if not has_session(uid):
        return await interaction.response.send_message("Mày có chạy gì đâu mà stop 😒", ephemeral=True)
    folder = db["sessions"][uid]["folder"]
    subprocess.run(f"rm -rf {folder}", shell=True)
    del db["sessions"][uid]
    save_db(db)
    await interaction.response.send_message("Xoá VPS rồi, khỏi lo.", ephemeral=True)

@tree.command(name="renew", description="Gia hạn VPS (10 credit)")
async def renew(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if not has_session(uid):
        return await interaction.response.send_message("Chó ơi mày chưa có VPS mà đòi gia hạn?", ephemeral=True)
    if not check_credit(uid, 10):
        return await interaction.response.send_message("Nghèo thì đừng đú gia hạn 😏", ephemeral=True)
    add_credit(uid, -10)
    save_db(db)
    await interaction.response.send_message("Được rồi, tao gia hạn cho mày đó.", ephemeral=True)

@tree.command(name="credit", description="Xem số credit")
async def credit(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    c = db["credits"].get(uid, 0)
    await interaction.response.send_message(f"💰 Credit của mày: `{c}`", ephemeral=True)

@tree.command(name="getcredit", description="Nhận 1 credit (12h/lần)")
async def getcredit(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    add_credit(uid, 1)
    await interaction.response.send_message("Thôi cho mày 1 credit, biến!", ephemeral=True)

@tree.command(name="givecredit", description="Tặng credit (OWNER)", default_permissions=discord.Permissions(administrator=True))
@app_commands.checks.has_permissions(administrator=True)
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Câm mồm thằng lạ mặt!", ephemeral=True)
    add_credit(user.id, amount)
    await interaction.response.send_message(f"Cho {user.name} {amount} credit rồi!", ephemeral=True)

@tree.command(name="xoacredit", description="Xoá sạch credit (OWNER)")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Mày không phải chủ, xéo!", ephemeral=True)
    db["credits"][str(user.id)] = 0
    save_db(db)
    await interaction.response.send_message(f"Xoá sạch credit của thg {user.name} rồi 😈", ephemeral=True)

@tree.command(name="cuoccredit", description="Cược 1 credit, thắng thì được 10")
async def cuoccredit(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if not check_credit(uid, 1):
        return await interaction.response.send_message("Mày còn méo có nổi 1 credit, đi xin đi thằng nghèo!", ephemeral=True)
    result = random.choice([True, False, False])
    if result:
        add_credit(uid, 10)
        await interaction.response.send_message("🤑 Mày ăn được 10 credit rồi đó, cược tiếp đi!", ephemeral=True)
    else:
        add_credit(uid, -1)
        await interaction.response.send_message("Thua sml mất 1 credit 😢", ephemeral=True)

@tree.command(name="shopping", description="Mua cấu hình VPS")
async def shopping(interaction: discord.Interaction):
    embed = discord.Embed(title="🏪 SHOP VPS", description="Chọn cấu hình mày muốn mua", color=0x00ff00)
    embed.add_field(name="2GB RAM, 2 core", value="`20 credit`", inline=False)
    embed.add_field(name="4GB RAM, 4 core", value="`40 credit`", inline=False)
    embed.add_field(name="8GB RAM, 8 core", value="`80 credit`", inline=False)

    view = discord.ui.View()
    for ram, cpu, cost in [(2,2,20), (4,4,40), (8,8,80)]:
        async def callback(interaction2, r=ram, c=cpu, cost=cost):
            uid = str(interaction.user.id)
            if not check_credit(uid, cost):
                return await interaction2.response.send_message("Không đủ credit, té!", ephemeral=True)
            add_credit(uid, -cost)
            db["configs"][uid] = {"ram": r, "cpu": c}
            save_db(db)
            await interaction2.response.send_message(f"Đã mua cấu hình {r}GB/{c} core!", ephemeral=True)
        btn = discord.ui.Button(label=f"{ram}GB/{cpu}core", style=discord.ButtonStyle.green)
        btn.callback = callback
        view.add_item(btn)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@tree.command(name="setcauhinh", description="Chọn cấu hình đã mua")
async def setcauhinh(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    config = db["configs"].get(uid)
    if not config:
        return await interaction.response.send_message("Mày chưa mua cái gì cả 🤡", ephemeral=True)
    await interaction.response.send_message(f"Đã set cấu hình {config['ram']}GB/{config['cpu']} core", ephemeral=True)

@tree.command(name="timevps", description="Xem thời gian còn lại VPS")
async def timevps(interaction: discord.Interaction):
    if not has_session(str(interaction.user.id)):
        return await interaction.response.send_message("Mày có VPS đâu mà đòi xem?", ephemeral=True)
    await interaction.response.send_message("Mày còn ~24h tính từ lúc deploy. Đừng hỏi nữa!", ephemeral=True)

# ===== On Ready =====
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot đã online dưới tên: {bot.user}")

# ===== Start =====
bot.run(TOKEN)
