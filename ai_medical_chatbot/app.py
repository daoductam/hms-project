import os
import mysql.connector
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cấu hình AI Provider (Groq hoặc Gemini)
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()  # Mặc định dùng Gemini

# Groq API Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# V1beta chỉ hỗ trợ: gemini-pro, gemini-pro-vision
# V1 hỗ trợ: gemini-1.5-flash, gemini-1.5-pro
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-pro")  # Có thể dùng: gemini-pro, gemini-pro-vision, gemini-1.5-flash, gemini-1.5-pro

# Tự động chọn API version dựa trên model
# Nếu model là gemini-1.5-* thì dùng v1, ngược lại dùng v1beta
if GEMINI_MODEL.startswith("gemini-1.5"):
    GEMINI_API_VERSION = "v1"
else:
    GEMINI_API_VERSION = "v1beta"

# Cho phép override bằng environment variable
GEMINI_API_VERSION = os.environ.get("GEMINI_API_VERSION", GEMINI_API_VERSION)

GEMINI_API_BASE = f"https://generativelanguage.googleapis.com/{GEMINI_API_VERSION}"

# Cấu hình Proxy (nếu cần fake IP)
PROXY_URL = os.environ.get("PROXY_URL")  # Ví dụ: "http://proxy.example.com:8080" hoặc "socks5://127.0.0.1:1080"
USE_PROXY = os.environ.get("USE_PROXY", "false").lower() == "true"

# Fake headers để tránh bị detect
FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# Kiểm tra API key theo provider được chọn
if AI_PROVIDER == "groq":
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY is not set in environment variables!")
        raise ValueError("GROQ_API_KEY is not set in the .env file")
    logger.info("Using Groq API as AI provider")
elif AI_PROVIDER == "gemini":
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set in environment variables!")
        raise ValueError("GEMINI_API_KEY is not set in the .env file")
    logger.info(f"Using Gemini API ({GEMINI_MODEL}) with version {GEMINI_API_VERSION} as AI provider")
else:
    raise ValueError(f"Invalid AI_PROVIDER: {AI_PROVIDER}. Must be 'groq' or 'gemini'")

# Cấu hình proxy nếu được bật
proxies = None
if USE_PROXY and PROXY_URL:
    proxies = {
        "http": PROXY_URL,
        "https": PROXY_URL
    }
    logger.info(f"Using proxy: {PROXY_URL}")

# Cấu hình Database
# Lưu ý: User cần quyền truy cập vào cả 3 database: userdb, profiledb, appointmentdb
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "TaM123456789@", 
    "port": 3306
}

class ChatRequest(BaseModel):
    message: str
    user_id: str
    role: str = "PATIENT"

# --- HÀM GỌI GROQ API ---
def call_groq_api(system_instruction: str, user_message: str) -> str:
    """Gọi Groq API để lấy phản hồi từ AI"""
    headers = {
        **FAKE_HEADERS,
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.3,
        "max_tokens": 1024
    }
    
    logger.info(f"Calling Groq API with model: {payload['model']}")
    if proxies:
        logger.info(f"Using proxy: {PROXY_URL}")
    
    response = requests.post(
        GROQ_API_URL,
        json=payload,
        headers=headers,
        proxies=proxies,
        timeout=30,
        verify=True
    )
    
    logger.info(f"Groq API response status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    else:
        error_detail = response.text
        logger.error(f"Groq API error: {response.status_code} - {error_detail}")
        
        if response.status_code == 401:
            raise HTTPException(
                status_code=500, 
                detail="API key không hợp lệ hoặc đã hết hạn. Vui lòng kiểm tra lại GROQ_API_KEY trong file .env"
            )
        elif response.status_code == 403:
            raise HTTPException(
                status_code=500,
                detail="Access denied. Có thể do IP bị chặn hoặc API key không có quyền truy cập. Vui lòng kiểm tra lại cài đặt trên Groq Console."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi từ Groq API: {response.status_code} - {error_detail}"
            )

# --- HÀM GỌI GEMINI API ---
def call_gemini_api(system_instruction: str, user_message: str) -> str:
    """Gọi Gemini API để lấy phản hồi từ AI"""
    # Gemini API URL với API key trong query parameter
    url = f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    # V1beta (gemini-pro) không hỗ trợ systemInstruction riêng, cần kết hợp vào prompt
    # V1 (gemini-1.5) hỗ trợ systemInstruction riêng
    if GEMINI_API_VERSION == "v1" and GEMINI_MODEL.startswith("gemini-1.5"):
        # Dùng systemInstruction riêng cho v1
        payload = {
            "contents": [{
                "parts": [{
                    "text": user_message
                }]
            }],
            "systemInstruction": {
                "parts": [{
                    "text": system_instruction
                }]
            },
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024,
            }
        }
    else:
        # V1beta: kết hợp system instruction vào user message
        full_prompt = f"{system_instruction}\n\nNgười dùng hỏi: {user_message}\n\nHãy trả lời:"
        payload = {
            "contents": [{
                "parts": [{
                    "text": full_prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024,
            }
        }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    logger.info(f"Calling Gemini API with model: {GEMINI_MODEL}")
    if proxies:
        logger.info(f"Using proxy: {PROXY_URL}")
    
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        proxies=proxies,
        timeout=30,
        verify=True
    )
    
    logger.info(f"Gemini API response status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        # Gemini trả về format khác
        if "candidates" in result and len(result["candidates"]) > 0:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            return content
        else:
            raise HTTPException(status_code=500, detail="Gemini API trả về response không hợp lệ")
    else:
        error_detail = response.text
        logger.error(f"Gemini API error: {response.status_code} - {error_detail}")
        
        if response.status_code == 400:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi request đến Gemini API: {error_detail}"
            )
        elif response.status_code == 401 or response.status_code == 403:
            raise HTTPException(
                status_code=500,
                detail="API key không hợp lệ hoặc đã hết hạn. Vui lòng kiểm tra lại GEMINI_API_KEY trong file .env"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi từ Gemini API: {response.status_code} - {error_detail}"
            )

# --- HÀM HỖ TRỢ: CHUYỂN ĐỔI USER_ID -> EMAIL -> PROFILE_ID ---
def resolve_profile_id(cursor, user_id, role):
    """
    Tìm ID thực sự của Patient/Doctor trong ProfileDB thông qua Email từ UserDB
    """
    try:
        # 1. Tìm Email từ UserDB dựa trên user_id
        # Lưu ý: Tên bảng mặc định thường là 'user' hoặc 'users'. 
        # Nếu lỗi, hãy kiểm tra lại tên bảng trong userdb của bạn.
        cursor.execute("SELECT email FROM userdb.user WHERE id = %s", (user_id,))
        user_record = cursor.fetchone()
        
        if not user_record:
            print(f"Không tìm thấy user với id {user_id} trong userdb")
            return None

        email = user_record['email']
        print(f"Mapping: UserID {user_id} -> Email {email}")

        # 2. Dùng Email để tìm Profile ID trong ProfileDB
        if role.upper() == "PATIENT":
            cursor.execute("SELECT id FROM profiledb.patient WHERE email = %s", (email,))
        elif role.upper() == "DOCTOR":
            cursor.execute("SELECT id FROM profiledb.doctor WHERE email = %s", (email,))
        else:
            return user_id # Admin hoặc role khác có thể không cần map

        profile_record = cursor.fetchone()
        if profile_record:
            print(f"Mapping: Email {email} -> ProfileID {profile_record['id']}")
            return profile_record['id']
        else:
            print(f"Không tìm thấy hồ sơ {role} cho email {email}")
            return None

    except Exception as e:
        print(f"Lỗi mapping ID: {e}")
        return None

# --- HÀM LẤY DỮ LIỆU TỔNG HỢP ---
def get_context_by_role(user_id, role):
    conn = None
    info_str = ""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # BƯỚC QUAN TRỌNG: Lấy đúng ID hồ sơ (Profile ID)
        real_id = resolve_profile_id(cursor, user_id, role)
        
        # Nếu không tìm thấy profile (ví dụ mới đăng ký chưa có hồ sơ), trả về thông báo
        if not real_id and role.upper() in ["PATIENT", "DOCTOR"]:
            return "Hệ thống không tìm thấy hồ sơ chi tiết của người dùng này. Vui lòng cập nhật hồ sơ cá nhân."

        # 1. LOGIC CHO BỆNH NHÂN (PATIENT)
        if role.upper() == "PATIENT":
            query = """
                SELECT appointment_time, reason, status, notes, doctor_id 
                FROM appointmentdb.appointment 
                WHERE patient_id = %s AND appointment_time >= NOW()
                ORDER BY appointment_time ASC LIMIT 5
            """
            cursor.execute(query, (real_id,))
            appts = cursor.fetchall()
            
            if appts:
                info_str += "📅 Lịch hẹn sắp tới của bạn:\n"
                for a in appts:
                    time_s = a['appointment_time'].strftime("%H:%M %d/%m/%Y")
                    status_vn = "Đã đặt" if a['status'] == 'BOOKED' else a['status']
                    info_str += f"- {time_s}: {a['reason']} (Trạng thái: {status_vn})\n"
            else:
                info_str += "Bạn hiện không có lịch hẹn nào sắp tới.\n"

        # 2. LOGIC CHO BÁC SĨ (DOCTOR)
        elif role.upper() == "DOCTOR":
            query = """
                SELECT appointment_time, reason, status, patient_id
                FROM appointmentdb.appointment 
                WHERE doctor_id = %s AND status != 'CANCELLED'
                AND appointment_time >= CURDATE()
                ORDER BY appointment_time ASC LIMIT 10
            """
            cursor.execute(query, (real_id,))
            tasks = cursor.fetchall()

            if tasks:
                info_str += "🩺 Lịch làm việc sắp tới của Bác sĩ:\n"
                for t in tasks:
                    time_s = t['appointment_time'].strftime("%H:%M %d/%m/%Y")
                    info_str += f"- {time_s}: Khám bệnh nhân (ID: {t['patient_id']}) về '{t['reason']}'\n"
            else:
                info_str += "Bác sĩ chưa có lịch hẹn nào sắp tới.\n"

        # 3. LOGIC CHO ADMIN (ADMIN)
        elif role.upper() == "ADMIN":
            info_str += "📊 Báo cáo nhanh hệ thống:\n"
            
            # Thống kê User
            cursor.execute("SELECT COUNT(*) as cnt FROM userdb.user")
            user_cnt = cursor.fetchone()['cnt']
            info_str += f"- Tổng số tài khoản: {user_cnt}\n"

            # Thống kê Lịch hẹn hôm nay
            cursor.execute("SELECT COUNT(*) as cnt FROM appointmentdb.appointment WHERE DATE(appointment_time) = CURDATE()")
            today_appt = cursor.fetchone()['cnt']
            info_str += f"- Lịch hẹn hôm nay: {today_appt}\n"

            # Thống kê thuốc (Nếu có)
            try:
                cursor.execute("SELECT COUNT(*) as cnt FROM pharmacydb.medicine_inventory WHERE stock < 50")
                low_stock = cursor.fetchone()['cnt']
                info_str += f"- Cảnh báo kho: {low_stock} loại thuốc sắp hết.\n"
            except:
                pass

        return info_str

    except mysql.connector.Error as err:
        return f"Lỗi truy xuất DB: {err}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. Lấy Context từ DB (đã qua xử lý map ID)
        db_context = get_context_by_role(request.user_id, request.role)
        current_time = datetime.now().strftime("%H:%M %d/%m/%Y")

        # 2. System Prompt
        role_instruction = ""
        if request.role.upper() == "DOCTOR":
            role_instruction = "Bạn là trợ lý ảo hỗ trợ Bác sĩ. Hãy trả lời chuyên nghiệp, ngắn gọn."
        elif request.role.upper() == "ADMIN":
            role_instruction = "Bạn là trợ lý quản trị viên. Hãy tập trung vào số liệu."
        else:
            role_instruction = "Bạn là trợ lý y tế thân thiện của phòng khám."

        system_instruction = (
            f"{role_instruction} "
            f"Bây giờ là: {current_time}. "
            f"Dưới đây là thông tin thực tế được trích xuất từ cơ sở dữ liệu:\n"
            f"--- DỮ LIỆU HỆ THỐNG ---\n{db_context}\n--- HẾT DỮ LIỆU ---\n"
            "Hãy trả lời câu hỏi của người dùng dựa trên dữ liệu trên. "
            "Nếu dữ liệu nói 'không có lịch hẹn', hãy trả lời y như vậy. "
            "Trả lời bằng tiếng Việt."
        )

        # 3. Gọi AI qua requests (hỗ trợ cả Groq và Gemini)
        try:
            if AI_PROVIDER == "groq":
                ai_response = call_groq_api(system_instruction, request.message)
            elif AI_PROVIDER == "gemini":
                ai_response = call_gemini_api(system_instruction, request.message)
            else:
                raise ValueError(f"Invalid AI provider: {AI_PROVIDER}")
            
            return {"response": ai_response}
                    
        except requests.exceptions.Timeout:
            logger.error(f"{AI_PROVIDER.upper()} API request timeout")
            raise HTTPException(status_code=500, detail="Request timeout. Vui lòng thử lại sau.")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Không thể kết nối đến {AI_PROVIDER.upper()} API. Vui lòng kiểm tra kết nối mạng."
            )
        except Exception as e:
            logger.error(f"Unexpected error calling {AI_PROVIDER.upper()} API: {e}")
            raise HTTPException(status_code=500, detail=f"Lỗi không xác định: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)