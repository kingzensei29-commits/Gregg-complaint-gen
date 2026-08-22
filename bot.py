import os
import random
import discord
from discord.ext import commands
from faker import Faker

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
    (
        "The pastry-to-filling ratio was mathematically offensive to baking"
        " standards."
    ),
    "It was inexplicably cold in the middle, ruining my morning commute.",
    (
        "They were completely sold out by 11 AM, which I consider a personal"
        " attack."
    ),
    "The icing on the Yum Yum was sticky enough to remove a filling.",
    "I was handed a lukewarm tragedy wrapped in a paper bag.",
]

DEMANDS = [
    "I expect a swift resolution and complimentary baked goods.",
    (
        "I demand a full inquiry into this specific branch's oven"
        " temperatures."
    ),
    "Please send vouchers immediately to restore my faith in British baking.",
    "I await your formal apology.",
]

# Set up bot with message_content intent so it can read commands
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  print(f"Logged in successfully as {bot.user}")


@bot.command(name="gregger")
async def gregger(ctx, amount: int = 1):
  # Cap the amount between 1 and 10 so it doesn't crash chat or get rate-limited
  amount = max(1, min(amount, 10))

  for i in range(amount):
    name = fake.name()
    town = fake.city()
    street = fake.street_address()
    date = fake.date_this_year(before_today=True, after_today=False)
    item = random.choice(ITEMS)
    tragedy = random.choice(TRAGEDIES)
    demand = random.choice(DEMANDS)

    embed = discord.Embed(
        title=f"🥧 Greggs Grievance #{i + 1}",
        description=(
            f"**From:** {name}\n**Branch:** {street},"
            f" {town}\n**Date:** {date}\n**Item:** {item}"
        ),
        color=0xF26522,  # Official Greggs Orange
    )

    letter_body = (
        f"**Subject:** Unacceptable experience regarding a {item}\n\nDear"
        f" Customer Care,\n\nI am writing to express my profound disappointment"
        f" following my visit to your {town} branch. I purchased a {item},"
        f" expecting the usual high standard. Instead,"
        f" {tragedy.lower()}\n\n{demand}\n\nYours"
        f" sincerely,\n{name}"
    )

    embed.add_field(name="Formal Complaint Letter", value=letter_body, inline=False)
    await ctx.send(embed=embed)


if __name__ == "__main__":
  # Pull token securely from environment variables on Render
  TOKEN = os.getenv("DISCORD_TOKEN")
  if not TOKEN:
    print("Error: DISCORD_TOKEN environment variable is missing!")
  else:
    bot.run(TOKEN)
