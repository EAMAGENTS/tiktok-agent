import os, json, requests, subprocess, tempfile, re
from dotenv import load_dotenv
import anthropic
from gtts import gTTS

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def get_trending_products():
    print("🔍 Produits trending...")
    return [
        {"name": "Lampe LED USB rechargeable", "price": "8.99€", "url": "https://fr.aliexpress.com/w/wholesale-led-lamp.html", "search": "led lamp desk"},
        {"name": "Montre connectée sport", "price": "15.99€", "url": "https://fr.aliexpress.com/w/wholesale-smart-watch.html", "search": "smartwatch fitness"},
        {"name": "Écouteurs sans fil Bluetooth", "price": "12.99€", "url": "https://fr.aliexpress.com/w/wholesale-earphones.html", "search": "wireless earbuds"},
        {"name": "Mini aspirateur de bureau USB", "price": "6.99€", "url": "https://fr.aliexpress.com/w/wholesale-vacuum.html", "search": "mini vacuum desk"},
        {"name": "Support téléphone voiture magnétique", "price": "4.99€", "url": "https://fr.aliexpress.com/w/wholesale-phone-holder.html", "search": "phone holder car"},
    ]

def select_product_and_write_script(products):
    print("🧠 Claude génère le script...")
    prompt = f"""Tu es expert TikTok viral. Produits disponibles :
{json.dumps(products, ensure_ascii=False)}

Choisis le meilleur et écris un script vidéo TikTok de 25 secondes en français.
Le script doit être TEXTE PUR à lire à voix haute, SANS indications scéniques, SANS parenthèses, SANS marqueurs de temps.
60 à 70 mots maximum.

Réponds UNIQUEMENT en JSON valide :
{{
  "product": {{"name": "...", "price": "...", "url": "...", "search": "..."}},
  "script": "texte pur, 60-70 mots",
  "tagline": "phrase choc de 5 mots maximum",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = re.sub(r'```json|```', '', response.content[0].text).strip()
    return json.loads(text)

def download_product_image(search_term, output_path):
    print(f"🖼️ Téléchargement image pour : {search_term}")
    if not UNSPLASH_KEY:
        return False
    try:
        r = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": search_term, "orientation": "portrait"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=10
        )
        if r.status_code == 200:
            img_url = r.json()["urls"]["regular"]
            img_data = requests.get(img_url, timeout=10).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"✅ Image téléchargée")
            return True
    except Exception as e:
        print(f"⚠️ Unsplash : {e}")
    return False

def generate_voiceover(script_text, output_path):
    print("🎙️ Voix off (gTTS)...")
    clean = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', script_text)
    clean = re.sub(r'\d+\s*[-–:]\s*\d+\s*s', '', clean)
    clean = clean.replace('"', '').strip()
    tts = gTTS(text=clean, lang='fr', slow=False)
    tts.save(output_path)
    if os.path.getsize(output_path) > 1000:
        print(f"✅ Audio OK")
        return True
    return False

def get_audio_duration(audio_path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 25.0

def create_video(image_path, audio_path, product_name, product_price, tagline, output_path):
    print("🎬 Montage vidéo dynamique...")
    duration = get_audio_duration(audio_path)
    print(f"   Durée : {duration:.1f}s")

    # Nettoyage texte pour FFmpeg drawtext
    safe_name = product_name.replace("'", "").replace(":", "").replace(",", "")[:30]
    safe_price = product_price.replace("'", "")
    safe_tagline = tagline.replace("'", "").replace(":", "").replace(",", "")[:40]

    # Filtre vidéo : zoom progressif + texte titre + texte prix + texte tagline
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"zoompan=z='min(zoom+0.0008,1.2)':d={int(duration*30)}:s=1080x1920:fps=30,"
        f"drawbox=x=0:y=200:w=1080:h=200:color=black@0.7:t=fill,"
        f"drawtext=text='{safe_name}':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=260,"
        f"drawbox=x=0:y=1500:w=1080:h=300:color=black@0.7:t=fill,"
        f"drawtext=text='{safe_tagline}':fontsize=56:fontcolor=yellow:x=(w-text_w)/2:y=1560,"
        f"drawtext=text='{safe_price}':fontsize=120:fontcolor=#FF3366:x=(w-text_w)/2:y=1650"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "30", "-i", image_path,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duration),
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.getsize(output_path) > 10000:
        print(f"✅ Vidéo OK ({os.path.getsize(output_path) // 1024} KB)")
        return True
    print(f"❌ FFmpeg : {result.stderr[-500:]}")
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
        print(f"✅ Tagline : {data['tagline']}")

        audio_path = f"{tmpdir}/voix.mp3"
        if not generate_voiceover(data["script"], audio_path):
            return

        image_path = f"{tmpdir}/img.jpg"
        if not download_product_image(product["search"], image_path):
            # Fallback fond coloré
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=0x1a1a2e:s=1080x1920:d=1",
                "-frames:v", "1", image_path
            ], capture_output=True)

        video_path = f"{tmpdir}/video.mp4"
        if not create_video(image_path, audio_path, product["name"], product["price"], data["tagline"], video_path):
            return

        url = upload_to_cloudinary(video_path)
        hashtags = " ".join(data["hashtags"])
        description = f"{data['tagline']} 🔥 Lien en bio ! {hashtags}"
        
        print("\n" + "="*40)
        print(f"✅ VIDÉO PROMO CRÉÉE")
        print(f"📦 {product['name']} — {product['price']}")
        print(f"🌐 {url}")
        print(f"📱 {description}")
        print("="*40)

if __name__ == "__main__":
    run_agent()