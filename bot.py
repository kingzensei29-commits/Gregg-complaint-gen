import os
import random
import smtplib
from email.message import EmailMessage
import asyncio
import threading
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
    app.run(host="0.0.0.0", port=port)

# --- SMTP Config ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
AUTH_EMAIL = os.getenv("SENDER_EMAIL")     
AUTH_PASSWORD = os.getenv("EMAIL_PASSWORD") 

GREGGS_SUPPORT_EMAIL = "getintouch@greggs.co.uk"

fake = Faker("en_GB")

# --- Discord Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

# --- ADVANCED HUMANIZER POOLS ---
ITEMS = [
    "Steak Bake", "Vegan Sausage Roll", "Festive Bake", 
    "Sausage, Bean & Cheese Melt", "Yum Yum", "Chicken Bake", "Jam Doughnut"
]

OPENINGS = [
    "To whom it may concern, I am writing this because I'm actually fuming.",
    "Morning. Not usually one to complain, but I've had a shocker today.",
    "Hello team, I need to raise an issue about what happened earlier.",
    "Hi there, genuinely gutted about my experience at one of your shops today.",
    "Listen, I love Greggs as much as the next bloke, but today was an absolute joke."
]

SCENARIOS = [
    "I popped into the local branch on my break and grabbed a {item}. When I took my first bite outside, it was stone cold in the middle like it had just come out of a freezer.",
    "Bought a {item} earlier today and honestly, the structural integrity was completely gone. It dissolved into a pile of crumbs and grease the second I touched it.",
    "Got served a {item} that was so burnt on top it practically chipped my tooth, yet the filling was somehow freezing cold. Make it make sense.",
    "Visited the counter for a quick {item} before work. The pastry was soggy, greasy, and completely inedible. Ruined my morning entirely.",
    "Absolute shambles today. My {item} was bone dry and tasted like it had been sitting under that heatlamp since Tuesday."
]

CLOSINGS = [
    "Expected way better from Greggs to be honest. Sorting out some vouchers or a refund wouldn't go amiss.",
    "I've got photos if you need them. Let me know how we're resolving this.",
    "Not happy at all. Look forward to hearing back from someone soon.",
    "Sort your ovens out lads. Cheers.",
    "Absolute waste of my hard-earned cash. Sort it out please."
]

SIGN_OFFS = [
    "Regrets,", "Kind regards (reluctantly),", "Cheers,", "Best,", "Yours,"
]


class SafeTempMail:
    def __init__(self):
        self.domain = "1secmail.com"
        letters = "abcdefghijklmnopqrstuvwxyz0123456789"
        self.username = ''.join(random.choice(letters) for i in range(10))
        self.address = f"{self.username}@{self.domain}"
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get("https://www.1secmail.com/api/v1/?action=getDomainList", headers=headers, timeout=5)
            if resp.status_code == 200:
                domains = resp.json()
                if domains:
                    self.domain = random.choice(domains)
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


def generate_human_complaint(item, town, street):
    opening = random.choice(OPENINGS)
    scenario = random.choice(SCENARIOS).format(item=item)
    closing = random.choice(CLOSINGS)
    signoff = random.choice(SIGN_OFFS)
    name = fake.name()
    
    if random.random() > 0.5:
        opening = opening.lower()
        
    email_body = (
        f"{opening}\n\n"
        f"This was at the {town} branch on {street}.\n\n"
        f"{scenario}\n\n"
        f"{closing}\n\n"
        f"{signoff}\n{name}"
    )
    return email_body, name


def create_email_image(sender, recipient, subject, body, output_path="sent_complaint.png"):
    width, height = 800, 500
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 13)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill="#F26522")
    draw.text((20, 20), "📤 Outbound Complaint Dispatched to Greggs", fill="white", font=font_title)

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
    draw.text((20, 20), "🥧 Greggs Customer Support Response", fill="white", font=font_title)

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
    
    # 🟥 for bright red progress squares, ⬛ for sleek dark empty blocks
    bar = "🟥" * filled_blocks + "⬛" * empty_blocks
    return f"{bar} **{progress_percent}%**"


async def watch_burner_inbox_with_progress(temp_email, status_message, burner_address, max_wait_seconds=7200):
    elapsed = 0
    check_interval = 30 

    while elapsed < max_wait_seconds:
        await asyncio.sleep(check_interval)
        elapsed += check_interval
        
        percent = min(100, int((elapsed / max_wait_seconds) * 100))
        emoji_bar_str = build_emoji_progress_bar(percent)
        
        try:
            hours_left = round((max_wait_seconds - elapsed) / 3600, 1)
            await status_message.edit(content=
                f"✉️ **Burner inbox:** `{burner_address}`\n"
                f"⏳ **Status:** Monitoring inbox for Greggs reply...\n"
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
            
            img_path = create_reply_image(sender, subject, body[:700])
            file = discord.File(img_path, filename="greggs_reply.png")
            await status_message.channel.send(f"🚨 **Greggs support has replied to your burner email!**", file=file)
            return

    await status_message.channel.send(f"⏰ **Timed out:** Greggs did not reply within the 2-hour window for burner inbox `{burner_address}`.")


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
        
        item = random.choice(ITEMS)
        town = fake.city()
        street = fake.street_address()

        email_body, name = generate_human_complaint(item, town, street)
        subject_line = f"Disappointed with my visit to {town} branch"

        sent_img_path = create_email_image(burner_address, GREGGS_SUPPORT_EMAIL, subject_line, email_body)
        sent_file = discord.File(sent_img_path, filename="sent_complaint.png")
        
        await ctx.send(
            f"✉️ **Generated burner inbox:** `{burner_address}`\n"
            f"📝 **Humanized complaint synthesized.** Here is the exact email dispatched to Greggs:",
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
            f"⏳ **Status:** Complaint dispatched! Monitoring inbox...\n"
            f"📊 **Progress Window:** `(~2.0h remaining)`\n"
            f"{initial_emoji_bar}"
        )

        bot.loop.create_task(watch_burner_inbox_with_progress(temp_email, status_message, burner_address, max_wait_seconds=7200))
    else:
        await ctx.send("⚠️ Usage: Type `!greg gen` to generate and send a humanized complaint to Greggs!")


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing!")
    else:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
