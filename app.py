from flask import Flask, render_template, request, jsonify
import os
from yt_dlp import YoutubeDL

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_reels():
    urls_input = request.form.get('urls', '')
    urls = [url.strip() for url in urls_input.split(",") if url.strip()]
    if not urls:
        return jsonify({"status": "error", "message": "No URLs provided."})

    cookies_file = 'cookies.txt' if os.path.exists('cookies.txt') else None

    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
        "quiet": True,
        "cookies": cookies_file,
        "noplaylist": True,
    }

    results = []
    with YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            try:
                ydl.download([url])
                results.append({"url": url, "status": "success"})
            except Exception as e:
                results.append({"url": url, "status": "failed", "error": str(e)})

    return jsonify({"status": "done", "results": results})

if __name__ == "__main__":
    app.run(debug=True)
