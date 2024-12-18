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
CORS(app, resources={r"/*": {"origins": "*"}})

# Load environment variables with error handling
try:
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
    MONGO_URI = os.getenv('MONGO_URI')

    # Validate critical environment variables
    if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET_NAME, MONGO_URI]):
        raise ValueError("Missing critical environment variables")

    # MongoDB client initialization
    client = MongoClient(MONGO_URI)
    db = client['saregama']
    songs_collection = db.songs

    # AWS S3 client initialization
    s3_client = boto3.client('s3', 
        aws_access_key_id=AWS_ACCESS_KEY_ID, 
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

except Exception as e:
    print(f"Initialization error: {e}")
    raise

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg'}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/songs', methods=['GET'])
def get_songs():
    """Fetch all songs from MongoDB"""
    try:
        songs = list(songs_collection.find())
        for song in songs:
            song['_id'] = str(song['_id'])
        return jsonify(songs)
    except Exception as e:
        return jsonify({'error': f'Failed to fetch songs: {str(e)}'}), 500

@app.route('/upload', methods=['POST'])
def upload_song():
    """Upload a song to AWS S3 and save metadata to MongoDB"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file and allowed_file(file.filename):
            # Generate a unique filename to prevent overwriting
            filename = f"{os.urandom(16).hex()}_{secure_filename(file.filename)}"
            file_url = upload_to_s3(file, filename)

            # Save song metadata to MongoDB
            song_data = {
                'name': request.form.get('name', filename),
                'url': file_url,
                'original_filename': file.filename
            }

            result = songs_collection.insert_one(song_data)
            return jsonify({
                'message': 'Song uploaded successfully!', 
                'song_id': str(result.inserted_id)
            }), 201
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

def upload_to_s3(file, filename):
    """Upload file to AWS S3 and return the file URL"""
    try:
        s3_client.upload_fileobj(file, AWS_BUCKET_NAME, filename)
        file_url = f'https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{filename}'
        return file_url
    except Exception as e:
        print(f"S3 upload error: {e}")
        raise

# Default route for health check
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

# Serverless handler for AWS Lambda
def lambda_handler(event, context):
    return handle_request(event, context)

# Gunicorn will use this
if __name__ != '__main__':
    # Configuration for production
    app.config['DEBUG'] = False
    app.config['TESTING'] = False

# Optional: Local development server
if __name__ == '__main__':
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 5000))
    )