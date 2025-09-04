import discord
from discord.ext import commands
import requests
import os
import re

# Load token from local file
TOKEN_FILE = "token.txt"
if not os.path.exists(TOKEN_FILE):
    print(f"[LOG] Token file {TOKEN_FILE} not found.")
    exit(1)

with open(TOKEN_FILE, "r") as f:
    TOKEN = f.read().strip()

# Enable intents, including message content intent
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Utility function to fetch a Bluesky post ---
def fetch_bsky_post(url):
    print(f"[LOG] Attempting to fetch post from URL: {url}")
    match = re.search(r"profile/([^/]+)/post/([^/]+)", url)
    if not match:
        print("[LOG] URL pattern not recognized.")
        return None, None, None, []

    handle, rkey = match.groups()
    post_uri = f"at://{handle}/app.bsky.feed.post/{rkey}"

    api_url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread"
    try:
        r = requests.get(api_url, params={"uri": post_uri, "depth": 0}, timeout=10)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[LOG] Failed to fetch post: {e}")
        return None, None, None, []

    data = r.json()
    post = data.get("thread", {}).get("post", {})
    author = post.get("author", {}).get("handle")
    record = post.get("record", {})
    text = record.get("text")
    date = record.get("createdAt")

    embed = post.get("embed") or record.get("embed")
    media_files = []
    if embed and "images" in embed:
        os.makedirs("media", exist_ok=True)
        for i, img in enumerate(embed["images"]):
            img_url = img.get("fullsize") or img.get("thumb")
            if img_url:
                fname = f"media/image_{i}.jpg"
                try:
                    img_data = requests.get(img_url, timeout=10).content
                    with open(fname, "wb") as f:
                        f.write(img_data)
                    media_files.append(fname)
                    print(f"[LOG] Saved media file: {fname}")
                except requests.exceptions.RequestException as e:
                    print(f"[LOG] Failed to download image: {e}")

    print(f"[LOG] Post fetch successful: Author={author}, Text length={len(text) if text else 0}")
    return author, text, date, media_files

# --- Text command (!bsky) ---
@bot.command(name="bsky")
async def bsky_cmd(ctx, url: str):
    await ctx.send("⏳ Fetching Bluesky post...")
    author, text, date, media_files = fetch_bsky_post(url)

    if not author:
        await ctx.send("❌ Unable to fetch the post, please try again later.")
        print("[LOG] Post fetch failed.")
        return

    msg = f"✅ **Author:** {author}\n📝 **Text:** {text}\n📅 **Date:** {date}"

    if media_files:
        await ctx.send(msg, files=[discord.File(f) for f in media_files])
    else:
        await ctx.send(msg + "\n⚠️ No media found in this post.")

# --- Slash command (/bsky) ---
@bot.tree.command(name="bsky", description="Fetch a Bluesky post from a URL")
async def bsky_slash(interaction: discord.Interaction, url: str):
    await interaction.response.send_message("⏳ Fetching Bluesky post...")
    author, text, date, media_files = fetch_bsky_post(url)

    if not author:
        await interaction.followup.send("❌ Unable to fetch the post, please try again later.")
        print("[LOG] Post fetch failed.")
        return

    msg = f"✅ **Author:** {author}\n📝 **Text:** {text}\n📅 **Date:** {date}"

    if media_files:
        await interaction.followup.send(msg, files=[discord.File(f) for f in media_files])
    else:
        await interaction.followup.send(msg + "\n⚠️ No media found in this post.")

# --- Sync slash commands ---
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"[LOG] {len(synced)} slash commands synced.")
    except Exception as e:
        print(f"[LOG] Slash command sync failed: {e}")

# --- Run the bot ---
bot.run(TOKEN)
