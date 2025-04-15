import os
import re
import shutil
import platform
import requests
import instaloader
import telebot
from time import sleep
from dotenv import load_dotenv

# Load env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
IG_SESSIONID = os.getenv("IG_SESSIONID")

# Bot
bot = telebot.TeleBot(BOT_TOKEN)

# Paths
if platform.system() == "Windows":
    download_path = f"C://Users//{os.getlogin()}//Downloads"
else:
    download_path = "/data/data/com.termux/files/home/storage/downloads"

temp_dir = os.path.join(download_path, "temp_download")
os.makedirs(temp_dir, exist_ok=True)

# Setup Instaloader
L = instaloader.Instaloader(
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    post_metadata_txt_pattern="",
    filename_pattern="{shortcode}"
)
L.context._session.cookies.set('sessionid', IG_SESSIONID, domain=".instagram.com")

# Extract shortcode
def extract_shortcode(url):
    match = re.search(r"instagram\.com/(?:reel|p|tv)/([^/?#&]+)", url)
    return match.group(1) if match else None

# Download post logic
def download_post(shortcode):
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.dirname_pattern = temp_dir
    L.download_post(post, target="")

    # Filter media files
    files = [file for file in os.listdir(temp_dir) if file.endswith((".mp4", ".jpg", ".jpeg", ".png")) and shortcode in file]
    if not files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, post

    saved_files = []
    for file in files:
        old_path = os.path.join(temp_dir, file)
        new_name = f"{post.owner_username}_{file}"
        new_path = os.path.join(download_path, new_name)
        shutil.move(old_path, new_path)
        saved_files.append(new_path)
    shutil.rmtree(temp_dir, ignore_errors=True)
    return saved_files, post

# Bot handler
@bot.message_handler(func=lambda msg: True)
def handle_url(message):
    url = message.text.strip()
    shortcode = extract_shortcode(url)
    if not shortcode:
        bot.reply_to(message, "❌ Invalid Instagram URL.")
        return

    bot.send_chat_action(message.chat.id, 'typing')

    try:
        files, post = download_post(shortcode)

        # Send cover image (without saving)
        cover_url = post.url
        r = requests.get(cover_url)
        if r.status_code == 200:
            bot.send_photo(message.chat.id, r.content, caption="🖼 Cover image")

        # Post details
        caption = post.caption or "No caption"
        details = f"""📄 <b>Post Details</b>
👤 <b>User:</b> @{post.owner_username}
❤️ <b>Likes:</b> {post.likes}
📝 <b>Caption:</b> {caption[:200]}{'...' if len(caption) > 200 else ''}
🔗 <a href="{url}">View on Instagram</a>"""
        bot.send_message(message.chat.id, details, parse_mode="HTML", disable_web_page_preview=False)

        # Send downloaded file(s)
        if files:
            for path in files:
                with open(path, 'rb') as media:
                    if path.endswith(".mp4"):
                        bot.send_video(message.chat.id, media)
                    else:
                        bot.send_photo(message.chat.id, media)
        else:
            bot.send_message(message.chat.id, "⚠️ Media not found.")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# Start bot
print("🤖 Bot running...")
bot.polling()
