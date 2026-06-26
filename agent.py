import os, json, requests, subprocess, tempfile, re, random
import unicodedata
from dotenv import load_dotenv
import anthropic
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


def get_trending_products():
    print("🔍 Produits trending...")
    return [
        {"name": "Lampe LED USB rechargeable", "price": "8.99€", "url": "https://fr.aliexpress.com/w/wholesale-led-lamp.html", "search": "desk lamp"},
        {"name": "Montre connectée sport", "price": "15.99€", "url": "https://fr.aliexpress.com/w/wholesale-smart-watch.html", "search": "smartwatch fitness"},
        {"name": "Écouteurs sans fil Bluetooth", "price": "12.99€", "url": "https://fr.aliexpress.com/w/wholesale-earphones.html", "search": "wireless earbuds"},
        {"name": "Mini aspirateur de bureau USB", "price": "6.99€", "url": "https://fr.aliexpress.com/w/wholesale-vacuum.html", "search": "vacuum cleaner"},
        {"name": "Support téléphone voiture", "price": "4.99€", "url": "https://fr.aliexpress.com/w/wholesale-phone-holder.html", "search": "phone car holder"},
    ]


def select_product_and_write_script(products):
    print("🧠 Claude génère script...")
    prompt = f"""Tu es expert TikTok viral. Produits :
{json.dumps(products, ensure_ascii=False)}

Choisis le meilleur et écris un script TikTok de 20 secondes en français, ULTRA viral.
RÈGLES : HOOK choc, 50-60 mots maximum, phrases courtes, juste le texte à lire.

JSON valide :
{{
  "product": {{"name": "...", "price": "...", "url": "...", "search": "..."}},
  "hook": "phrase choc 3-5 mots",
  "script": "texte pur 50-60 mots",
  "tagline": "CTA final 4-6 mots",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def generate_voiceover(script_text, output_path):
    print("🎙️ Voix off...")
    clean = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', script_text).replace('"', '').strip()
    tts = gTTS(text=clean, lang='fr', slow=False)
    tts.save(output_path)
    return os.path.getsize(output_path) > 1000


def get_audio_duration(audio_path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 20.0


def download_pexels_videos(search_term, count, output_dir):
    print(f"📹 B-rolls Pexels : {search_term} (×{count})")
    if not PEXELS_KEY:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": search_term, "per_page": 15, "orientation": "portrait"},
            headers={"Authorization": PEXELS_KEY}, timeout=15
        )
        videos = r.json().get("videos", [])
        if not videos:
            return []
        random.shuffle(videos)
        paths = []
        for i, video in enumerate(videos[:count]):
            files = sorted(video["video_files"], key=lambda f: f.get("width", 0))
            best = next((f for f in files if f.get("width", 0) >= 720 and f.get("width", 0) <= 1920), files[0] if files else None)
            if not best:
                continue
            video_data = requests.get(best["link"], timeout=30).content
            path = f"{output_dir}/clip_{i}.mp4"
            with open(path, "wb") as f:
                f.write(video_data)
            paths.append(path)
            print(f"   ✅ Clip {i+1} ({len(video_data)//1024} KB)")
        return paths
    except Exception as e:
        print(f"⚠️ Pexels : {e}")
        return []


def find_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def create_text_overlay(text, font_size, color, width, output_path, bg_alpha=180):
    font_path = find_font()
    if not font_path:
        return False
    img = Image.new("RGBA", (width, font_size * 3), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x, pad_y = 40, 25
    box_w = text_w + pad_x * 2
    box_h = text_h + pad_y * 2
    img = Image.new("RGBA", (width, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    box_x = (width - box_w) // 2
    draw.rectangle([box_x, 0, box_x + box_w, box_h], fill=(0, 0, 0, bg_alpha))
    text_x = (width - text_w) // 2 - bbox[0]
    text_y = pad_y - bbox[1]
    draw.text((text_x, text_y), text, font=font, fill=color)
    img.save(output_path, "PNG")
    return True


def create_video(clips, audio_path, hook, product_name, product_price, tagline, output_path):
    print("🎬 Montage vidéo...")
    duration = get_audio_duration(audio_path)
    print(f"   Durée : {duration:.1f}s")
    if not clips:
        return False

    tmpdir = os.path.dirname(clips[0])

    hook_png = f"{tmpdir}/hook.png"
    name_png = f"{tmpdir}/name.png"
    tagline_png = f"{tmpdir}/tagline.png"
    price_png = f"{tmpdir}/price.png"

    create_text_overlay(hook, 90, (255, 235, 59, 255), 1080, hook_png)
    create_text_overlay(product_name, 60, (255, 255, 255, 255), 1080, name_png)
    create_text_overlay(tagline, 55, (255, 235, 59, 255), 1080, tagline_png)
    create_text_overlay(product_price, 130, (255, 51, 102, 255), 1080, price_png)
    print("   ✅ Overlays texte créés")

    clip_duration = duration / len(clips)
    prepared = []
    for i, clip in enumerate(clips):
        out = f"{tmpdir}/prep_{i}.mp4"
        print(f"   ⏳ Clip {i+1} : préparation...")
        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-t", str(clip_duration),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-an", "-r", "30", out
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
                prepared.append(out)
                print(f"   ✅ Clip {i+1} prep ({os.path.getsize(out)//1024} KB)")
            else:
                print(f"   ❌ Clip {i+1} échec")
        except subprocess.TimeoutExpired:
            print(f"   ⏱️ Clip {i+1} timeout 60s")
            continue

    if not prepared:
        return False

    concat_file = f"{tmpdir}/concat.txt"
    with open(concat_file, "w") as f:
        loops = max(1, int(duration / (clip_duration * len(prepared))) + 2)
        for _ in range(loops):
            for p in prepared:
                f.write(f"file '{p}'\n")

    concat_out = f"{tmpdir}/concat.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-t", str(duration + 1), "-c", "copy", concat_out
        ], capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("   ⏱️ Concat timeout")
        return False

    if not os.path.exists(concat_out):
        return False
    print("   ✅ Concat OK")

    middle_time = duration * 0.6
    cmd = [
        "ffmpeg", "-y",
        "-i", concat_out,
        "-i", hook_png,
        "-i", name_png,
        "-i", tagline_png,
        "-i", price_png,
        "-i", audio_path,
        "-filter_complex",
        f"[0:v][1:v]overlay=0:700:enable='between(t,0,3)'[v1];"
        f"[v1][2:v]overlay=0:180:enable='gte(t,3)'[v2];"
        f"[v2][3:v]overlay=0:1450:enable='gte(t,{middle_time:.1f})'[v3];"
        f"[v3][4:v]overlay=0:1600:enable='gte(t,{middle_time:.1f})'[vout]",
        "-map", "[vout]", "-map", "5:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duration), "-movflags", "+faststart",
        output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("   ⏱️ Montage final timeout 180s")
        return False

    if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"✅ Vidéo OK ({os.path.getsize(output_path) // 1024} KB)")
        return True
    print("❌ FFmpeg erreur :")
    print(result.stderr[-2000:])
    return False


def upload_to_cloudinary(video_path):
    print("☁️ Upload Cloudinary...")
    try:
        import cloudinary, cloudinary.uploader
        cloudinary.config(url=os.getenv("CLOUDINARY_URL"))
        upload = cloudinary.uploader.upload_large(
            video_path, resource_type="video",
            folder="tiktok-agent", chunk_size=6000000
        )
        return upload["secure_url"]
    except Exception as e:
        print(f"❌ Cloudinary : {e}")
        return None


def run_agent():
    print("\n🚀 AGENT TIKTOK PROMO\n" + "="*40)
    with tempfile.TemporaryDirectory() as tmpdir:
        products = get_trending_products()
        data = select_product_and_write_script(products)
        product = data["product"]
        print(f"✅ Produit : {product['name']}")
        print(f"✅ Hook : {data['hook']}")

        audio_path = f"{tmpdir}/voix.mp3"
        if not generate_voiceover(data["script"], audio_path):
            return

        clips = download_pexels_videos(product["search"], 4, tmpdir)
        if not clips:
            return

        video_path = f"{tmpdir}/video.mp4"
        if not create_video(clips, audio_path, data["hook"], product["name"], product["price"], data["tagline"], video_path):
            return

        url = upload_to_cloudinary(video_path)
        hashtags = " ".join(data["hashtags"])
        description = f"{data['tagline']} 🔥 Lien en bio ! {hashtags}"

        print("\n" + "="*40)
        print("✅ VIDÉO PROMO CRÉÉE")
        print(f"📦 {product['name']} — {product['price']}")
        print(f"🌐 {url}")
        print(f"📱 {description}")
        print("="*40)


if __name__ == "__main__":
    run_agent()