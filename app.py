from flask import Flask, request, jsonify
from flask_cors import CORS 
import requests
from bs4 import BeautifulSoup
import base64
import os
from urllib.parse import quote
from requests.exceptions import RequestException

app = Flask(__name__)
BASE_URL = "https://animexin.dev/"

CORS(app)

# Configure headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def decode_video_url(encoded_url):
    """Decode base64 encoded video URL"""
    try:
        decoded = base64.b64decode(encoded_url).decode('utf-8')
        return decoded
    except:
        return None

def make_request(url):
    """Helper to GET a URL with headers and return the response or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp
    except RequestException:
        return None

@app.route('/')
def home():
    """Welcome page with API instructions."""
    welcome = {
        "api_name": "AnimeXin API",
        "author": {
            "name": "RAHAT",
            "telegram": "@r4h4t_69",
            "contact": "https://t.me/r4h4t_69"
        },
        "description": "API service for AnimeXin website data",
        "endpoints": [
            {
                "name": "Search Donghua",
                "path": "/search",
                "method": "GET",
                "parameters": {"query": "Search term (required)"},
                "example": f"{request.base_url}search?query=Martial+Universe"
            },
            {
                "name": "Get Donghua/​Movie Info",
                "path": "/donghua/info",
                "method": "GET",
                "parameters": {"slug": "Donghua or Movie slug (required)"},
                "example": f"{request.base_url}donghua/info?slug=some-slug"
            },
            {
                "name": "Get Episode Videos",
                "path": "/episode/videos",
                "method": "GET",
                "parameters": {"ep_slug": "Episode slug (required)"},
                "example": f"{request.base_url}episode/videos?ep_slug=some-ep-slug"
            }
        ]
    }
    return jsonify(welcome)

@app.route('/search', methods=['GET'])
def search_donghua():
    """Search for Donghua by title."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    search_url = f"{BASE_URL}?s={quote(query)}"
    resp = make_request(search_url)
    if not resp:
        return jsonify({
            "error": "Failed to connect to animexin.dev"
        }), 502

    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []
        for article in soup.select('div.listupd article.bs'):
            link = article.find('a', href=True)
            if not link:
                continue
            title = link.get('title', '').strip()
            url = link['href']
            slug = url.rstrip('/').split('/')[-1]
            image = article.find('img', src=True)
            status = article.select_one('div.status')
            typez = article.select_one('div.typez')
            badge = bool(article.select_one('div.hotbadge'))
            bt = article.select_one('div.bt')
            episode_status = bt.select_one('span.epx').text.strip() if bt and bt.select_one('span.epx') else None
            sub_status = bt.select_one('span.sb').text.strip() if bt and bt.select_one('span.sb') else None

            results.append({
                "title": title,
                "slug": slug,
                "url": url,
                "image": image['src'] if image else None,
                "status": status.text.strip() if status else None,
                "type": typez.text.strip() if typez else None,
                "episode_status": episode_status,
                "sub_status": sub_status,
                "is_hot": badge
            })
        return jsonify({"query": query, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/donghua/info', methods=['GET'])
def get_donghua_info():
    """Get detailed info about a Donghua or Movie."""
    slug = request.args.get('slug', '').strip()
    if not slug:
        return jsonify({"error": "slug parameter is required"}), 400

    # 1) Try Donghua URL
    donghua_url = f"{BASE_URL}donghua/{slug}"
    resp = make_request(donghua_url)

    # 2) Fallback to Movie URL on error
    if not resp or resp.status_code >= 400:
        movie_url = f"{BASE_URL}movie/{slug}"
        resp = make_request(movie_url)

    if not resp:
        return jsonify({"error": "Failed to connect to animexin.dev"}), 502

    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Basic metadata
        title = soup.select_one('h1.entry-title').text.strip()
        alt = soup.select_one('span.alter')
        alter_title = alt.text.strip() if alt else None

        cover_main = soup.select_one('div.ime img')
        cover_thumb = soup.select_one('div.thumb img')
        cover_images = {
            "main": cover_main['src'] if cover_main else None,
            "thumb": cover_thumb['src'] if cover_thumb else None
        }

        # Rating
        rdiv = soup.select_one('div.rating-prc')
        rating_info = {}
        if rdiv:
            rating_info = {
                "value": rdiv.select_one('meta[itemprop=ratingValue]')['content'],
                "best": rdiv.select_one('meta[itemprop=bestRating]')['content'],
                "count": rdiv.select_one('meta[itemprop=ratingCount]')['content'],
                "visual": soup.select_one('div.rtb span')['style'].replace('width:', '').replace('%','').strip()
            }

        followers_div = soup.select_one('div.bmc')
        followers = None
        if followers_div:
            followers = followers_div.text.replace('Followed','').replace('people','').strip()

        description_div = soup.select_one('div.mindesc')
        description = description_div.text.strip() if description_div else None

        info_items = {}
        for span in soup.select('div.info-content span'):
            b = span.find('b')
            if b:
                key = b.text.strip(':').strip()
                b.decompose()
                info_items[key] = span.text.strip()

        genres = [a.text for a in soup.select('div.genxed a')]
        tags   = [a.text for a in soup.select('div.bottom.tags a')]

        synopsis_div = soup.select_one('div.synp')
        synopsis = {"english": None, "indonesian": None}
        if synopsis_div:
            p_en = synopsis_div.find('p')
            p_id = synopsis_div.select_one('div.entry-content p')
            synopsis["english"] = p_en.text.strip() if p_en else None
            synopsis["indonesian"] = p_id.text.strip() if p_id else None

        # Episodes
        episodes = []
        for li in soup.select('div.eplister li'):
            a = li.find('a', href=True)
            if not a:
                continue
            num = li.select_one('div.epl-num').text.strip()
            ttl = li.select_one('div.epl-title').text.strip()
            sub = li.select_one('div.epl-sub').text.strip()
            dt  = li.select_one('div.epl-date').text.strip()
            ep_slug = a['href'].rstrip('/').split('/')[-1]
            episodes.append({
                "episode_number": num,
                "title": ttl,
                "sub_type": sub,
                "release_date": dt,
                "url": a['href'],
                "ep_slug": ep_slug
            })

        # First/Last episodes
        fl = {}
        lastend = soup.select_one('div.lastend')
        if lastend:
            ff = lastend.select_one('span.epcurfirst')
            fl['first'] = {"episode": ff.text.strip() if ff else None,
                           "url": lastend.find('a')['href'] if lastend.find('a') else None}
            ll = lastend.select('a')
            fl['last']  = {"episode": lastend.select_one('span.epcurlast').text.strip() if lastend.select_one('span.epcurlast') else None,
                           "url": ll[1]['href'] if len(ll)>1 else None}

        return jsonify({
            "title": title,
            "alternate_title": alter_title,
            "description": description,
            "cover_images": cover_images,
            "rating": rating_info,
            "followers": followers,
            "info": info_items,
            "genres": genres,
            "tags": tags,
            "synopsis": synopsis,
            "first_last_episode": fl,
            "episodes": episodes
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/episode/videos', methods=['GET'])
def get_episode_videos():
    """Get video URLs for an episode, with donghua/movie fallback."""
    ep_slug = request.args.get('ep_slug', '').strip()
    if not ep_slug:
        return jsonify({"error": "ep_slug parameter is required"}), 400

    # 1) Try donghua episode URL
    donghua_ep = f"{BASE_URL}donghua/{ep_slug}"
    resp = make_request(donghua_ep)

    # 2) Fallback to movie episode URL
    if not resp or resp.status_code >= 400:
        movie_ep = f"{BASE_URL}movie/{ep_slug}"
        resp = make_request(movie_ep)

    if not resp:
        return jsonify({"error": "Failed to connect to animexin.dev"}), 502

    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
        select = soup.find('select', class_='mirror')
        if not select:
            return jsonify({"error": "No video servers found"}), 404

        video_servers = []
        for opt in select.find_all('option'):
            val = opt.get('value')
            if not val:
                continue
            html = decode_video_url(val)
            # extract clean iframe src
            vsoup = BeautifulSoup(html or "", 'html.parser')
            iframe = vsoup.find('iframe')
            src = iframe['src'] if iframe and iframe.get('src') else None
            if src and src.startswith('//'):
                src = 'https:' + src
            video_servers.append({
                "server_name": opt.text.strip(),
                "video_url": src
            })

        # determine which URL we actually fetched
        ep_url = donghua_ep if resp.url.startswith(donghua_ep) else movie_ep

        return jsonify({
            "episode_url": ep_url,
            "available_servers": len(video_servers),
            "video_servers": video_servers
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_video_url(html):
    """Extract clean video URL from embed HTML (fallback)."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, 'html.parser')
        ifr = soup.find('iframe')
        if ifr and ifr.get('src'):
            src = ifr['src']
            return src if not src.startswith('//') else 'https:' + src
    except:
        pass
    return None

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
