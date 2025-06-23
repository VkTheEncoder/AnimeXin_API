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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def make_request(url):
    """GET helper with headers + timeout."""
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
            "/search?query=…",
            "/donghua/info?slug=…",
            "/episode/videos?ep_slug=…"
        ]
    })

@app.route('/search')
def search_donghua():
    """Search for Donghua by title (safe, never 500)."""
    q = request.args.get('query','').strip()
    if not q:
        return jsonify({"error":"query parameter is required"}), 400

    try:
        # 1) fetch the search page
        url = f"{BASE_URL}?s={quote(q)}"
        r = make_request(url)
        if not r:
            # API unreachable → treat as empty
            return jsonify({"query":q,"results":[]})

        soup = BeautifulSoup(r.text, 'lxml')
        results = []
        for art in soup.select('div.listupd article.bs'):
            a = art.find('a', href=True)
            if not a:
                continue
            u = a['href']
            slug = u.rstrip('/').split('/')[-1]
            results.append({
                "title":           a.get('title','').strip(),
                "slug":            slug,
                "url":             u,
                "image":           safe_attr(art,'img','src'),
                "status":          safe_text(art,'div.status'),
                "type":            safe_text(art,'div.typez'),
                "episode_status":  safe_text(art,'div.bt span.epx'),
                "sub_status":      safe_text(art,'div.bt span.sb'),
                "is_hot":          bool(art.select_one('div.hotbadge'))
            })
        return jsonify({"query":q,"results":results})

    except Exception as e:
        # log server-side if you like, but return 200 with empty results
        print("Search parsing error:", e)
        return jsonify({"query":q,"results":[]})

@app.route('/donghua/info')
def get_donghua_info():
    """Get detailed info about a Donghua or Movie."""
    slug = request.args.get('slug','').strip()
    if not slug:
        return jsonify({"error":"slug parameter is required"}), 400

    # Try /donghua/, then fallback /movie/
    for path in ("donghua", "movie"):
        r = make_request(f"{BASE_URL}{path}/{slug}")
        if r:
            break
    if not r:
        return jsonify({"error":"animexin.dev unreachable"}), 502

    soup = BeautifulSoup(r.text, 'lxml')

    title       = safe_text(soup,'h1.entry-title')
    alter_title = safe_text(soup,'span.alter')
    cover_images= {
        "main":  safe_attr(soup,'div.ime img','src'),
        "thumb": safe_attr(soup,'div.thumb img','src')
    }

    rating = {}
    if soup.select_one('div.rating-prc'):
        for field in ('ratingValue','bestRating','ratingCount'):
            sel = soup.select_one(f"div.rating-prc meta[itemprop={field}]")
            if sel and sel.has_attr('content'):
                rating[field] = sel['content']
        vis = soup.select_one('div.rtb span')
        if vis and vis.has_attr('style'):
            rating['visual'] = vis['style'].replace('width:','').replace('%','').strip()

    followers = safe_text(soup,'div.bmc')
    if followers:
        followers = followers.replace('Followed','').replace('people','').strip()
    description = safe_text(soup,'div.mindesc')

    info_items = {}
    for span in soup.select('div.info-content span'):
        b = span.find('b')
        if b:
            key = b.text.strip(':').strip()
            b.decompose()
            info_items[key] = span.text.strip()

    genres  = [a.text for a in soup.select('div.genxed a')]
    tags    = [a.text for a in soup.select('div.bottom.tags a')]

    synopsis = {"english":None,"indonesian":None}
    synp = soup.select_one('div.synp')
    if synp:
        p_en = synp.find('p')
        p_id = synp.select_one('div.entry-content p')
        synopsis['english']    = p_en.text.strip() if p_en else None
        synopsis['indonesian']= p_id.text.strip() if p_id else None

    episodes = []
    for li in soup.select('div.eplister li'):
        a = li.find('a',href=True)
        if not a: continue
        ep_slug = a['href'].rstrip('/').split('/')[-1]
        episodes.append({
            "episode_number": safe_text(li,'div.epl-num'),
            "title":          safe_text(li,'div.epl-title'),
            "sub_type":       safe_text(li,'div.epl-sub'),
            "release_date":   safe_text(li,'div.epl-date'),
            "url":            a['href'],
            "ep_slug":        ep_slug
        })

    fl = {}
    lastend = soup.select_one('div.lastend')
    if lastend:
        ff = safe_text(lastend,'span.epcurfirst')
        urls = [a['href'] for a in lastend.find_all('a', href=True)]
        fl['first']= {"episode": ff, "url": urls[0] if urls else None}
        ll = safe_text(lastend,'span.epcurlast')
        fl['last'] = {"episode": ll, "url": urls[1] if len(urls)>1 else None}

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
    """Get video URLs for an episode."""
    ep = request.args.get('ep_slug','').strip()
    if not ep:
        return jsonify({"error":"ep_slug parameter is required"}), 400

    for path in ("donghua","movie"):
        r = make_request(f"{BASE_URL}{path}/{ep}")
        if r: break
    if not r:
        return jsonify({"error":"animexin.dev unreachable"}),502

    soup = BeautifulSoup(r.text,'lxml')
    sel  = soup.find('select',class_='mirror')
    if not sel:
        return jsonify({"error":"no video servers found"}),404

    video_servers=[]
    for opt in sel.find_all('option'):
        val = opt.get('value')
        if not val: continue
        html = base64.b64decode(val).decode('utf-8')
        fsoup= BeautifulSoup(html,'lxml')
        ifr  = fsoup.find('iframe')
        src  = ifr['src'] if ifr and ifr.has_attr('src') else None
        if src and src.startswith('//'):
            src = 'https:' + src
        video_servers.append({
            "server_name": opt.text.strip(),
            "video_url": src
        })

    return jsonify({
        "episode_url": r.url,
        "available_servers": len(video_servers),
        "video_servers": video_servers
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8080)), debug=True)
