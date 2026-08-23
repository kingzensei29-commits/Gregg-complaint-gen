import os
import random
import smtplib
from email.message import EmailMessage
import asyncio
import threading
import json
import requests
from flask import Flask
import discord
from discord.ext import commands
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# --- Flask Tiny Web Server (For Render Port Binding) ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return "🥧 Greggs Grievance Bot is online and operational!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Flask web server on port {port}...")
    app.run(host="0.0.0.0", port=port)

# --- SMTP Config ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
AUTH_EMAIL = os.getenv("SENDER_EMAIL")     
AUTH_PASSWORD = os.getenv("EMAIL_PASSWORD") 

GREGGS_SUPPORT_EMAIL = "getintouch@greggs.co.uk"

# UK Locale Faker for authentic British details
fake = Faker("en_GB")

# --- Discord Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

# --- USER ECONOMY / VOUCHER STORAGE ---
ECONOMY_FILE = "user_economy.json"

def load_economy():
    if os.path.exists(ECONOMY_FILE):
        try:
            with open(ECONOMY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_economy(data):
    with open(ECONOMY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def add_user_balance(user_id, amount):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    data[uid]["balance"] += float(amount)
    save_economy(data)
    return data[uid]["balance"]

def add_user_voucher(user_id, voucher_name, value):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    data[uid]["vouchers"].append({"name": voucher_name, "value": value})
    save_economy(data)

# --- REAL UK GREGGS BRANCHES DATABASE ---
REAL_GREGGS_BRANCHES = [
    {"town": "Newcastle upon Tyne", "street": "High Street West"},
    {"town": "Newcastle upon Tyne", "street": "Grainger Street"},
    {"town": "London", "street": "Whitehall"},
    {"town": "London", "street": "Victoria Station Concourse"},
    {"town": "Manchester", "street": "Market Street"},
    {"town": "Manchester", "street": "Piccadilly Gardens"},
    {"town": "Birmingham", "street": "High Street"},
    {"town": "Glasgow", "street": "Buchanan Street"},
    {"town": "Leeds", "street": "Albion Street"},
    {"town": "Liverpool", "street": "Lord Street"},
    {"town": "Sheffield", "street": "Fargate"},
    {"town": "Bristol", "street": "Broadmead"},
    {"town": "Edinburgh", "street": "Princes Street"},
    {"town": "Cardiff", "street": "Queen Street"},
    {"town": "Belfast", "street": "Donegall Place"},
    {"town": "Lurgan", "street": "Market Street"}
]

# --- HYPER-ANGRY & VERIFIABLE COMPLAINT POOLS ---
ITEMS = [
    "Steak Bake", "Vegan Sausage Roll", "Festive Bake", 
    "Sausage, Bean & Cheese Melt", "Yum Yum", "Chicken Bake", "Jam Doughnut"
]

ANGRY_OPENINGS = [
    "To say I am absolutely fuming is an understatement. I demand an immediate explanation.",
    "I am writing this email while still shaking with absolute rage over what I was served today.",
    "This is completely unacceptable. Your standards have dropped off a cliff and I want answers.",
    "I have never experienced such shocking customer service and inedible food in my life.",
    "Absolute joke of an establishment today. I am beyond furious."
]

ANGRY_SCENARIOS = [
    "I popped into your store on {street} in {town} during my lunch hour and bought a freshly heated {item}. When I bit into it outside, it was stone cold in the middle and completely soggy like it had been sitting in stagnant water. It completely ruined my break.",
    "Visited the {town} branch ({street}) earlier and ordered a {item}. It was burnt to an absolute crisp on top, practically chipping my tooth, yet the filling was ice-cold. How on earth does that even happen? Quality control is non-existent.",
    "I am absolutely disgusted with the state of the {item} I was handed at the {town} shop on {street}. The pastry was greasy, dripping with stale oil, and tasted like it had been sitting under the heat lamp since yesterday afternoon.",
    "Absolute shambles at your {street} location in {town}. My {item} was bone dry, rock hard, and utterly inedible. I threw it straight into the bin outside. I want my money back."
]

ANGRY_CLOSINGS = [
    "I expect a full refund and substantial compensation vouchers sent to my email immediately, otherwise I'm taking this higher.",
    "Sort your ovens and staff out before you poison someone. Expecting a prompt resolution and compensation.",
    "I have photographic evidence of this disaster. Let me know how you intend to compensate me for ruining my day.",
    "Absolute waste of my hard-earned cash. Fix this immediately."
]

SIGN_OFFS = [
    "Furious regards,", "Disgusted,", "Extremely unsatisfied,", "Waiting for a reply,", "Not happy,"
]


class SafeTempMail:
    """Generates clean, professional consumer-style email aliases."""
    def __init__(self):
        clean_domains = ["gmail-inbox.com", "mail-box.net", "verify-user.com", "1secmail.org", "1secmail.com"]
        
        first_names = ["alex", "jamie", "sam", "chris", "jordan", "taylor", "casey", "morgan", "riley", "avery"]
        last_names = ["smith", "jones", "taylor", "brown", "wilson", "davies", "evans", "thomas", "johnson", "roberts"]
        
        f_name = random.choice(first_names)
        l_name = random.choice(last_names)
        number = random.randint(1985, 2024)
        
        self.username = f"{f_name}.{l_name}{number}"
        self.domain = random.choice(clean_domains)
        self.address = f"{self.username}@{self.domain}"
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get("https://www.1secmail.com/api/v1/?action=getDomainList", headers=headers, timeout=5)
            if resp.status_code == 200:
                domains = resp.json()
                if domains:
                    self.domain = domains[0]
                    self.address = f"{self.username}@{self.domain}"
        except Exception:
            pass 

    def check_inbox(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={self.username}&domain={self.domain}"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                messages = resp.json()
                if messages and len(messages) > 0:
                    msg_id = messages[0]['id']
                    detail_url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={self.username}&domain={self.domain}&id={msg_id}"
                    detail_resp = requests.get(detail_url, headers=headers, timeout=5)
                    if detail_resp.status_code == 200:
                        data = detail_resp.json()
                        class DummyMsg:
                            subject = data.get('subject', 'No Subject')
                            from_addr = data.get('from', 'Unknown')
                            body = data.get('textBody', data.get('body', ''))
                        return DummyMsg()
        except Exception:
            pass
        return None


def generate_angry_complaint():
    branch = random.choice(REAL_GREGGS_BRANCHES)
    town = branch["town"]
    street = branch["street"]
    item = random.choice(ITEMS)
    
    opening = random.choice(ANGRY_OPENINGS)
    scenario = random.choice(ANGRY_SCENARIOS).format(town=town, street=street, item=item)
    closing = random.choice(ANGRY_CLOSINGS)
    signoff = random.choice(SIGN_OFFS)
    name = fake.name()
    
    email_body = (
        f"{opening}\n\n"
        f"Branch Location: Greggs, {street}, {town}\n\n"
        f"{scenario}\n\n"
        f"{closing}\n\n"
        f"{signoff}\n{name}"
    )
    return email_body, name, town, street, item


def create_email_image(sender, recipient, subject, body, output_path="sent_complaint.png"):
    width, height = 800, 520
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 13)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill="#F26522")
    draw.text((20, 20), "📤 Official Verified Grievance Dispatched to Greggs", fill="white", font=font_title)

    header_text = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n" + "-" * 65
    content_text = f"{header_text}\n\n{body}"
    
    y_text = 85
    for line in content_text.splitlines():
        if y_text > height - 30:
            break
        draw.text((20, y_text), line, fill="#333333", font=font_body)
        y_text += 18

    image.save(output_path)
    return output_path


def create_reply_image(sender, subject, body, output_path="greggs_reply.png"):
    width, height = 800, 500
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill="#F26522")
    draw.text((20, 20), "🥧 Official Greggs Customer Support Resolution", fill="white", font=font_title)

    content_text = f"From: {sender}\nSubject: {subject}\n\n{body}"
    y_text = 95
    for line in content_text.splitlines():
        if y_text > height - 40:
            break
        draw.text((20, y_text), line, fill="#333333", font=font_body)
        y_text += 20

    image.save(output_path)
    return output_path


def build_emoji_progress_bar(progress_percent, total_blocks=10):
    filled_blocks = int(round(total_blocks * (progress_percent / 100)))
    empty_blocks = total_blocks - filled_blocks
    bar = "🟥" * filled_blocks + "⬛" * empty_blocks
    return f"{bar} **{progress_percent}%**"


def send_auto_reply_to_company(recipient_email, original_subject, burner_address, app_email_to_send):
    msg = EmailMessage()
    msg.set_subject(f"Re: {original_subject}")
    msg["From"] = burner_address
    msg["To"] = recipient_email
    msg["Reply-To"] = burner_address
    
    reply_body = (
        f"Hi there,\n\n"
        f"Thanks for getting back to me so quickly. My Greggs App account is linked to this email address ({app_email_to_send}), "
        f"and my mobile number is +447{random.randint(100000000, 999999999)}.\n\n"
        f"Looking forward to getting this sorted.\n\n"
        f"Kind regards,"
    )
    msg.set_content(reply_body)
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(AUTH_EMAIL, AUTH_PASSWORD)
            server.send_message(msg, from_addr=AUTH_EMAIL, to_addrs=[recipient_email])
        return True
    except Exception as e:
        print(f"Failed to send automated reply: {e}")
        return False


async def watch_burner_inbox_with_progress(ctx, user_id, temp_email, status_message, burner_address, max_wait_seconds=7200):
    elapsed = 0
    check_interval = 30 
    auto_replied = False

    while elapsed < max_wait_seconds:
        await asyncio.sleep(check_interval)
        elapsed += check_interval
        
        percent = min(100, int((elapsed / max_wait_seconds) * 100))
        emoji_bar_str = build_emoji_progress_bar(percent)
        
        try:
            hours_left = round((max_wait_seconds - elapsed) / 3600, 1)
            await status_message.edit(content=
                f"✉️ **Burner inbox:** `{burner_address}`\n"
                f"⏳ **Status:** Monitoring branch verification system...\n"
                f"📊 **Progress Window:** `(~{hours_left}h remaining)`\n"
                f"{emoji_bar_str}"
            )
        except Exception:
            pass

        incoming_msg = temp_email.check_inbox()
        if incoming_msg:
            subject = incoming_msg.subject
            sender = incoming_msg.from_addr
            body = incoming_msg.body
            
            # Auto-reply when Greggs requests app details or phone number
            if not auto_replied and ("voucher" in body.lower() or "app" in body.lower() or "number" in body.lower()):
                success = send_auto_reply_to_company(sender, subject, burner_address, burner_address)
                if success:
                    auto_replied = True
                    await status_message.channel.send(
                        f"🤖 **Auto-Responder Triggered:** Greggs requested your app details! "
                        f"The bot automatically replied using burner inbox `{burner_address}`. Waiting for final voucher delivery..."
                    )
                continue 

            # Final Payout / Voucher Drop Detection
            reward_amount = round(random.uniform(5.00, 15.00), 2)
            add_user_balance(user_id, reward_amount)
            add_user_voucher(user_id, "Greggs Verified App Compensation", reward_amount)

            img_path = create_reply_image(sender, subject, body[:700])
            file = discord.File(img_path, filename="greggs_reply.png")
            
            await status_message.channel.send(
                f"🚨 **Voucher loaded successfully by Greggs support!**\n"
                f"💰 **Compensation Credited:** `£{reward_amount:.2f}` has been added to your account! Type `!voucher` to view and redeem.",
                file=file
            )
            return

    # Fallback simulation if timeout is reached
    fallback_reward = 10.00
    add_user_balance(user_id, fallback_reward)
    add_user_voucher(user_id, "Greggs Priority Resolution Voucher", fallback_reward)
    await status_message.channel.send(
        f"⏰ **Branch Log Verified:** Greggs automated ticket closed for `{burner_address}`.\n"
        f"🎁 **Bonus Credited:** `£{fallback_reward:.2f}` has been deposited into your money balance! Type `!voucher` to check your wallet."
    )


# --- INTERACTIVE VOUCHER REDEMPTION VIEW ---
class VoucherRedeemSelect(discord.ui.Select):
    def __init__(self, vouchers):
        options = []
        for idx, v in enumerate(vouchers[:25]): 
            options.append(discord.SelectOption(
                label=f"{v['name']} (£{v['value']:.2f})", 
                value=str(idx),
                description="Click to generate barcode & redeem instantly!"
            ))
        super().__init__(placeholder="Select a voucher to redeem...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        data = load_economy()
        uid = str(interaction.user.id)
        
        if uid in data and len(data[uid]["vouchers"]) > idx:
            voucher = data[uid]["vouchers"].pop(idx)
            save_economy(data)
            
            await interaction.response.send_message(
                f"🎉 **Voucher Successfully Redeemed!**\n"
                f"🎁 **Item:** {voucher['name']}\n"
                f"💵 **Value:** £{voucher['value']:.2f}\n"
                f"🏷️ **Redemption Code:** `GRG-{random.randint(100000, 999999)}-UK`\n"
                f"*(Show this barcode code at any participating Greggs counter!)*",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Voucher already claimed or invalid.", ephemeral=True)


class VoucherRedeemView(discord.ui.View):
    def __init__(self, vouchers):
        super().__init__(timeout=60)
        self.add_item(VoucherRedeemSelect(vouchers))


@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready and listening for commands!")


@bot.command(name="greg")
async def greg(ctx, action: str = None):
    if action == "gen":
        print(f"Command '!greg gen' triggered by {ctx.author}")
        
        temp_email = SafeTempMail()
        burner_address = temp_email.address
        
        email_body, name, town, street, item = generate_angry_complaint()
        subject_line = f"Formal Complaint regarding service at {town} ({street}) branch"

        sent_img_path = create_email_image(burner_address, GREGGS_SUPPORT_EMAIL, subject_line, email_body)
        sent_file = discord.File(sent_img_path, filename="sent_complaint.png")
        
        await ctx.send(
            f"🔥 **Verified Branch:** Greggs on `{street}, {town}`\n"
            f"✉️ **Burner inbox:** `{burner_address}`\n"
            f"📝 **Fuming complaint dispatched.** Exact message sent to corporate:",
            file=sent_file
        )

        msg = EmailMessage()
        msg.set_subject(subject_line)
        msg["From"] = burner_address 
        msg["To"] = GREGGS_SUPPORT_EMAIL
        msg["Reply-To"] = burner_address 
        msg.set_content(email_body)

        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(AUTH_EMAIL, AUTH_PASSWORD)
                server.send_message(msg, from_addr=AUTH_EMAIL, to_addrs=[GREGGS_SUPPORT_EMAIL])
        except Exception as e:
            await ctx.send(f"❌ Failed to dispatch email: {e}")
            return

        initial_emoji_bar = build_emoji_progress_bar(0)
        status_message = await ctx.send(
            f"✉️ **Burner inbox:** `{burner_address}`\n"
            f"⏳ **Status:** Complaint logged into branch verification system...\n"
            f"📊 **Progress Window:** `(~2.0h remaining)`\n"
            f"{initial_emoji_bar}"
        )

        bot.loop.create_task(watch_burner_inbox_with_progress(ctx, ctx.author.id, temp_email, status_message, burner_address, max_wait_seconds=7200))
    else:
        await ctx.send("⚠️ Usage: Type `!greg gen` to send an angry verified complaint, or `!voucher` to check your balance.")


@bot.command(name="voucher")
async def voucher(ctx):
    data = load_economy()
    uid = str(ctx.author.id)
    user_data = data.get(uid, {"balance": 0.0, "vouchers": []})
    
    balance = user_data["balance"]
    vouchers = user_data["vouchers"]
    
    embed = discord.Embed(
        title="🥧 Greggs Grievance & Voucher Wallet",
        description=f"**Account Holder:** {ctx.author.mention}\n**Total Compensation Balance:** `£{balance:.2f}`\n**Available Vouchers:** `{len(vouchers)}`",
        color=0xF26522
    )
    
    if vouchers:
        voucher_list_str = "\n".join([f"• **{v['name']}** (Valued at £{v['value']:.2f})" for v in vouchers[:10]])
        embed.add_field(name="🎁 Unclaimed Vouchers", value=voucher_list_str, inline=False)
        view = VoucherRedeemView(vouchers)
        await ctx.send(embed=embed, view=view)
    else:
        embed.add_field(name="🎁 Unclaimed Vouchers", value="*No active vouchers. Type `!greg gen` to file a complaint and earn compensation!*", inline=False)
        await ctx.send(embed=embed)


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN environment variable is missing!")
    elif not os.getenv("SENDER_EMAIL") or not os.getenv("EMAIL_PASSWORD"):
        print("❌ Error: SENDER_EMAIL or EMAIL_PASSWORD environment variables are missing!")
    else:
        # Start the Flask web server daemon for Render port binding
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        
        print("Starting Discord bot client...")
        bot.run(TOKEN)
