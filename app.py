import os
import threading
from flask import Flask, render_template, request, send_file, jsonify, Response
from yt_dlp import YoutubeDL
import time

app = Flask(__name__)

# Define the base folder and the download folder
BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))  # Current directory
DOWNLOAD_FOLDER = os.path.join(BASE_FOLDER, "youtube_downloader", "download")

# Ensure the download folder exists
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def delete_file_after_delay(file_path, delay=1800):
    """Delete a file after a specified delay (default: 30 minutes). This runs in a separate thread."""
    def delete_file():
        if os.path.exists(file_path):
            time.sleep(delay)  # Simulate waiting for the specified delay
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
        else:
            print(f"File {file_path} does not exist or was already deleted.")

    # Start the file deletion in a new thread to handle many concurrent users
    threading.Thread(target=delete_file, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_video_details', methods=['POST'])
def get_video_details():
    """Fetch video details and thumbnail."""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "Please provide a valid YouTube URL."}), 400

    try:
        # Extract video metadata using yt-dlp
        ydl_opts = {
            'quiet': True,
            'format': 'best'  # Get the best available format
        }
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_details = {
                "title": info_dict.get("title"),
                "uploader": info_dict.get("uploader"),
                "views": info_dict.get("view_count"),
                "thumbnail_url": info_dict.get("thumbnail"),
                "duration": info_dict.get("duration_string"),
                "url": url,
            }
        return jsonify(video_details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def progress_hook(d):
    """Track the download progress."""
    if d['status'] == 'downloading':
        percent = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100  # Avoid division by zero
        return f"data: {percent:.2f}%\n\n"

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    if not url:
        return "Error: No URL provided.", 400

    # Get the downloader's IP address
    downloader_ip = request.remote_addr
    print(f"Download request from IP: {downloader_ip}")

    try:
        # Configure yt-dlp to save in the download folder and track progress
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
        }

        # Use yt-dlp to download the video and stream the progress
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)

        # Schedule the file for deletion after 30 minutes (1800 seconds)
        delete_file_after_delay(file_path, delay=1800)

        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/download_progress')
def download_progress():
    """Stream the download progress to the client using Server-Sent Events."""
    def generate():
        while True:
            # Send a heartbeat or any other signal
            yield f"data: {'waiting'}\n\n"
            time.sleep(1)

    return Response(generate(), content_type='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, threaded=True)  # Enable threading in Flask for multiple connections
