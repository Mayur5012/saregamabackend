import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import boto3
from pymongo import MongoClient
from serverless_wsgi import handle_request

load_dotenv()

app = Flask(__name__)
CORS(app)

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
MONGO_URI = os.getenv('MONGO_URI')

# MongoDB client
client = MongoClient(MONGO_URI)
db = client['saregama']
songs_collection = db.songs

# AWS S3 client
s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

ALLOWED_EXTENSIONS = {'mp3'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/songs', methods=['GET'])
def get_songs():
    songs = list(songs_collection.find())
    for song in songs:
        song['_id'] = str(song['_id'])
    return jsonify(songs)

@app.route('/upload', methods=['POST'])
def upload_song():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_url = upload_to_s3(file, filename)

        song_data = {
            'name': request.form['name'],
            'url': file_url
        }

        songs_collection.insert_one(song_data)
        return jsonify({'message': 'Song uploaded successfully!'}), 201
    else:
        return jsonify({'error': 'Invalid file type'}), 400

def upload_to_s3(file, filename):
    s3_client.upload_fileobj(file, AWS_BUCKET_NAME, filename)
    file_url = f'https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{filename}'
    return file_url

# Use the serverless-wsgi handler for the Flask app
def handler(event, context):
    return handle_request(app, event, context)

