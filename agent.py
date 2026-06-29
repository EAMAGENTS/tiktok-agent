import os, json, requests, subprocess, tempfile, re, random, hashlib, hmac, time
from datetime import datetime
from dotenv import load_dotenv
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
import anthropic

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
ALI_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
ALI_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ─── ALIEXPRESS API ────────────────────────────────────────────────────────────

def ali_sign(params, secret):
    """Génère la signature HMAC-SHA256 pour l'API AliExpress"""
    sorted_params = sorted(params.items())
    base = secret + "".join(f"{k}{v}" for k, v in sorted_params) + secret
    return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


def ali_request(method, extra_params):
    """Appel générique à l'API AliExpress"""
    url = "https://api-sg.aliexpress.com/sync"
    params = {
        "app_key": ALI_APP_KEY,
        "method": method,
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "sha256",
        "format": "json",
        "v": "2.0",
    }
    params.update(extra_params)
    params["sign"] = ali_sign(params, ALI_APP_SECRET)
    try:
        r = requests.post(url, data=params, timeout=15)
        return r.json()
    except Exception as e:
        print(f"⚠️ AliExpress API : {e}")
        return {}


def get_trending_products_aliexpress():
    """Récupère les produits trending via l'API AliExpress"""
    print("🔍 Recherche produits trending AliExpress...")
    result = ali_request("aliexpress.affiliate.hotproduct.query", {
        "app_signature": "",
        "category_id": "",
        "delivery_days": "7",
        "fields": "product_id,product_title,target_sale_price,product_main_image_url,product_video_url,evaluate_rate,thirty_day_orders_count,commission_rate,sale_price,product_detail_url",
        "keywords": "",
        "max_sale_price": "",
        "min_sale_price": "",
        "page_no": "1",
        "page_size": "20",
        "platform_product_type": "ALL",
        "ship_to_country": "FR",
        "sort": "LAST_VOLUME_DESC",
        "target_currency": "EUR",
        "target_language": "FR",
        "tracking_id": "default",
    })

    products = []
    try:
        items = result.get("aliexpress_affiliate_hotproduct_query_response", {}) \
                      .get("resp_result", {}) \
                      .get("result", {}) \
                      .get("products", {}) \
                      .get("product", [])
        for item in items:
            commission = float(item.get("commission_rate", "0").replace("%", ""))
            orders = int(item.get("thirty_day_orders_count", 0))
            rating = float(item.get("evaluate_rate", "0").replace("%", ""))
            # Filtre : commission > 5%, commandes > 100, note > 90%
            if commission >= 5 and orders >= 100 and rating >= 90:
                products.append({
                    "id": str(item.get("product_id", "")),
                    "name": item.get("product_title", "")[:80],
                    "price": f"{item.get('target_sale_price', '?')} EUR",
                    "commission": f"{commission}%",
                    "orders": orders,
                    "rating": f"{rating}%",
                    "image_url": item.get("product_main_image_url", ""),
                    "video_url": item.get("product_video_url", ""),
                    "url": item.get("product_detail_url", ""),
                    "search": item.get("product_title", "")[:30],
                })
        print(f"✅ {len(products)} produits qualifiés trouvés")
    except Exception as e:
        print(f"⚠️ Parsing AliExpress : {e}")

    # Fallback si API ne retourne rien
    if not products:
        print("⚠️ Fallback produits hardcodés")
        products = [
            {"id": "1", "name": "Lampe LED USB rechargeable portable", "price": "8.99 EUR", "commission": "7%", "orders": 520, "rating": "96%", "image_url": "", "video_url": "", "url": "https://fr.aliexpress.com", "search": "led lamp"},
            {"id": "2", "name": "Montre connectée sport waterproof", "price": "15.99 EUR", "commission": "8%", "orders": 340, "rating": "94%", "image_url": "", "video_url": "", "url": "https://fr.aliexpress.com", "search": "smartwatch"},
            {"id": "3", "name": "Écouteurs sans fil Bluetooth 5.0", "price": "12.99 EUR", "commission": "6%", "orders": 280, "rating": "92%", "image_url": "", "video_url": "", "url": "https://fr.aliexpress.com", "search": "wireless earbuds"},
        ]
    return products


def get_affiliate_link(product_url, product_id):
    """Génère un lien affilié tracké"""
    print("🔗 Génération lien affilié...")
    result = ali_request("aliexpress.affiliate.link.generate", {
        "promotion_link_type": "0",
        "source_values": product_url,
        "tracking_id": "default",
    })
    try:
        link = result.get("aliexpress_affiliate_link_generate_response", {}) \
                     .get("resp_result", {}) \
                     .get("result", {}) \
                     .get("promotion_links", {}) \
                     .get("promotion_link", [{}])[0] \
                     .get("promotion_link", "")
        if link:
            print(f"✅ Lien affilié généré")
            return link
    except Exception as e:
        print(f"⚠️ Lien affilié : {e}")
    return product_url


# ─── SCRIPT IA ────────────────────────────────────────────────────────────────

def select_product_and_write_script(products):
    print("🧠 Claude sélectionne et écrit le script...")
    prompt = f"""Tu es expert en marketing TikTok et affiliation. Voici des produits AliExpress avec leurs vraies stats :
{json.dumps(products, ensure_ascii=False, indent=2)}

MISSION :
1. Choisis le produit avec le meilleur potentiel viral (prix attractif + fort volume de commandes + bonne commission)
2. Écris un script voix off de 25 secondes en français, naturel et convaincant

RÈGLES STRICTES pour TikTok :
- Commence par une question ou un constat du quotidien (PAS de "secret", "gratuit", "hack", "miracle", "lien bio")
- Phrases courtes, ton naturel comme si tu parlais à un ami
- Mentionne le prix RÉEL
- Termine par une phrase simple du type "je te mets le lien en description"
- 55 à 65 mots maximum
- TEXTE PUR uniquement, aucune indication scénique

Réponds en JSON valide uniquement :
{{
  "product": {{"id": "...", "name": "...", "price": "...", "commission": "...", "image_url": "...", "video_url": "...", "url": "...", "search": "..."}},
  "hook": "question ou constat accrocheur, 5-7 mots",
  "script": "texte pur 55-65 mots, naturel",
  "tagline": "phrase finale simple 5-7 mots",
  "angle": "angle marketing choisi en 1 phrase",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


# ─── VOIX OFF ─────────────────────────────────────────────────────────────────

def generate_voiceover(script_text, output_path):
    print("🎙️ Génération voix off (gTTS)...")
    clean = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', script_text).replace('"', '').strip()
    tts = gTTS(text=clean, lang='fr', slow=False)
    tts.save(output_path)
    size = os.path.getsize(output_path)
    if size > 1000:
        print(f"✅ Audio OK ({size // 1024} KB)")
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


# ─── VISUELS ──────────────────────────────────────────────────────────────────

def download_media(url, output_path, timeout=20):
    """Télécharge un fichier depuis une URL"""
    try:
        r = requests.get(url, timeout=timeout, stream=True)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"⚠️ Download : {e}")
    return False


def get_pexels_clip(search_term, output_path):
    """Télécharge un clip Pexels portrait HD"""
    if not PEXELS_KEY:
        return False
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": search_term, "per_page": 10, "orientation": "portrait"},
            headers={"Authorization": PEXELS_KEY}, timeout=15
        )
        videos = r.json().get("videos", [])
        if not videos:
            return False
        video = random.choice(videos[:5])
        files = sorted(video["video_files"], key=lambda f: f.get("width", 0))
        # Prend le fichier le plus léger >= 720px de large
        best = next((f for f in files if 720 <= f.get("width", 0) <= 1280), files[0] if files else None)
        if not best:
            return False
        return download_media(best["link"], output_path, timeout=30)
    except Exception as e:
        print(f"⚠️ Pexels : {e}")
        return False


# ─── MONTAGE VIDÉO ────────────────────────────────────────────────────────────

def find_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def make_text_image(text, font_size, color_rgba, width, output_path):
    """Crée une image PNG avec texte centré sur fond transparent"""
    font_path = find_font()
    if not font_path:
        return False
    try:
        font = ImageFont.truetype(font_path, font_size)
        # Mesure
        tmp = Image.new("RGBA", (width, font_size * 4), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tmp)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad = 30
        # Image finale
        img = Image.new("RGBA", (width, th + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        bx = (width - tw - pad * 2) // 2
        draw.rectangle([bx, 0, bx + tw + pad * 2, th + pad * 2], fill=(0, 0, 0, 180))
        draw.text(((width - tw) // 2 - bbox[0], pad - bbox[1]), text, font=font, fill=color_rgba)
        img.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"⚠️ PIL text : {e}")
        return False


def create_video(source_video, source_image, audio_path, hook, product_name, product_price, tagline, output_path):
    """Assemble la vidéo finale avec overlays PIL"""
    print("🎬 Montage vidéo...")
    duration = get_audio_duration(audio_path)
    print(f"   Durée audio : {duration:.1f}s")
    tmpdir = os.path.dirname(audio_path)

    # Crée les overlays texte avec PIL
    hook_png = f"{tmpdir}/hook.png"
    name_png = f"{tmpdir}/name.png"
    price_png = f"{tmpdir}/price.png"
    tag_png = f"{tmpdir}/tagline.png"

    make_text_image(hook, 75, (255, 235, 59, 255), 1080, hook_png)
    make_text_image(product_name, 52, (255, 255, 255, 255), 1080, name_png)
    make_text_image(product_price, 100, (255, 51, 102, 255), 1080, price_png)
    make_text_image(tagline, 48, (255, 235, 59, 255), 1080, tag_png)
    print("   ✅ Overlays PIL créés")

    # Source vidéo : vidéo produit vendeur OU clip Pexels OU image produit
    if source_video and os.path.exists(source_video):
        print("   📹 Source : vidéo vendeur")
        base_input = ["-stream_loop", "-1", "-i", source_video]
        base_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
        has_audio_in_source = False
    elif source_image and os.path.exists(source_image):
        print("   🖼️ Source : image produit")
        base_input = ["-loop", "1", "-i", source_image]
        base_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
        has_audio_in_source = False
    else:
        print("   ⬛ Source : fond noir (fallback)")
        base_input = ["-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r=30"]
        base_filter = "null"
        has_audio_in_source = False

    mid = f"{duration * 0.55:.1f}"
    filter_complex = (
        f"[0:v]{base_filter}[base];"
        f"[base][1:v]overlay=0:700:enable='between(t,0,3)'[v1];"
        f"[v1][2:v]overlay=0:120:enable='gte(t,3)'[v2];"
        f"[v2][3:v]overlay=0:1550:enable='gte(t,{mid})'[v3];"
        f"[v3][4:v]overlay=0:1680:enable='gte(t,{mid})'[vout]"
    )

    audio_index = 5
    cmd = [
        "ffmpeg", "-y",
        *base_input,
        "-i", hook_png,
        "-i", name_png,
        "-i", price_png,
        "-i", tag_png,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", f"{audio_index}:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duration),
        "-movflags", "+faststart",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"✅ Vidéo OK ({os.path.getsize(output_path) // 1024} KB)")
            return True
        print(f"❌ FFmpeg erreur :\n{result.stderr[-1000:]}")
        return False
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg timeout 120s")
        return False


# ─── CLOUDINARY ───────────────────────────────────────────────────────────────

def upload_to_cloudinary(video_path):
    print("☁️ Upload Cloudinary...")
    try:
        import cloudinary, cloudinary.uploader
        cloudinary.config(url=os.getenv("CLOUDINARY_URL"))
        upload = cloudinary.uploader.upload_large(
            video_path, resource_type="video",
            folder="tiktok-agent", chunk_size=6000000
        )
        url = upload["secure_url"]
        print(f"✅ En ligne : {url}")
        return url
    except Exception as e:
        print(f"❌ Cloudinary : {e}")
        return None


# ─── KIT DU MATIN (fallback sans vidéo) ──────────────────────────────────────

def save_kit(data, affiliate_link, output_dir="/tmp"):
    """Sauvegarde le kit texte du matin"""
    product = data["product"]
    hashtags = " ".join(data["hashtags"])
    description = f"{data['tagline']} 🔥 #Partenariat #Affiliation {hashtags}"
    kit = f"""
╔══════════════════════════════════════════════╗
   KIT TIKTOK DU MATIN — {datetime.now().strftime('%d/%m/%Y %H:%M')}
╚══════════════════════════════════════════════╝

📦 PRODUIT : {product['name']}
💰 PRIX : {product['price']} | COMMISSION : {product['commission']}
⭐ COMMANDES 30J : {product.get('orders', '?')}

🎯 ANGLE : {data['angle']}

🎙️ SCRIPT À LIRE (voix off) :
─────────────────────────────
{data['script']}
─────────────────────────────

🔗 LIEN AFFILIÉ : {affiliate_link}

📱 DESCRIPTION TIKTOK (copie-colle) :
{description}

✅ CHECKLIST AVANT DE POSTER :
  □ Activer "Paid Partnership" dans TikTok
  □ Coller le lien affilié en description
  □ Vérifier les hashtags
"""
    kit_path = f"{output_dir}/kit_tiktok.txt"
    with open(kit_path, "w", encoding="utf-8") as f:
        f.write(kit)
    print(kit)
    return kit_path


# ─── PIPELINE PRINCIPAL ───────────────────────────────────────────────────────

def run_agent():
    print("\n🚀 AGENT TIKTOK — " + datetime.now().strftime('%d/%m/%Y %H:%M'))
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:

        # 1. Produits AliExpress
        products = get_trending_products_aliexpress()
        if not products:
            print("⛔ Pas de produits")
            return

        # 2. Sélection + script Claude
        data = select_product_and_write_script(products)
        product = data["product"]
        print(f"✅ Produit : {product['name']}")
        print(f"✅ Commission : {product['commission']}")
        print(f"✅ Hook : {data['hook']}")

        # 3. Lien affilié tracké
        affiliate_link = get_affiliate_link(product["url"], product["id"])

        # 4. Voix off gTTS (remplacée par ta voix réelle avant de poster)
        audio_path = f"{tmpdir}/voix.mp3"
        audio_ok = generate_voiceover(data["script"], audio_path)

        # 5. Visuels — vidéo vendeur en priorité, image produit en fallback, Pexels sinon
        source_video = None
        source_image = None

        if product.get("video_url"):
            print("📹 Téléchargement vidéo vendeur...")
            vid_path = f"{tmpdir}/product_video.mp4"
            if download_media(product["video_url"], vid_path):
                source_video = vid_path
                print("✅ Vidéo vendeur téléchargée")

        if not source_video and product.get("image_url"):
            print("🖼️ Téléchargement image vendeur...")
            img_path = f"{tmpdir}/product_image.jpg"
            if download_media(product["image_url"], img_path):
                source_image = img_path
                print("✅ Image vendeur téléchargée")

        if not source_video and not source_image:
            print("📹 Fallback Pexels...")
            pex_path = f"{tmpdir}/pexels.mp4"
            if get_pexels_clip(product["search"], pex_path):
                source_video = pex_path
                print("✅ Clip Pexels téléchargé")

        # 6. Montage vidéo
        video_url = None
        if audio_ok:
            video_path = f"{tmpdir}/video.mp4"
            video_ok = create_video(
                source_video, source_image, audio_path,
                data["hook"], product["name"], product["price"],
                data["tagline"], video_path
            )
            if video_ok:
                video_url = upload_to_cloudinary(video_path)

        # 7. Kit du matin (toujours généré, même si vidéo échoue)
        save_kit(data, affiliate_link, tmpdir)

        # 8. Résumé final
        print("\n" + "=" * 50)
        print("✅ CYCLE COMPLET")
        if video_url:
            print(f"🎬 VIDÉO : {video_url}")
        else:
            print("⚠️ Vidéo non générée — utilise le kit texte ci-dessus")
        print(f"🔗 LIEN : {affiliate_link}")
        print("=" * 50)


if __name__ == "__main__":
    run_agent()