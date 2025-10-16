from flask import Flask, request, render_template, jsonify, send_file
import os
import tempfile
import requests
import re
from datetime import datetime
import yt_dlp
import instaloader
from werkzeug.utils import secure_filename
import zipfile
import shutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-this'

# Create downloads directory if it doesn't exist
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

COOKIES_DIR = os.path.join(os.getcwd(), 'cookies')
if not os.path.exists(COOKIES_DIR):
    os.makedirs(COOKIES_DIR)

class UniversalDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    # ---------------- Platform Detection ----------------
    def detect_platform(self, url):
        url = url.lower()
        if 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube'
        elif 'instagram.com' in url:
            return 'instagram'
        elif 'facebook.com' in url or 'fb.watch' in url:
            return 'facebook'
        elif 'twitter.com' in url or 'x.com' in url:
            return 'twitter'
        elif 'tiktok.com' in url:
            return 'tiktok'
        elif 'pinterest.com' in url:
            return 'pinterest'
        elif 'linkedin.com' in url:
            return 'linkedin'
        elif 'snapchat.com' in url:
            return 'snapchat'
        elif 'reddit.com' in url:
            return 'reddit'
        elif 'twitch.tv' in url:
            return 'twitch'
        else:
            return 'unknown'

    # ---------------- Safe Filename ----------------
    def create_safe_filename(self, filename, max_length=100):
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip()
        if len(filename) > max_length:
            filename = filename[:max_length]
        return filename

    # ---------------- YouTube ----------------
    def download_youtube_content(self, url, path):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, '%(uploader)s - %(title)s.%(ext)s'),
                'format': 'best[height<=1080]',
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'ignoreerrors': True,
                'extractor_args': {
                    'youtube': {'player_client': ['web'], 'raw_json': True}
                },
                'cookiefile': os.path.join(COOKIES_DIR, 'youtube_cookies.txt'),
                'noplaylist': False
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if 'entries' in info:  # Playlist
                    titles = [entry.get('title', 'Unknown') for entry in info['entries'] if entry]
                    return {
                        'status': 'success',
                        'message': f'Downloaded {len(titles)} videos from playlist',
                        'titles': titles[:5],
                        'type': 'playlist'
                    }
                else:
                    return {
                        'status': 'success',
                        'message': 'YouTube content downloaded successfully!',
                        'title': info.get('title', 'Unknown'),
                        'uploader': info.get('uploader', 'Unknown'),
                        'type': 'video'
                    }

        except yt_dlp.utils.DownloadError as e:
            return {'status': 'error', 'message': f'YouTube download error: {str(e)}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Unexpected error: {str(e)}'}

    # ---------------- Instagram ----------------
    def download_instagram_content(self, url, path):
        try:
            loader = instaloader.Instaloader(
                dirname_pattern=path,
                filename_pattern='{profile}_{mediaid}_{date_utc}',
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=True,
                compress_json=False
            )
            if '/stories/' in url:
                username = self.extract_instagram_username(url)
                if username:
                    profile = instaloader.Profile.from_username(loader.context, username)
                    for story in loader.get_stories([profile.userid]):
                        for item in story.get_items():
                            loader.download_storyitem(item, target=username)
                    return {
                        'status': 'success',
                        'message': f'Instagram stories downloaded for {username}',
                        'type': 'stories'
                    }
            elif '/reel/' in url or '/p/' in url or '/tv/' in url:
                shortcode = self.extract_instagram_shortcode(url)
                post = instaloader.Post.from_shortcode(loader.context, shortcode)
                loader.download_post(post, target=post.owner_username)
                content_type = 'reel' if post.is_video else 'post'
                if post.typename == 'GraphSidecar':
                    content_type = 'carousel'
                return {
                    'status': 'success',
                    'message': f'Instagram {content_type} downloaded successfully!',
                    'username': post.owner_username,
                    'caption': post.caption[:100] + '...' if post.caption and len(post.caption) > 100 else post.caption,
                    'type': content_type
                }
            else:
                username = self.extract_instagram_username(url)
                profile = instaloader.Profile.from_username(loader.context, username)
                count = 0
                for post in profile.get_posts():
                    if count >= 10:
                        break
                    loader.download_post(post, target=username)
                    count += 1
                return {
                    'status': 'success',
                    'message': f'Downloaded {count} recent posts from {username}',
                    'type': 'profile'
                }
        except Exception as e:
            return {'status': 'error', 'message': f'Instagram error: {str(e)}'}

    # ---------------- TikTok ----------------
    def download_tiktok_content(self, url, path):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'TikTok_%(uploader)s_%(title)s.%(ext)s'),
                'format': 'best',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {'status': 'success', 'message': 'TikTok video downloaded successfully!', 'title': info.get('title', 'TikTok Video'), 'uploader': info.get('uploader', 'Unknown'), 'type': 'video'}
        except Exception as e:
            return {'status': 'error', 'message': f'TikTok error: {str(e)}'}

    # ---------------- Twitter/X ----------------
    def download_twitter_content(self, url, path):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'Twitter_%(uploader)s_%(title)s.%(ext)s'),
                'writesubtitles': True,
                'cookiefile': os.path.join(COOKIES_DIR, 'twitter_cookies.txt')
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {'status': 'success', 'message': 'Twitter content downloaded successfully!', 'title': info.get('title', 'Twitter Content'), 'uploader': info.get('uploader', 'Unknown'), 'type': 'tweet'}
        except Exception as e:
            return {'status': 'error', 'message': f'Twitter error: {str(e)}'}

    # ---------------- Facebook ----------------
    def download_facebook_content(self, url, path):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'Facebook_%(title)s.%(ext)s'),
                'format': 'best',
                'cookiefile': os.path.join(COOKIES_DIR, 'facebook_cookies.txt')
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {'status': 'success', 'message': 'Facebook content downloaded successfully!', 'title': info.get('title', 'Facebook Content'), 'type': 'video'}
        except Exception as e:
            return {'status': 'error', 'message': f'Facebook error: {str(e)}'}

    # ---------------- Reddit ----------------
    def download_reddit_content(self, url, path):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'Reddit_%(title)s.%(ext)s'),
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {'status': 'success', 'message': 'Reddit content downloaded successfully!', 'title': info.get('title', 'Reddit Post'), 'type': 'post'}
        except Exception as e:
            return {'status': 'error', 'message': f'Reddit error: {str(e)}'}

    # ---------------- Generic ----------------
    def download_generic_content(self, url, path):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, '%(extractor)s_%(title)s.%(ext)s'),
                'format': 'best',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {'status': 'success', 'message': 'Content downloaded successfully!', 'title': info.get('title', 'Unknown'), 'extractor': info.get('extractor', 'Unknown'), 'type': 'media'}
        except Exception as e:
            return {'status': 'error', 'message': f'Download error: {str(e)}'}

    # ---------------- Instagram helpers ----------------
    def extract_instagram_shortcode(self, url):
        patterns = [r'/p/([^/?]+)', r'/reel/([^/?]+)', r'/tv/([^/?]+)']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_instagram_username(self, url):
        match = re.search(r'instagram\.com/([^/?]+)', url)
        if match:
            return match.group(1)
        return None

    # ---------------- Main Downloader ----------------
    def download_content(self, url, custom_path=None):
        path = custom_path or DOWNLOAD_DIR
        platform = self.detect_platform(url)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_folder = os.path.join(path, f"{platform}_{timestamp}")
        os.makedirs(download_folder, exist_ok=True)

        try:
            if platform == 'youtube':
                return self.download_youtube_content(url, download_folder)
            elif platform == 'instagram':
                return self.download_instagram_content(url, download_folder)
            elif platform == 'tiktok':
                return self.download_tiktok_content(url, download_folder)
            elif platform == 'twitter':
                return self.download_twitter_content(url, download_folder)
            elif platform == 'facebook':
                return self.download_facebook_content(url, download_folder)
            elif platform == 'reddit':
                return self.download_reddit_content(url, download_folder)
            else:
                return self.download_generic_content(url, download_folder)
        except Exception as e:
            return {'status': 'error', 'message': f'Unexpected error: {str(e)}'}

# Initialize downloader
downloader = UniversalDownloader()

# ---------------- Flask Routes ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'status': 'error', 'message': 'URL is required'})
    platform = downloader.detect_platform(url)
    result = downloader.download_content(url)
    result['platform'] = platform
    return jsonify(result)

@app.route('/bulk-download', methods=['POST'])
def bulk_download():
    data = request.get_json()
    urls = data.get('urls', [])
    if not urls:
        return jsonify({'status': 'error', 'message': 'URLs list is required'})
    results = []
    for url in urls:
        if url.strip():
            result = downloader.download_content(url.strip())
            result['url'] = url
            results.append(result)
    return jsonify({'status': 'success', 'message': f'Processed {len(results)} URLs', 'results': results})

@app.route('/downloads')
def list_downloads():
    items = []
    if os.path.exists(DOWNLOAD_DIR):
        for item in os.listdir(DOWNLOAD_DIR):
            item_path = os.path.join(DOWNLOAD_DIR, item)
            if os.path.isfile(item_path):
                items.append({'name': item, 'type': 'file', 'size': os.path.getsize(item_path)})
            elif os.path.isdir(item_path):
                file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                items.append({'name': item, 'type': 'folder', 'file_count': file_count})
    return jsonify({'items': items})

@app.route('/download-file/<path:filename>')
def download_file(filename):
    safe_filename = secure_filename(filename)
    file_path = os.path.join(DOWNLOAD_DIR, safe_filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

@app.route('/download-folder/<foldername>')
def download_folder(foldername):
    safe_foldername = secure_filename(foldername)
   
