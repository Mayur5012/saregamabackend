import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import boto3
from pymongo import MongoClient
from serverless_wsgi import handle_request

# Load environment variables
load_dotenv()

# Initialize the Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://your-frontend-render-url.app"}})

# Load environment variables from .env
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
MONGO_URI = os.getenv('MONGO_URI')

# MongoDB client initialization
client = MongoClient(MONGO_URI)
db = client['saregama']
songs_collection = db.songs

# AWS S3 client initialization
s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'mp3'}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/songs', methods=['GET'])
def get_songs():
    """Fetch all songs from MongoDB"""
    songs = list(songs_collection.find())
    for song in songs:
        song['_id'] = str(song['_id'])
    return jsonify(songs)

@app.route('/upload', methods=['POST'])
def upload_song():
    """Upload a song to AWS S3 and save metadata to MongoDB"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_url = upload_to_s3(file, filename)

        # Save song metadata to MongoDB
        song_data = {
            'name': request.form['name'],
            'url': file_url
        }

        songs_collection.insert_one(song_data)
        return jsonify({'message': 'Song uploaded successfully!'}), 201
    else:
        return jsonify({'error': 'Invalid file type'}), 400

def upload_to_s3(file, filename):
    """Upload file to AWS S3 and return the file URL"""
    s3_client.upload_fileobj(file, AWS_BUCKET_NAME, filename)
    file_url = f'https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{filename}'
    return file_url

if __name__ == '__main__':
    # Ensure app runs on the correct port provided by Render
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# For serverless deployments (AWS Lambda), use serverless_wsgi to handle requests
def lambda_handler(event, context):
    return handle_request(event, context)
