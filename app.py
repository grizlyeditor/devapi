from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import aiohttp
import requests
import json
import like_pb2
import uid_generator_pb2
import data_pb2
from google.protobuf.json_format import MessageToJson, MessageToDict

app = Flask(__name__)

# ======================
# 🔑 API KEY CONFIG
# ======================
API_KEY = "grizlyapi"  # <-- your secret API key

# ======================
# 🔒 AES Encryption
# ======================
def encrypt_message(plaintext):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(plaintext, AES.block_size)
    encrypted_message = cipher.encrypt(padded_message)
    return binascii.hexlify(encrypted_message).decode('utf-8')

# ======================
# 🧩 Token Management
# ======================
def load_tokens(server_name):
    if server_name == "IND":
        with open("token_ind.json", "r") as f:
            return json.load(f)
    elif server_name in {"BR", "US", "SAC", "NA"}:
        with open("token_br.json", "r") as f:
            return json.load(f)
    else:
        with open("token_bd.json", "r") as f:
            return json.load(f)

# ======================
# ❤️ Like Request
# ======================
def create_protobuf_message(user_id, region):
    message = like_pb2.like()
    message.uid = int(user_id)
    message.region = region
    return message.SerializeToString()

async def send_request(encrypted_uid, token, url):
    edata = bytes.fromhex(encrypted_uid)
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'Expect': "100-continue",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': "OB50"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=edata, headers=headers) as response:
            return response.status

async def send_multiple_requests(uid, server_name, url):
    region = server_name
    protobuf_message = create_protobuf_message(uid, region)
    encrypted_uid = encrypt_message(protobuf_message)
    
    tasks = []
    tokens = load_tokens(server_name)
    for i in range(100):
        token = tokens[i % len(tokens)]["token"]
        tasks.append(send_request(encrypted_uid, token, url))
    
    results = await asyncio.gather(*tasks)
    return results

# ======================
# 📋 Info Request
# ======================
def create_info_protobuf(uid):
    message = uid_generator_pb2.uid_generator()
    message.saturn_ = int(uid)
    message.garena = 1
    return message.SerializeToString()

def encrypt_info_request(uid):
    protobuf_data = create_info_protobuf(uid)
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

def get_info_endpoint(server_name):
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    else:
        return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"

def get_like_endpoint(server_name):
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/LikeProfile"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/LikeProfile"
    else:
        return "https://clientbp.ggblueshark.com/LikeProfile"

def make_info_request(uid, server_name, token):
    encrypted_data = encrypt_info_request(uid)
    endpoint = get_info_endpoint(server_name)
    
    edata = bytes.fromhex(encrypted_data)
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'Expect': "100-continue",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': "OB50"
    }

    response = requests.post(endpoint, data=edata, headers=headers, verify=False)
    hex_response = response.content.hex()
    binary = bytes.fromhex(hex_response)
    
    try:
        info = data_pb2.AccountPersonalShowInfo()
        info.ParseFromString(binary)
        return info
    except Exception as e:
        print(f"Error decoding Protobuf data: {e}")
        return None

def extract_player_info(info_data):
    if not info_data:
        return None
    
    basic_info = info_data.basic_info
    return {
        'uid': basic_info.account_id,
        'nickname': basic_info.nickname,
        'level': basic_info.level,
        'region': basic_info.region,
        'likes': basic_info.liked,
        'release_version': basic_info.release_version,
        'exp': basic_info.exp,
        'rank': basic_info.rank,
        'ranking_points': basic_info.ranking_points,
        'cs_rank': basic_info.cs_rank,
        'cs_ranking_points': basic_info.cs_ranking_points
    }

# ======================
# 🌐 MAIN ROUTE
# ======================
@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    server_name = request.args.get("server_name", "").upper()
    key = request.args.get("key")

    # 🔒 Check for valid API key
    if not key or key != API_KEY:
        return jsonify({"error": "Invalid API key"}), 403

    if not uid or not server_name:
        return jsonify({"error": "UID and server_name are required"}), 400

    try:
        tokens = load_tokens(server_name)
        if not tokens:
            return jsonify({"error": "No tokens available for this server"}), 400
        
        token = tokens[0]['token']
        
        # Info before likes
        before_info = make_info_request(uid, server_name, token)
        if not before_info:
            return jsonify({"error": "Failed to get player info"}), 400
            
        player_info_before = extract_player_info(before_info)
        if not player_info_before:
            return jsonify({"error": "Failed to extract player info"}), 400
            
        before_likes = player_info_before.get('likes', 0)
        
        # Like send
        like_url = get_like_endpoint(server_name)
        asyncio.run(send_multiple_requests(uid, server_name, like_url))
        
        # Info after likes
        after_info = make_info_request(uid, server_name, token)
        if not after_info:
            return jsonify({"error": "Failed to get player info after sending likes"}), 400
            
        player_info_after = extract_player_info(after_info)
        if not player_info_after:
            return jsonify({"error": "Failed to extract player info after sending likes"}), 400
            
        after_likes = player_info_after.get('likes', 0)
        like_given = after_likes - before_likes
        
        result = {
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_likes,
            "LikesbeforeCommand": before_likes,
            "PlayerLevel": str(player_info_after.get('level', '')),
            "PlayerNickname": player_info_after.get('nickname', ''),
            "PlayerRegion": player_info_after.get('region', ''),
            "UID": str(player_info_after.get('uid', '')),
            "ReleaseVersion": player_info_after.get('release_version', ''),
            "status": 2 if like_given == 0 else 1
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# ======================
# 🚀 RUN APP
# ======================
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=5000)

# modify by @Nilay_vii
# credits @NR_CODEX