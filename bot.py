import os
import random
import smtplib
from email.message import EmailMessage
import discord
from discord.ext import commands
from faker import Faker

# --- Configuration & Environment Variables ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

GREGGS_SUPPORT_EMAIL = "getintouch@greggs.co.uk"

# Setup Faker for infinite British names and towns
fake = Faker("en_GB")

ITEMS = [
    "Steak Bake",
    "Vegan Sausage Roll",
    "Festive Bake",
    "Sausage, Bean & Cheese Melt",
    "Yum Yum",
    "Caramel Custard Doughnut",
    "Bacon Breakfast Roll",
    "Pepperoni Pizza Slice",
]

TRAGEDIES = [
    "It was structurally compromised and collapsed into my lap upon first bite.",
    "The pastry-to-filling ratio was mathematically offensive to baking standards.",
    "It was inexplicably cold in the middle, ruining my morning commute.",
    "They were completely sold out by 11 AM, which I consider a personal attack.",
    "The icing on the Yum Yum was sticky enough to remove a filling.",
    "I was handed a lukewarm tragedy wrapped in a paper bag.",
]

DEMANDS = [
    "I expect a swift resolution and complimentary baked goods.",
    "I demand a full inquiry into this specific branch's oven temperatures.",
    "Please send vouchers immediately to restore my faith in British baking.",
    "I await your formal apology.",
]

# Set up bot with intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def send_email_to_greggs(subject, letter_body, discord_user):
    """Sends the generated complaint via SMTP to Greggs support."""
    if not SENDER_EMAIL or not EMAIL_PASSWORD:
        print("Email credentials missing. Skipping email send.")
        return False

    msg = EmailMessage()
    msg.set_subject(subject)
    msg["From"] = SENDER_EMAIL
    msg["To"] = GREGGS_SUPPORT_EMAIL
    
    full_content = f"""
{letter_body}

---------------------------------------------------
[Automated copy generated via Discord user: {discord_user}]
    """
    msg.set_content(full_content)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send email to Greggs: {e}")
        return False


@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user} - Ready to dispatch grievances!")


@bot.command(name="gregger")
async def gregger(ctx, amount: int = 1):
    # Cap the amount between 1 and 5 so it doesn't spam email servers or get rate-limited
    amount = max(1, min(amount, 5))

    for i in range(amount):
        name = fake.name()
        town = fake.city()
        street = fake.street_address()
        date = fake.date_this_year(before_today=True, after_today=False)
        item = random.choice(ITEMS)
        tragedy = random.choice(TRAGEDIES)
        demand = random.choice(DEMANDS)

        email_subject = f"Customer Grievance regarding a {item} - {town} Branch"
        
        letter_body = (
            f"Dear Customer Care,\n\n"
            f"I am writing to express my profound disappointment following my visit to your {town} branch ({street}). "
            f"On {date}, I purchased a {item}, expecting the usual high standard. Instead, {tragedy.lower()}\n\n"
            f"{demand}\n\n"
            f"Yours sincerely,\n{name}"
        )

        # 1. Send the email to Greggs
        email_sent = send_email_to_greggs(email_subject, letter_body, str(ctx.author))

        # 2. Build the Discord Embed
        embed = discord.Embed(
            title=f"🥧 Greggs Grievance #{i + 1}",
            description=(
                f"**From:** {name}\n**Branch:** {street}, {town}\n"
                f"**Date:** {date}\n**Item:** {item}"
            ),
            color=0xF26522,  # Official Greggs Orange
        )

        embed.add_field(name="Formal Complaint Letter", value=f"**Subject:** {email_subject}\n\n{letter_body}", inline=False)
        
        # Add a footer indicator showing if the email successfully fired off
        if email_sent:
            embed.set_footer(text="✉️ Successfully dispatched to Greggs Customer Care!")
        else:
            embed.set_footer(text="⚠️ Generated in chat, but email failed to send (check credentials).")

        await ctx.send(embed=embed)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable is missing!")
    else:
        bot.run(DISCORD_TOKEN)
