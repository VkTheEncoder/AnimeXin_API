from flask import Flask, request, jsonify
from flask_cors import CORS 
import requests
from bs4 import BeautifulSoup
import base64
import os
import re
from urllib.parse import quote
from requests.exceptions import RequestException

app = Flask(__name__)
BASE_URL = "https://animexin.dev/"
CORS(app)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def make_request(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r
    except RequestException:
        return None

def safe_text(soup, selector, default=None):
    el = soup.select_one(selector)
    return el.text.strip() if el else default

def safe_attr(soup, selector, attr, default=None):
    el = soup.select_one(selector)
    return el.get(attr) if el and el.has_attr(attr) else default

@app.route('/')
def home():
    return jsonify({
        "api_name": "AnimeXin API",
        "description": "Search, info and videos (donghua or movie)",
        "endpoints": [
            {"path": "/search?query=…"},
            {"path": "/donghua/info?slug=…"},
            {"path": "/episode/videos?ep_slug=…"}
        ]
    })

@app.route('/search')
def search_donghua():
    q = request.args.get('query','').strip()
    if not q:
        return jsonify({"error":"query required"}),400

    url = f"{BASE_URL}?s={quote(q)}"
    r = make_request(url)
    if not r:
        return jsonify({"error":"animexin.dev unreachable"}),502

    soup = BeautifulSoup(r.text,'html.parser')
    results = []
    for art in soup.select('div.listupd article.bs'):
        a = art.find('a',href=True)
        if not a: continue
        u = a['href']
        slug = u.rstrip('/').split('/')[-1]
        results.append({
            "title":       a.get('title','').strip(),
            "slug":        slug,
            "url":         u,
            "image":       safe_attr(art,'img','src'),
            "status":      safe_text(art,'div.status'),
            "type":        safe_text(art,'div.typez'),
            "episode_status": safe_text(art,'div.bt span.epx'),
            "sub_status":     safe_text(art,'div.bt span.sb'),
            "is_hot":      bool(art.select_one('div.hotbadge'))
        })
    return jsonify({"query":q,"results":results})

@app.route('/donghua/info')
def get_donghua_info():
    slug = request.args.get('slug','').strip()
    if not slug:
        return jsonify({"error":"slug required"}),400

    # 1) try donghua
    url = f"{BASE_URL}donghua/{slug}"
    r = make_request(url)
    # 2) fallback to movie
    if not r or r.status_code>=400:
        url = f"{BASE_URL}movie/{slug}"
        r = make_request(url)
    if not r:
        return jsonify({"error":"animexin.dev unreachable"}),502

    soup = BeautifulSoup(r.text,'html.parser')

    # Basic titles
    title       = safe_text(soup,'h1.entry-title')
    alter_title = safe_text(soup,'span.alter')

    # Covers
    cover_main  = safe_attr(soup,'div.ime img','src')
    cover_thumb = safe_attr(soup,'div.thumb img','src')
    cover_images= {"main":cover_main,"thumb":cover_thumb}

    # Rating
    rating = {}
    if soup.select_one('div.rating-prc'):
        for field in ('ratingValue','bestRating','ratingCount'):
            sel = soup.select_one(f"div.rating-prc meta[itemprop={field}]")
            if sel and sel.has_attr('content'):
                rating[field] = sel['content']
        vis = soup.select_one('div.rtb span')
        if vis and vis.has_attr('style'):
            rating['visual'] = vis['style'].replace('width:','').replace('%','').strip()

    # Followers & Description
    followers   = safe_text(soup,'div.bmc')
    if followers:
        followers = followers.replace('Followed','').replace('people','').strip()
    description = safe_text(soup,'div.mindesc')

    # Info items
    info_items = {}
    for span in soup.select('div.info-content span'):
        b = span.find('b')
        if b:
            key = b.text.strip(':').strip()
            b.decompose()
            info_items[key] = span.text.strip()

    # Genres & Tags
    genres = [a.text for a in soup.select('div.genxed a')]
    tags   = [a.text for a in soup.select('div.bottom.tags a')]

    # Synopsis
    synopsis = {"english":None,"indonesian":None}
    synp = soup.select_one('div.synp')
    if synp:
        p_en = synp.find('p')
        p_id = synp.select_one('div.entry-content p')
        synopsis['english']    = p_en.text.strip() if p_en else None
        synopsis['indonesian']= p_id.text.strip() if p_id else None

    # Episodes
  # ————— Episodes (via AJAX) —————
    # 1) Try to extract the animeId by scanning every <script> for the AJAX URL
    anime_id = None
    for scr in soup.find_all("script"):
        text = (scr.string or scr.text or "")
        m = re.search(r"/ajax/v2/episode/list/(\d+)", text)
        if m:
            anime_id = m.group(1)
            break

    if not anime_id:
        # we couldn’t find the ID, so return a clean error instead of crashing
        return jsonify({
            "error": "Could not locate internal animeId for slug “%s”" % slug
        }), 500

    # 2) Call the real episode-list endpoint
    ajax = requests.get(
        f"{BASE_URL}ajax/v2/episode/list/{anime_id}",
        headers=HEADERS,
        timeout=10
    ).json()

    # 3) Build your episodes array
    episodes = []
    for e in ajax.get("episodesList", []):
        episodes.append({
            "episode_number": e.get("episodeNum"),
            "title":          "",  # animexin.dev doesn’t give you a title here
            "sub_type":       "",
            "release_date":   "",
            "url":            f"{BASE_URL}donghua/{e['episodeId']}",
            "ep_slug":        e["episodeId"]
        })
    # ——————————————————————————————

    # First/Last
    fl = {}
    lastend = soup.select_one('div.lastend')
    if lastend:
        ff = lastend.select_one('span.epcurfirst')
        ll = lastend.select('a')
        fl['first'] = {
            "episode": ff.text.strip() if ff else None,
            "url":     ll[0]['href'] if ll else None
        }
        fl['last'] = {
            "episode": safe_text(lastend,'span.epcurlast'),
            "url":     ll[1]['href'] if len(ll)>1 else None
        }

    return jsonify({
        "title":            title,
        "alternate_title":  alter_title,
        "description":      description,
        "cover_images":     cover_images,
        "rating":           rating,
        "followers":        followers,
        "info":             info_items,
        "genres":           genres,
        "tags":             tags,
        "synopsis":         synopsis,
        "first_last_episode": fl,
        "episodes":         episodes
    })

@app.route('/episode/videos')
def episode_videos():
    ep = request.args.get('ep_slug','').strip()
    if not ep:
        return jsonify({"error":"ep_slug required"}),400

    # 1) donghua
    url = f"{BASE_URL}donghua/{ep}"
    r = make_request(url)
    # 2) movie
    if not r or r.status_code>=400:
        url = f"{BASE_URL}movie/{ep}"
        r = make_request(url)
    if not r:
        return jsonify({"error":"animexin.dev unreachable"}),502

    soup = BeautifulSoup(r.text,'html.parser')
    sel  = soup.find('select',class_='mirror')
    if not sel:
        return jsonify({"error":"no servers"}),404

    video_servers = []
    for opt in sel.find_all('option'):
        val = opt.get('value')
        if not val: continue
        html = base64.b64decode(val).decode('utf-8')
        fsoup= BeautifulSoup(html,'html.parser')
        iframe = fsoup.find('iframe')
        src = iframe['src'] if iframe and iframe.has_attr('src') else None
        if src and src.startswith('//'):
            src = 'https:'+src
        video_servers.append({
            "server_name": opt.text.strip(),
            "video_url":   src
        })

    return jsonify({
        "episode_url": url,
        "available_servers": len(video_servers),
        "video_servers": video_servers
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8080)), debug=True)
