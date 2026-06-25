import os, json, requests, subprocess, tempfile, re, random
import unicodedata
from dotenv import load_dotenv
import anthropic
from gtts import gTTS

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


def strip_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


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

Choisis le meilleur produit. Écris un script TikTok de 20 secondes en français, ULTRA viral.
RÈGLES :
- HOOK choc dès le 1er mot
- 50 à 60 mots maximum
- Phrases courtes
- Pas d'indications scéniques, juste le texte à lire

Réponds en JSON valide :
{{
  "product": {{"name": "...", "price": "...", "url": "...", "search": "..."}},
  "hook": "phrase choc 3-5 mots",
  "script": "texte pur, 50-60 mots",
  "tagline": "CTA final 4-6 mots",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = re.sub(r'```json|```', '', response.content[0].text).strip()
    return json.loads(text)


def generate_voiceover(script_text, output_path):
    print("🎙️ Voix off...")
    clean = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', script_text)
    clean = clean.replace('"', '').strip()
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
            headers={"Authorization": PEXELS_KEY},
            timeout=15
        )
        videos = r.json().get("videos", [])
        if not videos:
            return []
        random.shuffle(videos)
        paths = []
        for i, video in enumerate(videos[:count]):
            files = sorted(video["video_files"], key=lambda f: f.get("width", 0))
            best = next((f for f in files if f.get("width", 0) >= 720), files[-1] if files else None)
            if not best:
                continue
            video_data = requests.get(best["link"], timeout=20).content
            path = f"{output_dir}/clip_{i}.mp4"
            with open(path, "wb") as f:
                f.write(video_data)
            paths.append(path)
            print(f"   ✅ Clip {i+1}")
        return paths
    except Exception as e:
        print(f"⚠️ Pexels : {e}")
        return []


def create_video(clips, audio_path, hook, product_name, product_price, tagline, output_path):
    print("🎬 Montage vidéo...")
    duration = get_audio_duration(audio_path)
    print(f"   Durée : {duration:.1f}s")

    if not clips:
        return False

    clip_duration = duration / len(clips)
    safe_hook = strip_accents(re.sub(r"[':,!?.]", "", hook))[:30]
    safe_name = strip_accents(re.sub(r"[':,!?.]", "", product_name))[:28]
    safe_tagline = strip_accents(re.sub(r"[':,!?.]", "", tagline))[:35]
    safe_price = strip_accents(product_price.replace("'", ""))

    tmpdir = os.path.dirname(clips[0])
    prepared = []
    for i, clip in enumerate(clips):
        out = f"{tmpdir}/prep_{i}.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-t", str(clip_duration),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-an", "-r", "30",
            out
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
            prepared.append(out)
            print(f"   ✅ Clip {i+1} prep")

    if not prepared:
        return False

    concat_file = f"{tmpdir}/concat.txt"
    with open(concat_file, "w") as f:
        for p in prepared:
            f.write(f"file '{p}'\n")

    concat_out = f"{tmpdir}/concat.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c", "copy", concat_out
    ], capture_output=True)

    if not os.path.exists(concat_out) or os.path.getsize(concat_out) < 1000:
        return False
    print("   ✅ Concat OK")

    vf = (
        f"drawbox=enable='between(t,0,3)':x=0:y=600:w=1080:h=400:color=black@0.75:t=fill,"
        f"drawtext=enable='between(t,0,3)':text='{safe_hook}':fontsize=90:fontcolor=yellow:x=(w-text_w)/2:y=720,"
        f"drawbox=enable='gte(t,3)':x=0:y=150:w=1080:h=180:color=black@0.7:t=fill,"
        f"drawtext=enable='gte(t,3)':text='{safe_name}':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=210,"
        f"drawbox=enable='gte(t,{duration*0.6:.1f})':x=0:y=1450:w=1080:h=350:color=black@0.8:t=fill,"
        f"drawtext=enable='gte(t,{duration*0.6:.1f})':text='{safe_tagline}':fontsize=55:fontcolor=yellow:x=(w-text_w)/2:y=1500,"
        f"drawtext=enable='gte(t,{duration*0.6:.1f})':text='{safe_price}':fontsize=130:fontcolor=#FF3366:x=(w-text_w)/2:y=1600"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", concat_out,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v", "-map", "1:a",
        "-t", str(duration),
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"✅ Vidéo OK ({os.path.getsize(output_path) // 1024} KB)")
        return True
    print("❌ FFmpeg erreur complète :")
    print(result.stderr)
    return False


def upload_to_cloudinary(video_path):
    print("☁️ Upload Cloudinary...")
    try:
        import cloudinary
        import cloudinary.uploader
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
            print("⛔ Audio échec")
            return

        clips = download_pexels_videos(product["search"], 4, tmpdir)
        if not clips:
            print("⛔ Pas de B-rolls")
            return

        video_path = f"{tmpdir}/video.mp4"
        if not create_video(clips, audio_path, data["hook"], product["name"], product["price"], data["tagline"], video_path):
            print("⛔ Montage échec")
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