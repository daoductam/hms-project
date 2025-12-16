# AI Medical Chatbot

Chatbot y tế sử dụng Groq API hoặc Gemini API để trả lời câu hỏi của người dùng.

## Cài đặt

1. Cài đặt dependencies:

```bash
pip install fastapi uvicorn mysql-connector-python python-dotenv requests

# Nếu dùng SOCKS5 proxy, cài thêm:
pip install requests[socks]
```

2. Tạo file `.env` trong thư mục `ai_medical_chatbot`:

**Cấu hình cho Gemini API (Khuyến nghị - ổn định hơn):**

```env
# Chọn AI Provider: "groq" hoặc "gemini" (mặc định: gemini)
AI_PROVIDER=gemini

# Gemini API Key (Lấy từ: https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here

# Model Gemini (tùy chọn, mặc định: gemini-pro)
# Có thể dùng: gemini-pro, gemini-pro-vision
GEMINI_MODEL=gemini-pro
```

**Hoặc cấu hình cho Groq API:**

```env
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
```

**Cấu hình Proxy (tùy chọn - để fake IP nếu bị chặn):**

```env
USE_PROXY=false
PROXY_URL=http://proxy.example.com:8080
# Hoặc dùng SOCKS5:
# PROXY_URL=socks5://127.0.0.1:1080
```

3. Lấy API key:

   - **Gemini API**: https://aistudio.google.com/app/apikey (Khuyến nghị - miễn phí, ổn định)
   - **Groq API**: https://console.groq.com/keys

4. **Nếu bị chặn IP**, cấu hình proxy:
   - Đặt `USE_PROXY=true` trong file `.env`
   - Đặt `PROXY_URL` là địa chỉ proxy của bạn
   - Có thể dùng HTTP proxy hoặc SOCKS5 proxy
   - Nếu dùng SOCKS5, cần cài thêm: `pip install requests[socks]`
   - Ví dụ proxy miễn phí: https://www.proxy-list.download/

## Chạy ứng dụng

```bash
python app.py
```

Hoặc:

```bash
uvicorn app:app --reload --port 8000
```

## Chọn AI Provider

### Gemini API (Khuyến nghị)

- ✅ Miễn phí với hạn mức hào phóng
- ✅ Ổn định, không bị chặn IP
- ✅ Không cần proxy
- ✅ Tốc độ nhanh
- Lấy API key: https://aistudio.google.com/app/apikey

### Groq API

- ⚠️ Có thể bị chặn IP ở một số khu vực
- ⚠️ Cần proxy nếu bị chặn
- Lấy API key: https://console.groq.com/keys

## Xử lý lỗi

### Nếu dùng Groq và gặp lỗi "Access denied":

1. **Chuyển sang Gemini API** (Khuyến nghị):

   ```env
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

2. **Hoặc sử dụng Proxy để fake IP**:

   ```env
   USE_PROXY=true
   PROXY_URL=http://your-proxy-server:port
   ```

3. **Kiểm tra API key**: Đảm bảo API key trong file `.env` đúng và còn hiệu lực

### Nếu dùng Gemini và gặp lỗi:

- Kiểm tra API key có đúng không
- Kiểm tra quota/limit trên Google AI Studio
- Thử lại sau vài phút

## Lưu ý

- Code hỗ trợ cả **Groq API** và **Gemini API**
- Mặc định sử dụng **Gemini API** (ổn định hơn, không bị chặn IP)
- Có thể chuyển đổi giữa các provider bằng cách thay đổi `AI_PROVIDER` trong file `.env`
- Code đã được cập nhật để sử dụng `requests` thay vì SDK để tránh lỗi network
- Có logging chi tiết để debug
- Error handling đã được cải thiện
- Hỗ trợ proxy nếu cần fake IP (chủ yếu cho Groq)
