import os
import random
import smtplib
from email.message import EmailMessage
import asyncio
import threading
from flask import Flask
import discord
from discord.ext import commands
from faker import Faker
from tempmail import EMail
from PIL import Image, ImageDraw, ImageFont

# --- Flask Tiny Web Server (Required for Render Web Service Port Binding) ---
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
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

ITEMS = [
    "Steak Bake", "Vegan Sausage Roll", "Festive Bake", 
    "Sausage, Bean & Cheese Melt", "Yum Yum", "Caramel Custard Doughnut"
]
TRAGEDIES = [
    "It was structurally compromised and collapsed into my lap upon first bite.",
    "The pastry-to-filling ratio was mathematically offensive to baking standards.",
    "It was inexplicably cold in the middle, ruining my morning commute.",
]
DEMANDS = [
    "I expect a swift resolution and complimentary baked goods.",
    "I demand a full inquiry into this specific branch's oven temperatures.",
]


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


async def watch_burner_inbox(temp_email, ctx, max_wait_seconds=7200):
    elapsed = 0
    check_interval = 30 

    while elapsed < max_wait_seconds:
        await asyncio.sleep(check_interval)
        elapsed += check_interval

        try:
            incoming_msg = temp_email.get_message()
            if incoming_msg:
                subject = incoming_msg.subject
                sender = incoming_msg.from_addr
                body = incoming_msg.body
                
                img_path = create_reply_image(sender, subject, body[:700])
                file = discord.File(img_path, filename="greggs_reply.png")
                await ctx.send(f"🚨 **Greggs support has replied to your burner email, {ctx.author.mention}!**", file=file)
                return
        except Exception:
            continue

    await ctx.send(f"⏰ **Timed out:** Greggs did not reply within the 2-hour window for burner inbox `{temp_email.address}`.")


@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user}")


@bot.command(name="gregger")
async def gregger(ctx):
    temp_email = EMail()
    burner_address = temp_email.address
    
    item = random.choice(ITEMS)
    town = fake.city()
    name = fake.name()
    street = fake.street_address()
    tragedy = random.choice(TRAGEDIES)
    demand = random.choice(DEMANDS)

    await ctx.send(f"✉️ **Burner inbox generated:** `{burner_address}`\nDispatching complaint to Greggs...")

    msg = EmailMessage()
    msg.set_subject(f"Grievance regarding a {item} - {town} Branch")
    msg["From"] = burner_address 
    msg["To"] = GREGGS_SUPPORT_EMAIL
    msg["Reply-To"] = burner_address 
    
    email_body = (
        f"Dear Customer Care,\n\n"
        f"I visited your {town} branch ({street}) and purchased a {item}. {tragedy}\n\n"
        f"{demand}\n\n"
        f"Yours sincerely,\n{name}"
    )
    msg.set_content(email_body)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(AUTH_EMAIL, AUTH_PASSWORD)
            server.send_message(msg, from_addr=AUTH_EMAIL, to_addrs=[GREGGS_SUPPORT_EMAIL])
    except Exception as e:
        await ctx.send(f"❌ Failed to dispatch email: {e}")
        return

    await ctx.send("⏳ Complaint sent successfully! Monitoring burner inbox in background (giving Greggs up to **2 hours** to reply).")
    bot.loop.create_task(watch_burner_inbox(temp_email, ctx, max_wait_seconds=7200))


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing!")
    else:
        # Start the Flask web server in a background thread so Render's port check passes
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()

        # Start the Discord bot on the main thread
        bot.run(TOKEN)
