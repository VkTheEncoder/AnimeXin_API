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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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
    """Helper function to make requests with error handling"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response
    except RequestException as e:
        print(f"Request failed: {e}")
        return None

@app.route('/')
def home():
    """Show welcome page with API instructions in JSON format"""
    welcome_message = {
        "api_name": "AnimeXin API",
        "author": {
            "name": "RAHAT",
            "telegram": "@r4h4t_69",
            "contact": "https://t.me/r4h4t_69"
        },
        "description": "API service for AnimeXin website data",
        "note": "The API might not work directly as animexin.dev may block their servers. For reliable operation, consider running this on a different hosting provider or use proxy.",
        "endpoints": [
            {
                "name": "Search Donghua",
                "path": "/search",
                "method": "GET",
                "parameters": {
                    "query": "Search term (required)"
                },
                "example": f"{request.base_url}search?query=Martial+Universe"
            },
            {
                "name": "Get Donghua Info",
                "path": "/donghua/info",
                "method": "GET",
                "parameters": {
                    "url": "Donghua Slug (required)"
                },
                "example": f"{request.base_url}donghua/info?slug=martial-universe-wu-dong-qian-kun-season-5"
            },
            {
                "name": "Get Episode Videos",
                "path": "/episode/videos",
                "method": "GET",
                "parameters": {
                    "url": "Episode Slug (required)"
                },
                "example": f"{request.base_url}episode/videos?ep_slug=martial-universe-wu-dong-qian-kun-season-5-episode-12-end-indonesia-english-sub"
            }
        ],
        "usage_tips": [
            "URL parameters must be properly URL-encoded",
            "For search terms with spaces, use '+' or '%20'",
            "The API returns JSON responses for all endpoints"
        ]
    }
    return jsonify(welcome_message)

@app.route('/search', methods=['GET'])
def search_donghua():
    """Search for Donghua by title"""
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    search_url = f"{BASE_URL}?s={quote(query)}"
    response = make_request(search_url)

    if not response:
        return jsonify({
            "error": "Failed to connect to animexin.dev",
            "solution": "This might be due to server restrictions. Try running the API on a different hosting provider."
        }), 502

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        articles = soup.select('div.listupd article.bs')

        for article in articles:
            link = article.find('a', href=True)
            if not link:
                continue

            title = link.get('title', '').strip()
            url = link['href']
            image = article.find('img', {'src': True})
            image_url = image['src'] if image else None

            # Extract additional fields
            status_tag = article.find('div', class_='status')
            status_text = status_tag.text.strip() if status_tag else None

            type_div = article.find('div', class_='typez')
            type_text = type_div.text.strip() if type_div else None

            badge = article.find('div', class_='hotbadge')
            is_hot = bool(badge)

            bt_div = article.find('div', class_='bt')
            episode_status = bt_div.find('span', class_='epx').text.strip() if bt_div and bt_div.find('span', class_='epx') else None
            sub_status = bt_div.find('span', class_='sb').text.strip() if bt_div and bt_div.find('span', class_='sb') else None

            slug = url.split('/')[-2]
            rel_id = link.get('rel')

            results.append({
                "title": title,
                "slug": slug,
                "url": url,
                "image": image_url,
                "status": status_text,
                "type": type_text,
                "episode_status": episode_status,
                "sub_status": sub_status,
                "is_hot": is_hot,
                "rel_id": rel_id
            })

        return jsonify({
            "query": query,
            "results": results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/donghua/info', methods=['GET'])
def get_donghua_info():
    """Get detailed info about a Donghua"""
    slug = request.args.get('slug')
    if not slug:
        return jsonify({"error": "slug parameter is required"}), 400

    # try donghua first
    donghua_url = f"{BASE_URL}donghua/{slug}"
    response = make_request(donghua_url)
    # if it 404s or errors, try movie
    if not response or response.status_code >= 400:
        movie_url = f"{BASE_URL}movie/{slug}"
        response = make_request(movie_url)
    if not response:
        return jsonify({
            "error": "Failed to connect to animexin.dev",
            "solution": "This might be due to server restrictions. Try running the API on a different hosting provider."
        }), 502
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic info
        title = soup.find('h1', class_='entry-title').text.strip()
        alter_title = soup.find('span', class_='alter').text.strip() if soup.find('span', class_='alter') else None
        
        # Extract cover images
        cover_images = {
            'main': soup.find('div', class_='ime').find('img')['src'] if soup.find('div', class_='ime') else None,
            'thumb': soup.find('div', class_='thumb').find('img')['src'] if soup.find('div', class_='thumb') else None
        }
        
        # Extract rating info
        rating_div = soup.find('div', class_='rating-prc')
        rating_info = {
            'value': rating_div.find('meta', itemprop='ratingValue')['content'] if rating_div else None,
            'best': rating_div.find('meta', itemprop='bestRating')['content'] if rating_div else None,
            'count': rating_div.find('meta', itemprop='ratingCount')['content'] if rating_div else None,
            'visual': soup.find('div', class_='rtb').find('span')['style'].replace('width:', '').replace('%', '').strip() if soup.find('div', class_='rtb') else None
        }
        
        # Extract followers count
        followers = soup.find('div', class_='bmc').text.replace('Followed', '').replace('people', '').strip() if soup.find('div', class_='bmc') else None
        
        # Extract basic description
        description = soup.find('div', class_='mindesc').text.strip() if soup.find('div', class_='mindesc') else None
        
        # Extract info items
        info_div = soup.find('div', class_='info-content')
        if not info_div:
            return jsonify({"error": "Could not find info content"}), 404
            
        info_items = {}
        spans = info_div.find_all('span')
        for span in spans:
            if span.find('b'):
                key = span.find('b').text.strip(':').strip()
                span.find('b').decompose()
                value = span.text.strip()
                info_items[key] = value
        
        # Extract genres
        genres = [a.text for a in soup.select('div.genxed a')]
        
        # Extract tags
        tags = [a.text for a in soup.select('div.bottom.tags a')]
        
        # Extract synopsis
        synopsis_div = soup.find('div', class_='synp')
        synopsis = {
            'english': synopsis_div.find('p').text.strip() if synopsis_div and synopsis_div.find('p') else None,
            'indonesian': synopsis_div.find('div', class_='entry-content').find('p').text.strip() if synopsis_div and synopsis_div.find('div', class_='entry-content') and synopsis_div.find('div', class_='entry-content').find('p') else None
        }
        
        # Extract episodes
        episodes = []
        ep_list = soup.find('div', class_='eplister')
        if ep_list:
            for li in ep_list.find_all('li'):
                ep_link = li.find('a', href=True)
                if not ep_link:
                    continue
                    
                ep_num = li.find('div', class_='epl-num').text.strip()
                ep_title = li.find('div', class_='epl-title').text.strip()
                ep_sub = li.find('div', class_='epl-sub').text.strip()
                ep_date = li.find('div', class_='epl-date').text.strip()
                
                episodes.append({
                    "episode_number": ep_num,
                    "title": ep_title,
                    "sub_type": ep_sub,
                    "release_date": ep_date,
                    "url": ep_link['href'],
                    "ep_slug": ep_link['href'].split('/')[-2]
                })
        
        # Extract first and last episode
        lastend_div = soup.find('div', class_='lastend')
        first_last_ep = {
            'first': {
                'episode': lastend_div.find('span', class_='epcurfirst').text.strip() if lastend_div and lastend_div.find('span', class_='epcurfirst') else None,
                'url': lastend_div.find('a')['href'] if lastend_div and lastend_div.find('a') else None
            },
            'last': {
                'episode': lastend_div.find('span', class_='epcurlast').text.strip() if lastend_div and lastend_div.find('span', class_='epcurlast') else None,
                'url': lastend_div.find_all('a')[1]['href'] if lastend_div and len(lastend_div.find_all('a')) > 1 else None
            }
        }
        
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
            "first_last_episode": first_last_ep,
            "episodes": episodes
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/episode/videos', methods=['GET'])
def get_episode_videos():
    """Get video URLs for an episode"""
    ep_slug = request.args.get('ep_slug')
    if not ep_slug:
        return jsonify({"error": "ep_slug parameter is required"}), 400

    # same fallback logic for episodes
    donghua_ep = f"{BASE_URL}donghua/{ep_slug}"
    response = make_request(donghua_ep)
    if not response or response.status_code >= 400:
        movie_ep = f"{BASE_URL}movie/{ep_slug}"
        response = make_request(movie_ep)
    if not response:
        return jsonify({
            "error": "Failed to connect to animexin.dev",
            "solution": "This might be due to server restrictions. Try running the API on a different hosting provider."
        }), 502
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the video server select element
        server_select = soup.find('select', class_='mirror')
        if not server_select:
            return jsonify({"error": "No video servers found"}), 404
            
        video_servers = []
        for option in server_select.find_all('option'):
            if option.get('value'):
                encoded_url = option['value']
                decoded_html = decode_video_url(encoded_url)
                
                # Extract the clean video URL from the HTML
                video_url = extract_video_url(decoded_html)
                
                video_servers.append({
                    "server_name": option.text.strip(),
                    "video_url": video_url
                    #"embed_html": decoded_html if decoded_html else None,
                    #"encoded_data": encoded_url
                })
        
        return jsonify({
            "episode_url": url,
            "available_servers": len(video_servers),
            "video_servers": video_servers
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_video_url(html):
    """Extract clean video URL from embed HTML"""
    if not html:
        return None
        
    try:
        soup = BeautifulSoup(html, 'html.parser')
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'):
            src = iframe['src']
            # Clean up URL
            if src.startswith('//'):
                src = f"https:{src}"
            return src
        return None
    except:
        return None


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))  # Get PORT from environment variable or default to 5000
    app.run(host='0.0.0.0', port=port, debug=True)
