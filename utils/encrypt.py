import random
import rsa
import base64
import hashlib
import uuid
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

n = 21594300428334646329393296465327247608593538968207227725504834910767283352043033486153266470952842619717435786023550216118175358468344847600166174944240636513614491735529488542052888395376419723636544185872272584090575904576271298284497472735222674858409037553008049845502538367355260688388224699394267291073042455163488596527774733683895330263989547484325616107696706344789576205344850129431200983555152538381266465128501567477884529317150143532404243697673077241952720781430723023518035429308733907985155804586233888060216312871570414343135002626541825235439731658942280989501317867992830351297917024864950204324877
e = 65537


def encrypt_rsa(password: str) -> str:
    pub_key = rsa.PublicKey(n, e)
    encrypted = rsa.encrypt(password.encode("utf-8"), pub_key)
    return base64.b64encode(encrypted).decode("utf-8")


def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


w = "c640ca392cd45fb3a55b00a63a86c618"


def calculate_sign(timestamp: str, path: str, data: dict) -> str:
    c = w + path
    for key in sorted(data.keys()):
        value = data[key]
        if value != "" and value is not None and not isinstance(value, dict):
            c += str(key) + str(value)
    c += str(timestamp) + " " + w
    return md5_hash(c)


def encrypt_aes_ecb(data: str, key: str) -> str:
    cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
    padded = pad(data.encode("utf-8"), AES.block_size, style="pkcs7")
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


KEY = "c1h2i5n6g2o2k4a7"
IV = "C2H3I4N5G2O3K1E4"


def encrypt_aes_cbc(data: str) -> str:
    cipher = AES.new(KEY.encode("utf-8"), AES.MODE_CBC, IV.encode("utf-8"))
    padded = pad(data.encode("utf-8"), AES.block_size, style="pkcs7")
    return cipher.encrypt(padded).hex()


def generate_order_pin() -> str:
    x = random.randint(100, 1200)
    y = random.randint(900, 1200)
    return encrypt_aes_cbc(f"{x},{y}")


def generate_uuid() -> str:
    return str(uuid.uuid4())
