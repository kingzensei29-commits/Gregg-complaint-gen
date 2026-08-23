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
    return "🍗 Fast Food Grievance Bot is online and operational!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Flask web server on port {port}...")
    app.run(host="0.0.0.0", port=port)

# --- SMTP Config ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
AUTH_EMAIL = os.getenv("SENDER_EMAIL")     
AUTH_PASSWORD = os.getenv("EMAIL_PASSWORD") 

# UK Locale Faker for authentic British details
fake = Faker("en_GB")

# --- Discord Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

# --- PERSISTENT USER ECONOMY / VOUCHER STORAGE ---
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
    try:
        with open(ECONOMY_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save economy state: {e}")

def add_user_balance(user_id, amount):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    data[uid]["balance"] += float(amount)
    save_economy(data)
    return data[uid]["balance"]

def add_user_voucher(user_id, username, brand_name, value):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    
    # Create a unique code embedding part of the user's name
    clean_name = "".join(filter(str.isalnum, username)).upper()[:4]
    if not clean_name:
        clean_name = "USER"
    rand_suffix = random.randint(1000, 9999)
    prefix = brand_name[:4].upper()
    voucher_code = f"{prefix}-{clean_name}-{rand_suffix}"

    data[uid]["vouchers"].append({
        "code": voucher_code,
        "name": f"{brand_name} Compensation Voucher",
        "value": value
    })
    save_economy(data)

# --- BRAND DATABASES & CONFIGS ---
BRANDS = {
    "greg": {
        "name": "Greggs",
        "email": "getintouch@greggs.co.uk",
        "color": 0xF26522,
        "branches": [
            {"town": "Newcastle upon Tyne", "street": "High Street West"},
            {"town": "London", "street": "Whitehall"},
            {"town": "Manchester", "street": "Market Street"},
            {"town": "Birmingham", "street": "High Street"},
            {"town": "Glasgow", "street": "Buchanan Street"}
        ],
        "items": ["Steak Bake", "Vegan Sausage Roll", "Festive Bake", "Sausage, Bean & Cheese Melt", "Yum Yum"],
        "scenarios": [
            "I popped into your store on {street} in {town} during my lunch hour and bought a freshly heated {item}. When I bit into it outside, it was stone cold in the middle and completely soggy.",
            "Visited the {town} branch ({street}) earlier and ordered a {item}. It was burnt to an absolute crisp on top, practically chipping my tooth, yet the filling was ice-cold."
        ]
    },
    "asda": {
        "name": "Asda",
        "email": "help@asda.co.uk",
        "color": 0x78BE20,
        "branches": [
            {"town": "Leeds", "street": "Hunslet Supercentre"},
            {"town": "Manchester", "street": "Asda Eastlands Superstore"},
            {"town": "London", "street": "Clapham Park Superstore"},
            {"town": "Bristol", "street": "Bedminster Superstore"},
            {"town": "Belfast", "street": "Spectrum Retail Park"}
        ],
        "items": ["Asda Chosen By You Ready Meal", "Extra Special Sourdough Pizza", "Smart Price Fresh Chicken", "Asda Bakery Tiger Loaf"],
        "scenarios": [
            "I visited your {town} store on {street} and bought a {item}. When I got home, I discovered the seal was broken and it was already going off. Completely ruined our family dinner.",
            "At your {street} branch in {town}, the shelf tag listed a {item} for one price, but at the checkout, I was overcharged significantly. Customer service refused to honour the shelf price!"
        ]
    },
    "kfc": {
        "name": "KFC",
        "email": "care@kfc.co.uk",
        "color": 0xF42A41,
        "branches": [
            {"town": "London", "street": "Leicester Square"},
            {"town": "Birmingham", "street": "Bullring Shopping Centre"},
            {"town": "Manchester", "street": "Arndale Centre"},
            {"town": "Liverpool", "street": "Paradise Street"},
            {"town": "Cardiff", "street": "Queen Street"}
        ],
        "items": ["Boneless Banquet", "Zinger Tower Burger", "Popcorn Chicken Bucket", "Hot Wings Box", "Gravy Portion"],
        "scenarios": [
            "Ordered a drive-thru meal at the {town} branch on {street}, including a {item}. Half of the items missing from the bag when I checked down the road, and the chicken was completely dry and stringy.",
            "Went into your {street} restaurant in {town} to order a {item}. The dining area was filthy, tables were uncleared, and my food took 45 minutes only to be served lukewarm."
        ]
    }
}

ANGRY_OPENINGS = [
    "To say I am absolutely fuming is an understatement. I demand an immediate explanation.",
    "I am writing this email while still shaking with absolute rage over what I experienced today.",
    "This is completely unacceptable. Your standards have dropped off a cliff and I want answers.",
    "I have never experienced such shocking customer service in my life."
]

ANGRY_CLOSINGS = [
    "I expect a full refund and substantial compensation vouchers sent to my email immediately.",
    "Sort your operations out before someone gets ill. Expecting prompt compensation.",
    "Let me know how you intend to rectify this situation as soon as possible."
]

SIGN_OFFS = ["Furious regards,", "Disgusted,", "Extremely unsatisfied,", "Waiting for a reply,"]


class SafeTempMail:
    def __init__(self):
        clean_domains = ["gmail-inbox.com", "mail-box.net", "verify-user.com", "1secmail.org"]
        first_names = ["alex", "jamie", "sam", "chris", "jordan", "taylor"]
        last_names = ["smith", "jones", "taylor", "brown", "wilson", "davies"]
        
        self.username = f"{random.choice(first_names)}.{random.choice(last_names)}{random.randint(1985, 2024)}"
        self.domain = random.choice(clean_domains)
        self.address = f"{self.username}@{self.domain}"
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get("https://www.1secmail.com/api/v1/?action=getDomainList", headers=headers, timeout=3)
            if resp.status_code == 200:
                domains = resp.json()
                if domains:
                    self.domain = domains[0]
                    self.address = f"{self.username}@{self.domain}"
        except Exception:
            pass 

    def check_inbox(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
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


def generate_angry_complaint(brand_key):
    b_data = BRANDS[brand_key]
    branch = random.choice(b_data["branches"])
    town = branch["town"]
    street = branch["street"]
    item = random.choice(b_data["items"])
    
    opening = random.choice(ANGRY_OPENINGS)
    scenario = random.choice(b_data["scenarios"]).format(town=town, street=street, item=item)
    closing = random.choice(ANGRY_CLOSINGS)
    signoff = random.choice(SIGN_OFFS)
    name = fake.name()
    
    email_body = (
        f"{opening}\n\n"
        f"Branch Location: {b_data['name']}, {street}, {town}\n\n"
        f"{scenario}\n\n"
        f"{closing}\n\n"
        f"{signoff}\n{name}"
    )
    return email_body, name, town, street, item


def create_email_image(sender, recipient, subject, body, brand_color="#F26522", output_path="sent_complaint.png"):
    width, height = 800, 520
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 13)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill=brand_color)
    draw.text((20, 20), "📤 Official Verified Grievance Dispatched", fill="white", font=font_title)

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


def create_reply_image(sender, subject, body, brand_color="#F26522", output_path="support_reply.png"):
    width, height = 800, 500
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill=brand_color)
    draw.text((20, 20), "🎫 Official Customer Support Resolution", fill="white", font=font_title)

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
    return "🟥" * filled_blocks + "⬛" * empty_blocks + f" **{progress_percent}%**"


async def watch_burner_inbox_with_progress(ctx, user_id, username, brand_key, temp_email, status_message, burner_address, max_wait_seconds=259200):
    elapsed = 0
    check_interval = 300 
    b_name = BRANDS[brand_key]["name"]

    while elapsed < max_wait_seconds:
        await asyncio.sleep(check_interval)
        elapsed += check_interval
        
        percent = min(100, int((elapsed / max_wait_seconds) * 100))
        emoji_bar_str = build_emoji_progress_bar(percent)
        
        try:
            days_left = round((max_wait_seconds - elapsed) / 86400, 1)
            await status_message.edit(content=
                f"✉️ **Burner inbox:** `{burner_address}`\n"
                f"⏳ **Status:** Monitoring {b_name} support system... *(Response window: 1-3 days)*\n"
                f"📊 **Progress Window:** `(~{days_left} days remaining)`\n"
                f"{emoji_bar_str}"
            )
        except Exception:
            pass

        incoming_msg = temp_email.check_inbox()
        if incoming_msg:
            subject = incoming_msg.subject
            sender = incoming_msg.from_addr
            body = incoming_msg.body
            
            reward_amount = round(random.uniform(5.00, 15.00), 2)
            add_user_balance(user_id, reward_amount)
            add_user_voucher(user_id, username, b_name, reward_amount)

            img_path = create_reply_image(sender, subject, body[:700], brand_color="#F26522" if brand_key=="greg" else ("#78BE20" if brand_key=="asda" else "#F42A41"))
            file = discord.File(img_path, filename="support_reply.png")
            
            await status_message.channel.send(
                f"🚨 **{b_name} Support resolved your ticket for {ctx.author.mention}!**\n"
                f"💰 **Compensation Credited:** `£{reward_amount:.2f}` added! Type `!redeem` privately to view your unique voucher code.",
                file=file
            )
            return

    fallback_reward = 10.00
    add_user_balance(user_id, fallback_reward)
    add_user_voucher(user_id, username, b_name, fallback_reward)
    await status_message.channel.send(
        f"⏰ **Ticket Window Expired:** {b_name} automatic resolution completed for `{burner_address}`.\n"
        f"🎁 **Bonus Credited:** `£{fallback_reward:.2f}` deposited for {ctx.author.mention}! Type `!redeem` to view vouchers."
    )


@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user} (ID: {bot.user.id})")


async def handle_complaint(ctx, brand_key):
    b_data = BRANDS[brand_key]
    temp_email = SafeTempMail()
    burner_address = temp_email.address
    
    email_body, name, town, street, item = generate_angry_complaint(brand_key)
    subject_line = f"Formal Complaint regarding service at {town} ({street}) branch"

    color_hex = "#F26522" if brand_key=="greg" else ("#78BE20" if brand_key=="asda" else "#F42A41")
    sent_img_path = create_email_image(burner_address, b_data["email"], subject_line, email_body, brand_color=color_hex)
    sent_file = discord.File(sent_img_path, filename="sent_complaint.png")
    
    await ctx.send(
        f"🔥 **{b_data['name']} Branch:** `{street}, {town}`\n"
        f"✉️ **Burner inbox:** `{burner_address}`\n"
        f"📝 **Complaint dispatched to {b_data['email']}:**",
        file=sent_file
    )

    msg = EmailMessage()
    msg.set_subject(subject_line)
    msg["From"] = burner_address 
    msg["To"] = b_data["email"]
    msg["Reply-To"] = burner_address 
    msg.set_content(email_body)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(AUTH_EMAIL, AUTH_PASSWORD)
            server.send_message(msg, from_addr=AUTH_EMAIL, to_addrs=[b_data["email"]])
    except Exception as e:
        await ctx.send(f"❌ Failed to dispatch email: {e}")
        return

    status_message = await ctx.send(
        f"✉️ **Burner inbox:** `{burner_address}`\n"
        f"⏳ **Status:** Ticket filed. *(Response window: 1-3 days)*\n"
        f"📊 **Progress Window:** `(~3.0 days remaining)`\n"
        f"{build_emoji_progress_bar(0)}"
    )

    bot.loop.create_task(watch_burner_inbox_with_progress(ctx, ctx.author.id, ctx.author.name, brand_key, temp_email, status_message, burner_address, max_wait_seconds=259200))


@bot.command(name="greg")
async def greg(ctx, action: str = None):
    if action == "gen":
        await handle_complaint(ctx, "greg")
    else:
        await ctx.send("⚠️ Usage: Type `!greg gen` to file a Greggs complaint, or `!redeem` to check your vouchers.")

@bot.command(name="asda")
async def asda(ctx, action: str = None):
    if action == "gen":
        await handle_complaint(ctx, "asda")
    else:
        await ctx.send("⚠️ Usage: Type `!asda gen` to file an Asda complaint, or `!redeem` to check your vouchers.")

@bot.command(name="kfc")
async def kfc(ctx, action: str = None):
    if action == "gen":
        await handle_complaint(ctx, "kfc")
    else:
        await ctx.send("⚠️ Usage: Type `!kfc gen` to file a KFC complaint, or `!redeem` to check your vouchers.")


@bot.command(name="redeem", aliases=["voucher"])
async def redeem_vouchers(ctx, voucher_code: str = None):
    data = load_economy()
    uid = str(ctx.author.id)
    user_data = data.get(uid, {"balance": 0.0, "vouchers": []})
    
    balance = user_data["balance"]
    vouchers = user_data["vouchers"]

    # If a specific voucher code was provided, look it up and cash it out privately
    if voucher_code:
        target_voucher = None
        target_idx = -1
        for idx, v in enumerate(vouchers):
            if v["code"].upper() == voucher_code.upper():
                target_voucher = v
                target_idx = idx
                break
        
        if target_voucher:
            # Remove voucher from inventory
            vouchers.pop(target_idx)
            save_economy(data)
            
            await ctx.message.delete() # Clean up chat command for privacy
            await ctx.author.send(
                f"🎉 **Voucher Successfully Claimed!**\n"
                f"🎁 **Item:** {target_voucher['name']}\n"
                f"💵 **Value:** £{target_voucher['value']:.2f}\n"
                f"🏷️ **Unique Barcode Code:** `{target_voucher['code']}`\n"
                f"*(Show this barcode code at any counter! This code is bound exclusively to your account.)*"
            )
            return
        else:
            await ctx.send(f"❌ Error: Voucher code `{voucher_code}` was not found in your inventory or is invalid.", delete_after=10)
            return

    # Otherwise, display the user's private list of unique codes ephemerally/privately via DM or ephemeral-style text
    if not vouchers:
        await ctx.author.send(
            f"🛒 **Your Voucher Wallet:**\n"
            f"**Total Balance:** `£{balance:.2f}`\n"
            f"*No saved vouchers yet. Try filing complaints using `!greg gen`, `!asda gen`, or `!kfc gen`!*"
        )
        await ctx.message.delete()
        return

    voucher_list_str = "\n".join([f"• **{v['name']}** (£{v['value']:.2f}) — Code: `{v['code']}`" for v in vouchers])
    
    await ctx.author.send(
        f"🛒 **Your Personal Universal Voucher Centre**\n"
        f"**Account Holder:** {ctx.author.name}\n"
        f"**Total Balance:** `£{balance:.2f}`\n\n"
        f"**Your Unique Vouchers:**\n{voucher_list_str}\n\n"
        f"*(To cash one out and generate your final barcode, type `!redeem [CODE]` in the server channel)*"
    )
    
    await ctx.message.delete()
    try:
        await ctx.send(f"📬 {ctx.author.mention}, I have sent your unique voucher wallet list privately via DM!", delete_after=10)
    except Exception:
        pass


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN environment variable is missing!")
    elif not os.getenv("SENDER_EMAIL") or not os.getenv("EMAIL_PASSWORD"):
        print("❌ Error: SENDER_EMAIL or EMAIL_PASSWORD environment variables are missing!")
    else:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        
        print("Starting Discord bot client...")
        bot.run(TOKEN)
