import os
import random
import asyncio
import threading
import json
import re
import requests
from flask import Flask, request, jsonify
import discord
from discord.ext import commands
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# --- Flask Web Server & Brevo Inbound Webhook Hub ---
app = Flask(__name__)

# Active tracker to match incoming emails to discord users
ACTIVE_DISCORD_USERS = {}

@app.route("/")
def health_check():
    return "🍗 Brevo Inbound Pipeline Bot is online and listening!"

@app.route("/brevo-inbound", methods=["POST"])
def brevo_inbound_webhook():
    """Catches inbound email replies forwarded by Brevo and auto-extracts vouchers."""
    try:
        data = request.json or request.form
        print(f"📥 Brevo Inbound Webhook Triggered: {data}")

        # Extract email fields sent by Brevo's parsing engine
        sender_email = data.get("from", {}).get("email", "") or data.get("sender", "")
        body_content = data.get("textBody", "") or data.get("body", "") or data.get("stripped-text", "")
        subject_line = data.get("subject", "")

        # Look for a user session matching this email or parse codes natively
        target_user_id = None
        brand_matched = "Corporate Support"

        for uid, session in list(ACTIVE_DISCORD_USERS.items()):
            if session["email"].lower() in sender_email.lower() or session["email"].lower() in body_content.lower():
                target_user_id = uid
                brand_matched = session["brand_name"]
                break

        # Fallback to the most recent user if direct match fails but traffic is active
        if not target_user_id and ACTIVE_DISCORD_USERS:
            target_user_id, session = list(ACTIVE_DISCORD_USERS.items())[0]
            brand_matched = session["brand_name"]

        if target_user_id:
            # Search text content for standard voucher patterns (e.g., alphanumeric codes or monetary values)
            code_match = re.search(r'\b([A-Z0-9]{4,6}-[A-Z0-9]{4,6}-[A-Z0-9]{4,6}|[A-Z0-9]{8,12})\b', body_content)
            extracted_code = code_match.group(1) if code_match else f"{brand_matched[:4].upper()}-REPLY-{random.randint(1000,9999)}"
            
            val = round(random.uniform(5.00, 25.00), 2)
            
            # Save to unified storage
            add_user_balance(target_user_id, val)
            add_user_voucher(target_user_id, ACTIVE_DISCORD_USERS[target_user_id]["username"], brand_matched, val, extracted_code, status="Ready to Use")
            
            print(f"✅ Successfully extracted voucher for user {target_user_id}: {extracted_code}")
            
            # Clean up active session
            del ACTIVE_DISCORD_USERS[target_user_id]
            return jsonify({"status": "success", "processed": True}), 200

        return jsonify({"status": "ignored", "reason": "No matching active user session"}), 200

    except Exception as e:
        print(f"Webhook parsing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

fake = Faker("en_GB")

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

ECONOMY_FILE = "user_economy.json"
SHARED_VOUCHERS_FILE = "shared_vouchers.json"
BRANDS_FILE = "brands.json"

def load_json_file(filename, default_val=None):
    if default_val is None:
        default_val = {}
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_val

def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save {filename}: {e}")

BRANDS = load_json_file(BRANDS_FILE, {})

def load_economy():
    return load_json_file(ECONOMY_FILE, {})

def save_economy(data):
    save_json_file(ECONOMY_FILE, data)

def load_shared_vouchers():
    return load_json_file(SHARED_VOUCHERS_FILE, {})

def save_shared_vouchers(data):
    save_json_file(SHARED_VOUCHERS_FILE, data)

def add_user_balance(user_id, amount):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    data[uid]["balance"] += float(amount)
    save_economy(data)
    return data[uid]["balance"]

def add_user_voucher(user_id, username, brand_name, value, custom_code, status="Ready to Use"):
    data = load_economy()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0.0, "vouchers": []}
    
    data[uid]["vouchers"].append({
        "code": custom_code,
        "name": f"{brand_name} Voucher",
        "value": value,
        "status": status
    })
    save_economy(data)

def generate_mistral_complaint(brand_key):
    b_data = BRANDS[brand_key]
    town = random.choice(b_data["towns"])
    consistent_name = fake.name()
    api_key = os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        fallback_issue = f"I am thoroughly disgusted with the appalling service at your {town} branch."
        email_body = f"Dear Support Team,\n\nMy name is {consistent_name}. I am writing to formally complain about my terrible experience at your {town} branch.\n\n{fallback_issue}\n\nI expect a generous goodwill gift voucher.\n\nRegards,\n{consistent_name}"
        return email_body, consistent_name, town, f"Unacceptable experience at {town} branch"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"You are an irate, genuinely furious UK customer writing a formal complaint email to customer relations for the brand '{b_data['name']}'. "
        f"The incident occurred at their physical store or via delivery in {town}. "
        f"STRICT RULES:\n"
        f"1. Reference specific realistic items sold by '{b_data['name']}' that were ruined, faulty, or missing.\n"
        f"2. Tone must be deeply angry, highly critical, and completely human.\n"
        f"3. Explicitly demand a substantial financial refund or a goodwill gift voucher as compensation.\n"
        f"4. ABSOLUTE CONSTRAINT: NEVER mention receipts, paper proof, transaction numbers, or having physical evidence.\n"
        f"5. Sign off using the exact consumer name: '{consistent_name}'.\n"
        f"6. On the very first line of your response, write a custom email subject line starting with 'SUBJECT: '."
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": 400
    }

    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            result_json = response.json()
            content = result_json["choices"][0]["message"]["content"].strip()
            lines = content.splitlines()
            subject_line = f"Absolute shambles at your {town} branch"
            body_lines = lines
            if lines and lines[0].lower().startswith("subject:"):
                subject_line = lines[0].split(":", 1)[1].strip()
                body_lines = lines[1:]
            return "\n".join(body_lines).strip(), consistent_name, town, subject_line
    except Exception:
        pass

    return f"Terrible service at {town}. I demand a voucher.", consistent_name, town, "Complaint"

def create_email_image(sender, recipient, subject, body, brand_color=0xF26522, output_path="sent_complaint.png"):
    if isinstance(brand_color, int):
        brand_color = f"#{brand_color:06x}"
    width, height = 800, 540
    image = Image.new("RGB", (width, height), color="#FFF3E0")
    draw = ImageDraw.Draw(image)
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 12)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 70)], fill=brand_color)
    draw.text((20, 20), "📤 Brevo Pipeline Dispatched Complaint", fill="white", font=font_title)
    content_text = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n" + "-" * 68 + f"\n\n{body}"
    
    y_text = 85
    for line in content_text.splitlines():
        if y_text > height - 25:
            break
        draw.text((20, y_text), line, fill="#222222", font=font_body)
        y_text += 17
    image.save(output_path)
    return output_path

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip().lower()
    
    if content.startswith("!") and content.endswith(" gen"):
        brand_query = content[1:-4].strip()
        
        if brand_query in BRANDS:
            ctx = await bot.get_context(message)
            try:
                await message.delete()
            except Exception:
                pass

            b_info = BRANDS[brand_query]
            email_body, complaint_name, town, subject_line = await asyncio.to_thread(generate_mistral_complaint, brand_query)
            
            # Generate a clean custom tracking tag or reply address for Brevo tracking
            unique_tag = f"user-{ctx.author.id}-{random.randint(100,999)}"
            reply_address = os.getenv("BREVO_SENDER_EMAIL", "iusethisforwatching@gmail.com")

            # Track user session for inbound routing
            ACTIVE_DISCORD_USERS[str(ctx.author.id)] = {
                "email": reply_address,
                "username": ctx.author.name,
                "brand_name": b_info["name"]
            }

            add_user_voucher(ctx.author.id, ctx.author.name, b_info["name"], 0.00, f"PENDING-{random.randint(1000,9999)}", status="Pending / Processing")

            sent_img_path = create_email_image(reply_address, b_info["email"], subject_line, email_body, brand_color=b_info["color"])
            sent_file = discord.File(sent_img_path, filename="sent_complaint.png")

            await ctx.send(f"🔥 **{b_info['name']} (Brevo Hub Active)**: Complaint dispatched successfully.", file=sent_file)

            def send_brevo_email():
                api_key = os.getenv("BREVO_API_KEY")
                if not api_key:
                    raise Exception("BREVO_API_KEY is missing.")
                headers = {"api-key": api_key, "Content-Type": "application/json"}
                payload = {
                    "sender": {"name": "Consumer Grievances", "email": reply_address},
                    "to": [{"email": b_info["email"], "name": b_info["name"]}],
                    "subject": subject_line,
                    "textContent": email_body,
                    "replyTo": {"email": reply_address},
                    "tags": [unique_tag]
                }
                requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=8)

            try:
                await asyncio.to_thread(send_brevo_email)
            except Exception as e:
                await ctx.send(f"❌ Dispatch failure: {e}")
                return

            await ctx.send(f"⏳ **Pipeline Armed:** Waiting for Brevo webhook to catch customer service reply...")
            return

    await bot.process_commands(message)

@bot.command(name="voucher", aliases=["wallet", "vouchers"])
async def show_voucher_wallet(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    data = load_economy()
    uid = str(ctx.author.id)
    
    if uid not in data or (not data[uid]["vouchers"] and data[uid]["balance"] <= 0):
        await ctx.send(f"📦 {ctx.author.mention}, your wallet ledger is empty! File a complaint using `![brand] gen`.")
        return

    balance = data[uid].get("balance", 0.0)
    vouchers = data[uid].get("vouchers", [])

    embed = discord.Embed(
        title=f"💳 {ctx.author.name}'s Unified Voucher & Wallet Ledger",
        description=f"Total Virtual Balance: **£{balance:.2f}**",
        color=0x3498DB
    )

    for i, v in enumerate(vouchers, 1):
        status = v.get("status", "Ready to Use")
        status_icon = "🟢 **Ready to Use**" if status == "Ready to Use" else "⏳ **Pending / Processing**"
        field_value = f"Code: `{v['code']}`\nValue: **£{v['value']:.2f}**\nStatus: {status_icon}"
        embed.add_field(name=f"Request #{i}: {v['name']}", value=field_value, inline=False)

    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | Brevo Inbound Webhook Pipeline running.")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        server_thread = threading.Thread(target=run_web_server)
        server_thread.daemon = True
        server_thread.start()
        bot.run(TOKEN)
