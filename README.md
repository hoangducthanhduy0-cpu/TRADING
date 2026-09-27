# 📈 Web App Kiểm Định Chiến Lược Giao Dịch: Kết Hợp EMA & OBV (Cổ Phiếu ACB)

Ứng dụng web định lượng chuyên nghiệp được xây dựng trên nền tảng **Streamlit**, phục vụ việc kiểm định hiệu quả chiến lược giao dịch kỹ thuật kết hợp giữa đường trung bình động hàm mũ (**EMA**) và chỉ báo khối lượng cân bằng (**OBV**) trên dữ liệu lịch sử cổ phiếu **ACB** (2014 – 2023).

---

## 🎯 1. Bối Cảnh & Điểm Mấu Chốt của Mô Hình

Phiên bản này được thiết kế và hoàn thiện nhằm xử lý triệt để các vấn đề học thuật trong backtesting theo chuẩn mực định lượng:

1. **Hạch toán vị thế chuẩn xác (Position Accounting):**
   - Khắc phục lỗi mở vị thế liên tục khi đang nắm giữ cổ phiếu hoặc gửi tín hiệu bán khi đang giữ tiền mặt.
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
   - Phân chia rõ ràng: **Tập Train (2014 – 2020)** để tìm tham số và **Tập Test (2021 – 2023)** để kiểm tra tính chống khớp quá mức (Overfitting) qua các chu kỳ thị trường khác nhau.

---

## ✨ 2. Các Tính Năng Chính Trên Web App

- **Tab 1: 📊 Tổng Quan & Tín Hiệu Thời Gian Thực:**
  - Hộp khuyến nghị hành động tức thì cho phiên mới nhất: `BUY`, `HOLD`, `SELL`, hoặc `STAND ASIDE`.
  - Thẻ chỉ số hiệu suất chính: Tổng lợi nhuận, Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor.
  - Biểu đồ tương tác (Plotly) hiển thị giá, đường EMA, độ dốc OBV và các điểm Mua/Bán thực tế.
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

---

## 📂 3. Cấu Trúc Thư Mục Dự Án

```text
TAO APP TRADING/
│
├── ACB.csv                                      # File dữ liệu giá lịch sử cổ phiếu ACB (2014-2023)
├── ACB_Strategy_EMA_OBV_Nhom3_Adjusted.ipynb    # Jupyter Notebook gốc đã hiệu chỉnh
├── app.py                                       # Mã nguồn chính ứng dụng Streamlit
├── requirements.txt                             # Danh mục thư viện cần thiết (Streamlit Cloud)
├── requirement.txt                              # File dự phòng alias
└── README.md                                    # Hướng dẫn chi tiết dự án
```

---

## 🚀 4. Hướng Dẫn Chạy Cục Bộ (Local Machine)

### Bước 1: Mở Terminal / PowerShell
Mở PowerShell hoặc Command Prompt tại thư mục dự án:
```bash
cd "c:\Users\HNC\Desktop\TAO APP TRADING"
```

### Bước 2: Tạo môi trường ảo (Khuyến nghị)
```bash
python -m venv venv
# Kích hoạt trên Windows:
.\venv\Scripts\activate
```

### Bước 3: Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```

### Bước 4: Khởi chạy ứng dụng Streamlit
```bash
streamlit run app.py
```
Sau khi chạy lệnh, trình duyệt web sẽ tự động mở trang web tại địa chỉ `http://localhost:8501`.

---

## 🌐 5. Hướng Dẫn Tải Lên GitHub & Deploy Lên Streamlit Cloud

### Cách 1: Đẩy mã nguồn lên GitHub bằng Git CLI

1. **Khởi tạo Git repo và commit:**
   ```bash
   git init
   git add .
   git commit -m "Khoi tao Streamlit Web App Kiem Dinh Chien Luoc EMA & OBV"
   ```

2. **Tạo repository mới trên GitHub:**
   - Truy cập [GitHub](https://github.com) $\rightarrow$ Nhấn **New Repository**.
   - Đặt tên Repository (ví dụ: `acb-trading-strategy-streamlit`), chọn chế độ **Public**.
   - Không cần tích chọn tạo sẵn README vì dự án đã có sẵn.

3. **Liên kết và đẩy code lên GitHub:**
   ```bash
   git remote add origin https://github.com/<tai-khoan-github-cua-ban>/<ten-repo>.git
   git branch -M main
   git push -u origin main
   ```

---

### Cách 2: Triển khai trực tiếp lên Streamlit Cloud (100% Miễn phí)

1. Truy cập [share.streamlit.io](https://share.streamlit.io/) và đăng nhập bằng tài khoản **GitHub**.
2. Nhấn nút **"Create app"** (hoặc **"New app"**).
3. Điền thông tin cấu hình:
   - **Repository:** Chọn repository vừa tạo (ví dụ: `<tai-khoan>/acb-trading-strategy-streamlit`).
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Nhấn nút **"Deploy!"**.
5. Đợi khoảng 1-2 phút để hệ thống tự động cài đặt các thư viện từ file `requirements.txt` và khởi chạy ứng dụng. Sau khi hoàn tất, bạn sẽ nhận được đường link web app công khai (ví dụ: `https://acb-strategy.streamlit.app`) để gửi báo cáo cho Giảng viên hoặc chia sẻ với mọi người!

---

## 📊 6. Bộ Tham Số Khuyến Nghị

Dựa trên kết quả tối ưu hóa 1,066 lần thử nghiệm trên tập dữ liệu Train (2014 – 2020):
- **Chiến lược EMA riêng lẻ:** `EMA = 36`
- **Chiến lược OBV riêng lẻ:** `OBV Slope Period = 19`
- **Chiến lược Kết Hợp EMA + OBV:** `EMA = 36`, `OBV Slope Period = 20`
- **Bộ mặc định kiểm tra:** `EMA = 20`, `OBV Slope Period = 3`

---

## 📜 7. Giấy Phép & Tuyên Bố Miễn Trừ Trách Nhiệm
Dự án được xây dựng phục vụ mục đích nghiên cứu học thuật và kiểm định định lượng. Kết quả quá khứ không bảo đảm cho lợi nhuận trong tương lai trong giao dịch chứng khoán thực tế.
