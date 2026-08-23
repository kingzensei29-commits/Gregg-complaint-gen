import os
import random
import smtplib
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
import asyncio
from PIL import Image, ImageDraw, ImageFont
import discord
from discord.ext import commands, tasks
from faker import Faker

# --- Configuration & Environment Variables ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")

# The Discord channel ID where the bot will drop Greggs' reply images
TARGET_DISCORD_CHANNEL_ID = int(os.getenv("TARGET_DISCORD_CHANNEL_ID", "0"))

GREGGS_SUPPORT_EMAIL = "getintouch@greggs.co.uk"

# Setup Faker for British data
fake = Faker("en_GB")

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

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def send_email_to_greggs(subject, letter_body, discord_user):
    """Sends the generated complaint to Greggs."""
    if not SENDER_EMAIL or not EMAIL_PASSWORD:
        return False

    msg = EmailMessage()
    msg.set_subject(subject)
    msg["From"] = SENDER_EMAIL
    msg["To"] = GREGGS_SUPPORT_EMAIL
    msg.set_content(f"{letter_body}\n\n[Automated Discord User: {discord_user}]")

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False


def create_reply_image(sender, subject, body, output_path="greggs_reply.png"):
    """Turns the email text into a clean image attachment for Discord."""
    # Setup image canvas
    width, height = 800, 600
    image = Image.new("RGB", (width, height), color="#FFF3E0") # Light orange tint background
    draw = ImageDraw.Draw(image)

    # Use default font or load a TTF if available
    try:
        font_title = ImageFont.truetype("arial.ttf", 20)
        font_body = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Draw Header box
    draw.rectangle([(0, 0), (width, 80)], fill="#F26522") # Greggs Orange header
    draw.text((20, 25), "🥧 Official Greggs Customer Care Reply", fill="white", font=font_title)

    # Format text fields
    content_text = f"From: {sender}\nSubject: {subject}\n\n{body}"
    
    # Word wrap utility simulation for drawing text safely on image
    margin = 25
    y_text = 100
    for line in content_text.splitlines():
        if y_text > height - 50:
            break
        draw.text((margin, y_text), line, fill="#333333", font=font_body)
        y_text += 22

    image.save(output_path)
    return output_path


@tasks.loop(minutes=5)
async def check_greggs_replies():
    """Background task checking your inbox every 5 mins for replies from Greggs."""
    if not TARGET_DISCORD_CHANNEL_ID or not SENDER_EMAIL or not EMAIL_PASSWORD:
        return

    try:
        # Connect to IMAP inbox
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(SENDER_EMAIL, EMAIL_PASSWORD)
        mail.select("inbox")

        # Search for unread emails from Greggs support
        status, messages = mail.search(None, f'(UNSEEN FROM "{GREGGS_SUPPORT_EMAIL}")')
        
        if status != "OK":
            mail.logout()
            return

        for num in messages[0].split():
            res, msg_data = mail.fetch(num, "(RFC822)")
            if res != "OK":
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decode Subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8", errors="ignore")

                    # Extract body text
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")

                    # Generate image of the reply
                    img_path = create_reply_image(GREGGS_SUPPORT_EMAIL, subject, body[:800]) # Trim long bodies

                    # Send to Discord channel
                    channel = bot.get_channel(TARGET_DISCORD_CHANNEL_ID)
                    if channel:
                        file = discord.File(img_path, filename="greggs_reply.png")
                        await channel.send("🚨 **New response received from Greggs Support!**", file=file)

        mail.logout()
    except Exception as e:
        print(f"IMAP checking error: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not check_greggs_replies.is_running():
        check_greggs_replies.start()


@bot.command(name="gregger")
async def gregger(ctx, amount: int = 1):
    amount = max(1, min(amount, 3))

    for i in range(amount):
        name = fake.name()
        town = fake.city()
        street = fake.street_address()
        item = random.choice(ITEMS)
        tragedy = random.choice(TRAGEDIES)
        demand = random.choice(DEMANDS)

        email_subject = f"Grievance regarding {item} - {town}"
        letter_body = f"Dear Customer Care,\n\nI visited your {town} branch ({street}) and bought a {item}. {tragedy}\n\n{demand}\n\nSincerely,\n{name}"

        # Send email
        email_sent = send_email_to_greggs(email_subject, letter_body, str(ctx.author))

        embed = discord.Embed(title=f"🥧 Grievance Dispatched #{i+1}", description=f"**Item:** {item}\n**Branch:** {town}", color=0xF26522)
        embed.set_footer(text="✉️ Sent to Greggs. Awaiting manual email reply...")
        await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
