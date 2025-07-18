import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))  # Your Discord ID
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID"))  # The channel ID allowed to use /deploy

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

sessions = {}
user_credits = {}
last_credit_claim = {}
session_durations = {}

CREDIT_COST_PER_DAY = 10

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")

def is_owner(user: discord.User) -> bool:
    return user.id == OWNER_ID

def format_duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h {minutes}m {seconds}s"

@tree.command(name="deploy", description="Tạo VPS tạm thời bằng tmate")
async def deploy(interaction: discord.Interaction):
    user = interaction.user
    if interaction.channel.id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("⛔ Bạn không thể sử dụng lệnh này ở kênh này.", ephemeral=True)
        return

    if user.id in sessions:
        await interaction.response.send_message("⚠️ Bạn đã có một session đang hoạt động. Dùng /stop để xoá session cũ.", ephemeral=True)
        return

    if user_credits.get(user.id, 0) < CREDIT_COST_PER_DAY:
        await interaction.response.send_message("❌ Bạn không đủ 10 credit để tạo VPS. Dùng /getcredit để nhận thêm.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    try:
        process = await asyncio.create_subprocess_exec(
            "tmate", "-F", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        await asyncio.sleep(5)

        proc = await asyncio.create_subprocess_shell(
            "tmate show-messages | grep 'ssh'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        ssh_line = stdout.decode().strip().splitlines()[0]

        sessions[user.id] = {
            "ssh": ssh_line,
            "start_time": datetime.utcnow(),
            "duration": timedelta(days=1),
        }
        user_credits[user.id] -= CREDIT_COST_PER_DAY

        try:
            await user.send(f"🔐 VPS của bạn đã sẵn sàng:\n```{ssh_line}```\nDùng `/timevps` để xem thời gian còn lại.")
            await interaction.followup.send("✅ VPS đã được tạo. Kiểm tra tin nhắn riêng để lấy SSH.", ephemeral=True)
        except:
            await interaction.followup.send("✅ VPS đã tạo, nhưng tôi không thể gửi DM. Vui lòng mở tin nhắn riêng.", ephemeral=True)

        # Schedule DM on expiration
        async def notify_expiration():
            await asyncio.sleep(86400)  # 24h
            if user.id in sessions:
                del sessions[user.id]
                try:
                    await user.send("⏳ VPS của bạn đã hết hạn và đã bị xoá.")
                except:
                    pass

        bot.loop.create_task(notify_expiration())

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi tạo VPS: {str(e)}", ephemeral=True)

@tree.command(name="stop", description="Xoá VPS tạm thời hiện tại của bạn")
async def stop(interaction: discord.Interaction):
    user = interaction.user
    if user.id in sessions:
        del sessions[user.id]
        await interaction.response.send_message("🗑️ VPS của bạn đã được xoá.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Bạn không có VPS nào đang chạy.", ephemeral=True)

@tree.command(name="list", description="Xem các ID người dùng đang có VPS")
async def list_sessions(interaction: discord.Interaction):
    if not sessions:
        await interaction.response.send_message("📭 Không có VPS nào đang hoạt động.", ephemeral=True)
        return

    ids = "
".join(str(uid) for uid in sessions.keys())
    await interaction.response.send_message(f"🧾 Danh sách user ID có VPS:
```
{ids}
```", ephemeral=True)

@tree.command(name="timevps", description="Xem thời gian còn lại của VPS")
async def timevps(interaction: discord.Interaction):
    user_id = interaction.user.id
    session = sessions.get(user_id)
    if not session:
        await interaction.response.send_message("⚠️ Bạn chưa có VPS nào đang hoạt động.", ephemeral=True)
        return

    started = session["start_time"]
    duration = session["duration"]
    elapsed = datetime.utcnow() - started
    remaining = duration - elapsed
    if remaining.total_seconds() <= 0:
        del sessions[user_id]
        await interaction.response.send_message("⏳ VPS đã hết hạn.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⏰ Thời gian còn lại: **{format_duration(remaining.total_seconds())}**", ephemeral=True)

@tree.command(name="getcredit", description="Nhận 1 credit mỗi 12 giờ.")
async def get_credit(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = datetime.utcnow()
    cooldown = timedelta(hours=12)

    last_claim = last_credit_claim.get(user_id)
    if last_claim and now - last_claim < cooldown:
        remaining = cooldown - (now - last_claim)
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes = remainder // 60
        await interaction.response.send_message(
            f"⏳ Bạn cần chờ {hours} giờ {minutes} phút nữa để nhận credit tiếp.",
            ephemeral=True
        )
        return

    user_credits[user_id] = user_credits.get(user_id, 0) + 1
    last_credit_claim[user_id] = now
    await interaction.response.send_message("✅ Bạn đã nhận được 1 credit!", ephemeral=True)

@tree.command(name="givecredit", description="(Chỉ Owner) Cộng credit cho người dùng.")
@app_commands.describe(user="Người nhận", amount="Số credit")
async def give_credit(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ Bạn không có quyền dùng lệnh này.", ephemeral=True)
        return

    user_credits[user.id] = user_credits.get(user.id, 0) + amount
    await interaction.response.send_message(f"✅ Đã cộng {amount} credit cho {user.mention}", ephemeral=True)

@tree.command(name="xoacredit", description="(Chỉ Owner) Xoá toàn bộ credit của người dùng.")
@app_commands.describe(user="Người bị xoá credit")
async def xoacredit(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ Bạn không có quyền dùng lệnh này.", ephemeral=True)
        return

    user_credits[user.id] = 0
    await interaction.response.send_message(f"🗑️ Đã xoá toàn bộ credit của {user.mention}", ephemeral=True)

bot.run(TOKEN)
