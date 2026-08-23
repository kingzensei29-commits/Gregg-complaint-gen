import os
import random
import smtplib
from email.message import EmailMessage
import discord
from discord.ext import commands
from faker import Faker
from tempmail import EMail  # Free temporary email generator
from PIL import Image, ImageDraw, ImageFont

# --- SMTP Config (Used to send out the initial email to Greggs) ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

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


def create_reply_image(sender, subject, body, output_path="greggs_reply.png"):
    """Renders the incoming email response text into a clean image card."""
    width, height = 800, 500
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Header bar matching Greggs orange
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


@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user}")


@bot.command(name="gregger")
async def gregger(ctx):
    # 1. Generate a temporary burner email address automatically
    temp_email = EMail()
    burner_address = temp_email.address
    
    item = random.choice(ITEMS)
    town = fake.city()
    name = fake.name()
    street = fake.street_address()
    tragedy = random.choice(TRAGEDIES)
    demand = random.choice(DEMANDS)

    await ctx.send(f"✉️ **Burner inbox generated:** `{burner_address}`\nDispatching complaint to Greggs...")

    # 2. Build the email payload with Reply-To pointed at our temporary inbox
    msg = EmailMessage()
    msg.set_subject(f"Grievance regarding a {item} - {town} Branch")
    msg["From"] = SENDER_EMAIL
    msg["To"] = GREGGS_SUPPORT_EMAIL
    msg["Reply-To"] = burner_address  # Forces Greggs support replies to land in our burner inbox
    
    email_body = (
        f"Dear Customer Care,\n\n"
        f"I visited your {town} branch ({street}) and purchased a {item}. {tragedy}\n\n"
        f"{demand}\n\n"
        f"Yours sincerely,\n{name}"
    )
    msg.set_content(email_body)

    # 3. Send out via SMTP
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        await ctx.send(f"❌ Failed to dispatch email: {e}")
        return

    await ctx.send("⏳ Complaint sent! Listening for Greggs response in the server (waiting up to 90 seconds)...")

    # 4. Wait for incoming mail asynchronously in the background
    try:
        # This pauses and waits up to 90 seconds for an email reply to land on the burner address
        incoming_msg = temp_email.wait_for_message(timeout=90)
        
        if incoming_msg:
            subject = incoming_msg.subject
            sender = incoming_msg.from_addr
            body = incoming_msg.body
            
            # Generate image screenshot of the reply
            img_path = create_reply_image(sender, subject, body[:700])
            file = discord.File(img_path, filename="greggs_reply.png")
            
            # Send the resulting image straight back into the Discord channel!
            await ctx.send("🚨 **Greggs support has replied!**", file=file)
        else:
            await ctx.send("⏰ Timed out: Greggs did not reply within 90 seconds.")
            
    except Exception as e:
        await ctx.send(f"⚠️ Error while listening for reply: {e}")


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing!")
    else:
        bot.run(TOKEN)
