from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import base64
from urllib.parse import quote
from requests.exceptions import RequestException

app = Flask(__name__)
BASE_URL = "https://animexin.dev/"

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
                    "url": "Donghua URL (required)"
                },
                "example": f"{request.base_url}donghua/info?url=martial-universe-wu-dong-qian-kun-season-5/"
            },
            {
                "name": "Get Episode Videos",
                "path": "/episode/videos",
                "method": "GET",
                "parameters": {
                    "url": "Episode URL (required)"
                },
                "example": f"{request.base_url}episode/videos?url=martial-universe-wu-dong-qian-kun-season-5-episode-12-end-indonesia-english-sub/"
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
                
            title = link.get('title', '')
            url = link['href']
            image = article.find('img', {'src': True})
            image_url = image['src'] if image else None
            status = article.find('div', class_='status')
            status_text = status.text.strip() if status else None
            type_div = article.find('div', class_='typez')
            type_text = type_div.text.strip() if type_div else None
            
            results.append({
                "title": title,
                "url": url,
                "image": image_url,
                "status": status_text,
                "type": type_text
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
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    url = f"{BASE_URL}{url}"
    response = make_request(url)
    if not response:
        return jsonify({
            "error": "Failed to connect to animexin.dev",
            "solution": "This might be due to server restrictions. Try running the API on a different hosting provider."
        }), 502
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic info
        title = soup.find('h1', class_='entry-title').text.strip()
        
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
                    "url": ep_link['href']
                })
        
        return jsonify({
            "title": title,
            "info": info_items,
            "genres": genres,
            "episodes": episodes
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/episode/videos', methods=['GET'])
def get_episode_videos():
    """Get video URLs for an episode"""
    url = request.args.get('url')

    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    url = f"{BASE_URL}{url}"
    response = make_request(url)
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
                    "video_url": video_url,
                    "embed_html": decoded_html if decoded_html else None,
                    "encoded_data": encoded_url
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
