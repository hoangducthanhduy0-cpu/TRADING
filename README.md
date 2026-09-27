# 📈 Web App Kiểm Định Chiến Lược EMA & OBV — Cổ Phiếu ACB & AI Gemini

Ứng dụng web định lượng chuyên nghiệp được xây dựng trên nền tảng **Streamlit**, phục vụ việc kiểm định hiệu quả chiến lược giao dịch kỹ thuật kết hợp giữa đường trung bình động hàm mũ (**EMA**) và chỉ báo khối lượng cân bằng (**OBV**) trên dữ liệu lịch sử cổ phiếu **ACB** (2014 – 2023), tích hợp **Trợ lý AI Google Gemini** để phân tích định lượng tự động.

---

## 🎯 1. Bối Cảnh & Điểm Mấu Chốt của Mô Hình

1. **Hạch toán vị thế chuẩn xác (Position Accounting):**
   - Khắc phục triệt để lỗi mở vị thế liên tục khi đang nắm giữ cổ phiếu hoặc gửi tín hiệu bán khi đang giữ tiền mặt.
   - Mô hình hóa chuẩn vị thế `Long-only` (1 vị thế duy nhất tại một thời điểm: Tiền mặt $\leftrightarrow$ Cổ phiếu).
2. **Khắc phục Look-ahead Bias:**
   - Tất cả tín hiệu kỹ thuật đều được dịch chuyển 1 phiên (`shift(1)`), đảm bảo chỉ dùng thông tin đóng cửa của phiên hôm trước để ra quyết định mua/bán cho phiên tiếp theo.
3. **Quản trị rủi ro & Chi phí thực tế:**
   - Cắt lỗ cố định (**Stop Loss**): 7% từ mức giá mua.
   - Phí giao dịch (**Fees**): 0.2% mỗi lượt.
   - Trượt giá (**Slippage**): 0.1% mỗi lượt.
4. **Loại bỏ bẫy Sharpe ảo (MIN_TRADES Constraint):**
   - Áp dụng điều kiện số lượng vị thế đóng tối thiểu (`MIN_TRADES >= 5`) khi tối ưu tham số để loại bỏ các trường hợp "ăn may" hoặc không giao dịch dẫn tới phương sai lợi nhuận gần bằng 0 gây Sharpe vô định (`inf`/`NaN`).
5. **Kiểm định ngoài mẫu (Out-of-sample Testing):**
   - Phân chia rõ ràng: **Tập Train (2014 – 2020)** để tìm tham số và **Tập Test (2021 – 2023)** để kiểm tra tính chống khớp quá mức (Overfitting) qua chu kỳ suy thoái 2022.
6. **🤖 Trợ lý AI Google Gemini Phân Tích Chuyên Sâu:**
   - Tích hợp trực tiếp Google Gemini API để phân tích tự động toàn bộ số liệu hiệu suất, nhận định thị trường, đánh giá mức độ Overfitting và đề xuất khuyến nghị hành động cụ thể cho phiên giao dịch gần nhất.

---

## ✨ 2. Các Tab Chức Năng Chính Trên Web App

- **Tab 1: 📊 Tổng Quan & Tín Hiệu Thời Gian Thực:**
  - Hộp khuyến nghị hành động tức thì cho phiên mới nhất: `BUY`, `HOLD`, `SELL`, hoặc `STAND ASIDE`.
  - Thẻ chỉ số hiệu suất chính: Tổng lợi nhuận, Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor.
  - Biểu đồ kỹ thuật tương tác (Plotly / Matplotlib) hiển thị giá, đường EMA, độ dốc OBV và các điểm Mua/Bán thực tế.
- **Tab 2: 🧪 Kiểm Định 3 Chiến Lược:**
  - So sánh trực quan giữa 3 chiến lược: **EMA riêng lẻ**, **OBV riêng lẻ**, và **EMA + OBV kết hợp** cùng đường chuẩn **Buy & Hold**.
  - Đồ thị đường cong vốn (Equity Curve) và biểu đồ sụt giảm vốn (Underwater Drawdown).
- **Tab 3: ⚖️ Đối Chiếu Train vs Test:**
  - Tái hiện bảng số liệu và biểu đồ so sánh đa chiều (Sharpe, Return, Drawdown) giữa hai giai đoạn thị trường.
- **Tab 4: 📝 Sổ Lệnh & Nhật Ký Giao Dịch (Trade Log):**
  - Chi tiết từng lệnh: Ngày mua, giá mua, ngày bán, giá bán, PnL (%), lý do đóng vị thế (Tín hiệu hay Stop Loss).
  - Hỗ trợ xuất dữ liệu ra file **CSV**.
- **Tab 5: ⚙️ Studio Tối Ưu Hóa Tham Số:**
  - Quét tham số đa chiều (Grid Search) trực tiếp trên giao diện với thanh tiến trình.
  - Bản đồ nhiệt (Heatmap) trực quan hóa không gian tham số Sharpe Ratio.
- **Tab 6: 🤖 AI Gemini Phân Tích Chuyên Sâu:**
  - Kết nối trực tiếp với **Google Gemini API** (`gemini-1.5-flash` / `gemini-1.5-pro`).
  - Tự động nạp dữ liệu định lượng của các chiến lược và tạo Báo Cáo Nhận Định Định Lượng toàn diện.
  - Hỗ trợ hỏi đáp thêm với AI về chiến lược và quản trị rủi ro.

---

## 📂 3. Cấu Trúc 4 File Trong Thư Mục `LAN 4`

```text
LAN 4/
│
├── ACB.csv                                      # File dữ liệu giá lịch sử cổ phiếu ACB (2014-2023)
├── app.py                                       # Mã nguồn chính Streamlit (tích hợp Gemini AI)
├── requirements.txt                             # Danh mục thư viện siêu nhẹ (plotly, matplotlib, requests)
├── requirement.txt                              # File dự phòng alias
└── README.md                                    # Hướng dẫn chi tiết dự án & cấu hình API
```

---

## 🔑 4. Hướng Dẫn Lấy & Cấu Hình Google Gemini API Key

1. **Lấy API Key miễn phí (mất 30 giây):**
   - Truy cập: [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Đăng nhập tài khoản Google $\rightarrow$ Nhấn **"Create API key"** $\rightarrow$ Sao chép khóa API.

2. **Sử dụng trên Web App:**
   - **Cách 1 (Nhập trực tiếp trên web):** Nhập khóa API vào ô *"Nhập Google Gemini API Key"* ở thanh bên trái (Sidebar).
   - **Cách 2 (Cấu hình tự động trên Streamlit Cloud):**
     + Vào phần cài đặt ứng dụng trên Streamlit Cloud: **Settings** $\rightarrow$ **Secrets**.
     + Thêm dòng:
       ```toml
       GEMINI_API_KEY = "dien_khoa_api_cua_ban_vao_day"
       ```
     + Lưu lại, web app sẽ tự động nhận diện API key mà bạn không cần nhập lại mỗi lần mở trang!

---

## 🚀 5. Hướng Dẫn Triển Khai Lên Streamlit Cloud

1. **Mở repository `trading` trên GitHub của bạn.**
2. **Tải lên 4 file từ thư mục `LAN 4`:**
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `ACB.csv`
3. **Commit changes lên nhánh `main`.**
4. **Truy cập web app trên Streamlit Cloud** $\rightarrow$ Chọn **Reboot app** để trải nghiệm phiên bản mới nhất!
