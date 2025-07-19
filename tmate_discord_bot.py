import discord
from discord.ext import commands
from discord import app_commands
import asyncio, os, json, random, datetime
import subprocess
from dotenv import load_dotenv


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
# con cak
load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = 882844895902040104
ALLOWED_CHANNEL_ID = 1378918272812060742
UBUNTU_URL = "https://raw.githubusercontent.com/proot-me/proot/master/test/ubuntu-rootfs.tar.gz"
ROOTFS_LOCAL = "ubuntu-rootfs.tar.gz"

DB_PATH = "db.json"

def load_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w") as f:
            json.dump({"credits": {}, "configs": {}, "selected_configs": {}, "expiry_times": {}}, f)
    with open(DB_PATH) as f:
        return json.load(f)

def save_db(data):
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)

def ensure_user(db, user_id):
    uid = str(user_id)
    if uid not in db["credits"]:
        db["credits"][uid] = 0
    if uid not in db["configs"]:
        db["configs"][uid] = []
    if uid not in db["selected_configs"]:
        db["selected_configs"][uid] = None

async def ensure_rootfs():
    if not os.path.exists(ROOTFS_LOCAL):
        subprocess.run(["wget", "-O", ROOTFS_LOCAL, UBUNTU_URL])

def build_proot_command(session_path):
    return (
        f"proot -S {session_path}/ubuntu /usr/bin/env -i HOME=/root "
        f"PATH=/bin:/usr/bin:/sbin:/usr/sbin tmate -S {session_path}/tmate.sock new-session -d && "
        f"tmate -S {session_path}/tmate.sock wait tmate-ready && "
        f"tmate -S {session_path}/tmate.sock display -p '#{{tmate_ssh}}'"
    )

@tree.command(name="deploy", description="Triệu hồi VPS (mất 10 credit/ngày)")
async def deploy(interaction: discord.Interaction):
    await interaction.response.defer()
    db = load_db()
    user_id = str(interaction.user.id)

    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        return await interaction.followup.send("Cút về đúng kênh!", ephemeral=True)

    ensure_user(db, user_id)
    if db["credits"][user_id] < 10:
        return await interaction.followup.send("Mày nghèo quá, không đủ credit!", ephemeral=True)

    config = db["selected_configs"].get(user_id)
    if not config:
        return await interaction.followup.send("Chưa chọn cấu hình! Dùng lệnh /setcauhinh trước.", ephemeral=True)

    db["credits"][user_id] -= 10
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    db["expiry_times"][user_id] = expiry.isoformat()
    save_db(db)

    session_path = f"sessions/{user_id}"
    os.makedirs(f"{session_path}/ubuntu", exist_ok=True)
    await ensure_rootfs()
    subprocess.run(["tar", "-xzf", ROOTFS_LOCAL, "-C", f"{session_path}/ubuntu", "--strip-components=1"])

    command = build_proot_command(session_path)
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=30)
        ssh_link = output.decode().strip()
        await interaction.user.send(f"🔌 SSH VPS của mày nè: `{ssh_link}`\nTự động xoá sau 24h")
        await interaction.followup.send("Đã gửi SSH link vào tin nhắn riêng!", ephemeral=True)
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f"Lỗi khi tạo VPS: {e.output.decode()}", ephemeral=True)

@tree.command(name="stopvps", description="Xoá VPS")
async def stopvps(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    session_path = f"sessions/{user_id}"
    if os.path.exists(session_path):
        subprocess.run(["rm", "-rf", session_path])
        await interaction.response.send_message("Đã xoá VPS cho mày!", ephemeral=True)
    else:
        await interaction.response.send_message("Mày chưa có VPS để xoá!", ephemeral=True)

@tree.command(name="renew", description="Gia hạn VPS (10 credit/ngày)")
async def renew(interaction: discord.Interaction):
    db = load_db()
    user_id = str(interaction.user.id)
    ensure_user(db, user_id)

    if db["credits"][user_id] < 10:
        return await interaction.response.send_message("Không đủ credit!", ephemeral=True)

    db["credits"][user_id] -= 10
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    db["expiry_times"][user_id] = expiry.isoformat()
    save_db(db)
    await interaction.response.send_message("Gia hạn VPS thành công!", ephemeral=True)

@tree.command(name="timevps", description="Xem thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    db = load_db()
    user_id = str(interaction.user.id)
    expiry_str = db["expiry_times"].get(user_id)

    if not expiry_str:
        return await interaction.response.send_message("Mày chưa có VPS!", ephemeral=True)

    expiry = datetime.datetime.fromisoformat(expiry_str)
    remaining = expiry - datetime.datetime.utcnow()
    if remaining.total_seconds() <= 0:
        await interaction.response.send_message("VPS đã hết hạn!", ephemeral=True)
    else:
        await interaction.response.send_message(f"Còn lại: {str(remaining).split('.')[0]}", ephemeral=True)

@tree.command(name="getcredit", description="Nhận credit mỗi 12 tiếng (1 credit)")
async def getcredit(interaction: discord.Interaction):
    db = load_db()
    user_id = str(interaction.user.id)
    ensure_user(db, user_id)

    last = db.get("last_claim", {}).get(user_id)
    now = datetime.datetime.utcnow()
    if last:
        delta = now - datetime.datetime.fromisoformat(last)
        if delta.total_seconds() < 43200:
            return await interaction.response.send_message("Chưa đủ 12 tiếng để xin credit nữa!", ephemeral=True)

    db["credits"][user_id] += 1
    if "last_claim" not in db:
        db["last_claim"] = {}
    db["last_claim"][user_id] = now.isoformat()
    save_db(db)
    await interaction.response.send_message("Cho mày 1 credit nè!", ephemeral=True)

@tree.command(name="givecredit", description="(OWNER) Tặng credit cho thằng ngu nào đó")
@app_commands.describe(user="Thằng muốn nhận", amount="Bao nhiêu credit")
async def givecredit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Cút!", ephemeral=True)
    db = load_db()
    ensure_user(db, user.id)
    db["credits"][str(user.id)] += amount
    save_db(db)
    await interaction.response.send_message(f"Đã tặng {amount} credit cho {user.name}!", ephemeral=True)

@tree.command(name="xoacredit", description="(OWNER) Reset credit về 0")
@app_commands.describe(user="Thằng cần bị nghèo lại")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Mày méo phải owner!", ephemeral=True)
    db = load_db()
    ensure_user(db, user.id)
    db["credits"][str(user.id)] = 0
    save_db(db)
    await interaction.response.send_message(f"Đã reset credit cho {user.name}", ephemeral=True)

@tree.command(name="credit", description="Xem credit mày còn bao nhiêu")
async def credit(interaction: discord.Interaction):
    db = load_db()
    ensure_user(db, interaction.user.id)
    await interaction.response.send_message(f"💰 Mày có {db['credits'][str(interaction.user.id)]} credit!", ephemeral=True)

@tree.command(name="cuoccredit", description="Cược 1 credit, hên thì x10")
async def cuoccredit(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    ensure_user(db, uid)

    if db["credits"][uid] < 1:
        return await interaction.response.send_message("Không đủ credit cược nha mày!", ephemeral=True)

    db["credits"][uid] -= 1
    if random.randint(1, 10) == 1:
        db["credits"][uid] += 10
        save_db(db)
        await interaction.response.send_message("🤑 Hên vãi! Mày nhân 10 credit!", ephemeral=True)
    else:
        save_db(db)
        await interaction.response.send_message("😂 Thua sml, mất mẹ 1 credit rồi!", ephemeral=True)

@tree.command(name="shopping", description="Mua cấu hình VPS")
async def shopping(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    ensure_user(db, uid)

    view = discord.ui.View()
    options = [
        ("2GB RAM, 2 Core - 20c", "2gb_2core", 20),
        ("4GB RAM, 4 Core - 40c", "4gb_4core", 40),
        ("8GB RAM, 8 Core - 80c", "8gb_8core", 80)
    ]
    for label, value, cost in options:
        async def callback(inter, val=value, cost=cost):
            if db["credits"][uid] < cost:
                await inter.response.send_message("Mày không đủ credit!", ephemeral=True)
                return
            if val in db["configs"][uid]:
                await inter.response.send_message("Cấu hình này mày mua rồi!", ephemeral=True)
                return
            db["credits"][uid] -= cost
            db["configs"][uid].append(val)
            save_db(db)
            await inter.response.send_message(f"Đã mua {val}!", ephemeral=True)

        btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
        btn.callback = callback
        view.add_item(btn)

    await interaction.response.send_message("🛍️ Chọn cấu hình muốn mua:", view=view, ephemeral=True)

@tree.command(name="setcauhinh", description="Chọn cấu hình VPS để deploy")
async def setcauhinh(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    ensure_user(db, uid)
    configs = db["configs"][uid]

    if not configs:
        return await interaction.response.send_message("Mày chưa mua cấu hình nào!", ephemeral=True)

    view = discord.ui.View()
    for cfg in configs:
        async def callback(inter, val=cfg):
            db["selected_configs"][uid] = val
            save_db(db)
            await inter.response.send_message(f"Đã chọn {val}!", ephemeral=True)

        btn = discord.ui.Button(label=f"Chọn {cfg}", style=discord.ButtonStyle.success)
        btn.callback = callback
        view.add_item(btn)

    await interaction.response.send_message("🔧 Chọn cấu hình VPS để dùng:", view=view, ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot {bot.user} đã online!")

bot.run(TOKEN)
