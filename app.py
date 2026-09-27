import sys
import subprocess
import os

# ==============================================================================
# 0. TỰ ĐỘNG CÀI ĐẶT THƯ VIỆN NẾU THIẾU (SELF-HEALING BOOTSTRAP)
# ==============================================================================
for _pkg in ["plotly", "matplotlib"]:
    try:
        __import__(_pkg)
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", _pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

import streamlit as st
import pandas as pd
import numpy as np
import io
import time
from datetime import datetime

# Kiểm tra thư viện vẽ biểu đồ Plotly
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False
    go = None
    make_subplots = None
    px = None

# Kiểm tra Matplotlib (Lớp đồ họa dự phòng an toàn tuyệt đối)
try:
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception:
    HAS_MPL = False
    plt = None


# ==============================================================================
# 1. CẤU HÌNH TRANG WEB STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Kiểm Định Chiến Lược EMA & OBV - Cổ Phiếu ACB",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho giao diện FinTech hiện đại
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(90deg, #1E88E5, #00ACC1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #6c757d;
        font-size: 1.0rem;
        margin-bottom: 1.2rem;
    }
    .signal-card {
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 15px;
        font-weight: 600;
    }
    .signal-buy {
        background-color: #e8f5e9;
        border: 1px solid #4caf50;
        color: #2e7d32;
    }
    .signal-sell {
        background-color: #ffebee;
        border: 1px solid #ef5350;
        color: #c62828;
    }
    .signal-hold {
        background-color: #e3f2fd;
        border: 1px solid #2196f3;
        color: #1565c0;
    }
    .signal-aside {
        background-color: #fafafa;
        border: 1px solid #bdbdbd;
        color: #616161;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 2. HÀM TÍNH TOÁN CHỈ BÁO THUẦN PANDAS (CHÍNH XÁC 100%, KHÔNG CẦN TA-LIB)
# ==============================================================================

def calc_ema(series, window):
    """Tính Exponential Moving Average thuần pandas (chuẩn xác từng phiên)"""
    return series.ewm(span=int(window), adjust=False).mean()


def calc_obv(close, volume):
    """Tính On-Balance Volume (OBV) thuần pandas & numpy"""
    diff = close.diff()
    direction = np.where(diff > 0, 1, np.where(diff < 0, -1, 0))
    direction[0] = 0
    return pd.Series(volume.values * direction, index=close.index).cumsum()


def get_ema_signals(data, price_col, ema_period):
    """Tín hiệu EMA: Mua khi Giá > EMA, Bán khi Giá < EMA (shift 1 phiên tránh Look-ahead)"""
    close = data[price_col]
    ema = calc_ema(close, ema_period)
    
    raw_entries = (close > ema)
    raw_exits = (close < ema)
    
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, ema


def get_obv_signals(data, price_col, obv_slope_period=3):
    """Tín hiệu OBV: Mua khi Độ dốc OBV > 0, Bán khi Độ dốc OBV < 0 (shift 1)"""
    close = data[price_col]
    volume = data['Volume']
    obv = calc_obv(close, volume)
    obv_slope = obv.diff(int(obv_slope_period))
    
    raw_entries = (obv_slope > 0)
    raw_exits = (obv_slope < 0)
    
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, obv, obv_slope


def get_ema_obv_combined_signals(data, price_col, ema_period, obv_slope_period=3):
    """Tín hiệu Kết Hợp: Mua khi Giá > EMA VÀ OBV Slope > 0; Bán khi Giá < EMA (shift 1)"""
    close = data[price_col]
    volume = data['Volume']
    
    ema = calc_ema(close, ema_period)
    obv = calc_obv(close, volume)
    obv_slope = obv.diff(int(obv_slope_period))
    
    raw_entries = (close > ema) & (obv_slope > 0)
    raw_exits = (close < ema)
    
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, ema, obv, obv_slope


# ==============================================================================
# 3. QUẢN LÝ VỊ THẾ & ENGINE BACKTEST (POSITION ACCOUNTING CHUẨN XÁC)
# ==============================================================================

def get_positions(entries, exits):
    """Hạch toán vị thế (Position Accounting) theo thời gian: Long (1) <-> Tiền mặt (0)"""
    n = len(entries)
    position = pd.Series(0, index=entries.index, dtype=int)
    buy_orders = pd.Series(False, index=entries.index, dtype=bool)
    sell_orders = pd.Series(False, index=entries.index, dtype=bool)
    
    current_pos = 0
    for i in range(n):
        if current_pos == 0 and entries.iloc[i]:
            current_pos = 1
            buy_orders.iloc[i] = True
        elif current_pos == 1 and exits.iloc[i]:
            current_pos = 0
            sell_orders.iloc[i] = True
        position.iloc[i] = current_pos
        
    return position, buy_orders, sell_orders


def run_backtest_simulation(
    df,
    price_col,
    entries,
    exits,
    initial_cash=100_000_000,
    fees=0.002,         # 0.2%
    slippage=0.001,     # 0.1%
    sl_stop=0.07        # 7% Stop loss
):
    """Mô phỏng backtest chuẩn mực: Phí, Trượt giá, Stop-loss 7%, Long-only 1 vị thế"""
    dates = df.index
    close_prices = df[price_col].values
    low_prices = df['Low'].values if 'Low' in df.columns else close_prices
    
    n = len(df)
    cash = initial_cash
    shares = 0.0
    entry_price = 0.0
    entry_date = None
    
    portfolio_value = np.zeros(n)
    positions = np.zeros(n, dtype=int)
    trades = []
    
    for i in range(n):
        curr_date = dates[i]
        curr_close = close_prices[i]
        curr_low = low_prices[i]
        
        # 1. Đang giữ cổ phiếu -> kiểm tra bán
        if shares > 0:
            stop_price = entry_price * (1.0 - sl_stop)
            is_stop_loss = (curr_low <= stop_price) or (curr_close <= stop_price)
            is_signal_exit = exits.iloc[i]
            
            if is_stop_loss or is_signal_exit:
                if is_stop_loss:
                    exit_price = min(curr_close, stop_price) * (1.0 - slippage)
                    reason = "Stop Loss (-7%)"
                else:
                    exit_price = curr_close * (1.0 - slippage)
                    reason = "Tín hiệu Exit (EMA)"
                
                gross_revenue = shares * exit_price
                net_revenue = gross_revenue * (1.0 - fees)
                cash += net_revenue
                
                pnl_val = net_revenue - (shares * entry_price * (1.0 + fees + slippage))
                pnl_pct = (exit_price / entry_price - 1.0 - 2 * fees - 2 * slippage) * 100.0
                holding_days = (curr_date - entry_date).days
                
                trades.append({
                    'Mã': 'ACB',
                    'Ngày Mua': entry_date.strftime('%Y-%m-%d'),
                    'Giá Mua': round(entry_price, 1),
                    'Ngày Bán': curr_date.strftime('%Y-%m-%d'),
                    'Giá Bán': round(exit_price, 1),
                    'Số lượng': round(shares, 2),
                    'Lợi nhuận (%)': round(pnl_pct, 2),
                    'PnL (VND)': round(pnl_val, 0),
                    'Thời gian giữ (ngày)': holding_days,
                    'Lý do đóng': reason
                })
                
                shares = 0.0
                entry_price = 0.0
                entry_date = None
        
        # 2. Đang giữ tiền mặt -> kiểm tra mua
        elif shares == 0:
            if entries.iloc[i]:
                effective_entry_price = curr_close * (1.0 + slippage)
                available_cash = cash
                max_shares = available_cash / (effective_entry_price * (1.0 + fees))
                
                if max_shares > 0:
                    shares = max_shares
                    total_buy_cost = shares * effective_entry_price * (1.0 + fees)
                    cash -= total_buy_cost
                    entry_price = effective_entry_price
                    entry_date = curr_date
        
        # 3. Định giá danh mục cuối phiên
        current_equity = cash + (shares * curr_close)
        portfolio_value[i] = current_equity
        positions[i] = 1 if shares > 0 else 0

    equity_series = pd.Series(portfolio_value, index=dates)
    position_series = pd.Series(positions, index=dates)
    trades_df = pd.DataFrame(trades)
    
    # 4. Tính toán chỉ số hiệu suất
    total_return = (equity_series.iloc[-1] / equity_series.iloc[0] - 1.0) * 100.0
    benchmark_equity = (df[price_col] / df[price_col].iloc[0]) * initial_cash
    benchmark_return = (df[price_col].iloc[-1] / df[price_col].iloc[0] - 1.0) * 100.0
    
    daily_returns = equity_series.pct_change().dropna()
    mean_ret = daily_returns.mean()
    std_ret = daily_returns.std()
    
    if std_ret > 1e-8 and len(daily_returns) > 10:
        sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0
        
    negative_returns = daily_returns[daily_returns < 0]
    downside_std = negative_returns.std()
    sortino_ratio = (mean_ret / downside_std) * np.sqrt(252) if downside_std > 1e-8 else 0.0
        
    cummax_equity = equity_series.cummax()
    drawdown = (equity_series - cummax_equity) / cummax_equity * 100.0
    max_drawdown = drawdown.min()
    calmar_ratio = abs(total_return / max_drawdown) if abs(max_drawdown) > 1e-4 else 0.0
    
    num_closed_trades = len(trades_df)
    if num_closed_trades > 0:
        winning_trades = trades_df[trades_df['Lợi nhuận (%)'] > 0]
        losing_trades = trades_df[trades_df['Lợi nhuận (%)'] <= 0]
        win_rate = (len(winning_trades) / num_closed_trades) * 100.0
        
        avg_win = winning_trades['Lợi nhuận (%)'].mean() if len(winning_trades) > 0 else 0.0
        avg_loss = losing_trades['Lợi nhuận (%)'].mean() if len(losing_trades) > 0 else 0.0
        
        sum_win = winning_trades['PnL (VND)'].sum() if len(winning_trades) > 0 else 0.0
        sum_loss = abs(losing_trades['PnL (VND)'].sum()) if len(losing_trades) > 0 else 0.0
        profit_factor = (sum_win / sum_loss) if sum_loss > 0 else (99.0 if sum_win > 0 else 0.0)
        
        expectancy = trades_df['Lợi nhuận (%)'].mean()
        avg_hold_days = trades_df['Thời gian giữ (ngày)'].mean()
    else:
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0
        profit_factor = 0.0
        expectancy = 0.0
        avg_hold_days = 0.0
        
    stats = {
        'Tổng Lợi Nhuận (%)': round(total_return, 2),
        'Lợi Nhuận Benchmark (%)': round(benchmark_return, 2),
        'Sharpe Ratio': round(sharpe_ratio, 4),
        'Sortino Ratio': round(sortino_ratio, 4),
        'Max Drawdown (%)': round(max_drawdown, 2),
        'Calmar Ratio': round(calmar_ratio, 4),
        'Số Giao Dịch': num_closed_trades,
        'Tỷ Lệ Thắng (%)': round(win_rate, 2),
        'Profit Factor': round(profit_factor, 2),
        'Lợi Nhuận Trung Bình / Lệnh (%)': round(expectancy, 2),
        'Lãi TB / Lệnh Thắng (%)': round(avg_win, 2),
        'Lỗ TB / Lệnh Thua (%)': round(avg_loss, 2),
        'Thời Gian Nắm Giữ TB (ngày)': round(avg_hold_days, 1),
        'Vốn Cuối Kỳ (VND)': round(equity_series.iloc[-1], 0)
    }
    
    return {
        'equity': equity_series,
        'benchmark_equity': benchmark_equity,
        'drawdown': drawdown,
        'positions': position_series,
        'trades': trades_df,
        'stats': stats
    }


# ==============================================================================
# 4. THANH ĐIỀU KHIỂN BÊN TRÁI (SIDEBAR)
# ==============================================================================

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2784/2784403.png", width=64)
    st.title("Bảng Điều Khiển")
    st.markdown("---")
    
    # 4.1 Nạp Dữ Liệu
    st.subheader("📁 1. Nguồn Dữ Liệu")
    uploaded_file = st.file_uploader(
        "Tải lên file CSV dữ liệu (hoặc dùng mặc định ACB.csv):",
        type=['csv']
    )
    
    @st.cache_data
    def load_data(file_source):
        if file_source is not None:
            df = pd.read_csv(file_source)
        else:
            candidates = [
                "ACB.csv",
                "LAN 1/ACB.csv",
                "LAN 2/ACB.csv",
                os.path.join(os.path.dirname(__file__), "ACB.csv") if "__file__" in globals() else "ACB.csv"
            ]
            df = None
            for p in candidates:
                if os.path.exists(p):
                    try:
                        df = pd.read_csv(p)
                        break
                    except Exception:
                        pass
            if df is None:
                for root, _, files in os.walk("."):
                    if "ACB.csv" in files:
                        try:
                            df = pd.read_csv(os.path.join(root, "ACB.csv"))
                            break
                        except Exception:
                            pass
            if df is None:
                st.error("Không tìm thấy file ACB.csv. Vui lòng tải file lên.")
                return None
                
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        return df

    df_full = load_data(uploaded_file)
    
    if df_full is not None:
        price_col = 'Close'
        min_date = df_full.index.min().date()
        max_date = df_full.index.max().date()
        st.success(f"Đã nạp {len(df_full):,} phiên ({min_date} → {max_date})")
        
        st.markdown("---")
        # 4.2 Thiết lập phân chia Train & Test
        st.subheader("📅 2. Phân Chia Tập Dữ Liệu")
        preset_choice = st.radio(
            "Chế độ kiểm định:",
            options=["Mẫu Chuẩn Notebook (Train 2014-2020, Test 2021-2023)", "Tùy Chỉnh Ngày", "Toàn Bộ Dữ Liệu (Full Sample)"]
        )
        
        if preset_choice == "Mẫu Chuẩn Notebook (Train 2014-2020, Test 2021-2023)":
            train_start, train_end = pd.to_datetime('2014-01-01').date(), pd.to_datetime('2020-12-31').date()
            test_start, test_end = pd.to_datetime('2021-01-01').date(), pd.to_datetime('2023-12-31').date()
        elif preset_choice == "Tùy Chỉnh Ngày":
            c1, c2 = st.columns(2)
            with c1:
                train_start = st.date_input("Train Từ Ngày", min_date, min_value=min_date, max_value=max_date)
            with c2:
                train_end = st.date_input("Train Đến Ngày", pd.to_datetime('2020-12-31').date(), min_value=min_date, max_value=max_date)
            c3, c4 = st.columns(2)
            with c3:
                test_start = st.date_input("Test Từ Ngày", pd.to_datetime('2021-01-01').date(), min_value=min_date, max_value=max_date)
            with c4:
                test_end = st.date_input("Test Đến Ngày", max_date, min_value=min_date, max_value=max_date)
        else: # Toàn bộ dữ liệu
            train_start, train_end = min_date, max_date
            test_start, test_end = min_date, max_date

        st.markdown("---")
        # 4.3 Cấu hình tham số chiến lược
        st.subheader("⚙️ 3. Tham Số Chiến Lược")
        
        col_preset1, col_preset2 = st.columns(2)
        with col_preset1:
            if st.button("💡 Mặc Định (20, 3)", use_container_width=True):
                st.session_state['param_ema'] = 20
                st.session_state['param_obv'] = 3
        with col_preset2:
            if st.button("🏆 Tối Ưu (36, 20)", use_container_width=True):
                st.session_state['param_ema'] = 36
                st.session_state['param_obv'] = 20

        default_ema = st.session_state.get('param_ema', 20)
        default_obv = st.session_state.get('param_obv', 3)
        
        ema_period = st.slider("Chu kỳ EMA (EMA Window)", min_value=5, max_value=80, value=default_ema, step=1)
        obv_slope_period = st.slider("Chu kỳ Độ dốc OBV (OBV Slope)", min_value=1, max_value=30, value=default_obv, step=1)

        st.markdown("---")
        # 4.4 Quản trị rủi ro & Chi phí
        with st.expander("🛡️ 4. Quản Trị Rủi Ro & Chi Phí", expanded=False):
            initial_capital = st.number_input("Vốn ban đầu (VND)", min_value=1_000_000, value=100_000_000, step=10_000_000)
            stop_loss_pct = st.slider("Cắt lỗ Stop Loss (%)", min_value=1.0, max_value=20.0, value=7.0, step=0.5) / 100.0
            fees_pct = st.slider("Phí giao dịch mỗi lượt (%)", min_value=0.0, max_value=1.0, value=0.2, step=0.05) / 100.0
            slippage_pct = st.slider("Trượt giá mỗi lượt (%)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0
            min_trades = st.number_input("Số lệnh tối thiểu (MIN_TRADES)", min_value=1, value=5, step=1)


# ==============================================================================
# 5. KHỞI TẠO DỮ LIỆU & TÍNH TOÁN CÁC CHIẾN LƯỢC
# ==============================================================================

if df_full is None:
    st.info("👋 Vui lòng tải file ACB.csv lên từ thanh bên trái.")
    st.stop()

# Cắt tập dữ liệu Train và Test
train_df = df_full.loc[str(train_start):str(train_end)].copy()
test_df = df_full.loc[str(test_start):str(test_end)].copy()

if len(train_df) < 30:
    st.warning("⚠️ Tập Train quá ngắn để tính toán các chỉ báo. Vui lòng chọn khoảng thời gian rộng hơn.")
    st.stop()

# Tính toán tín hiệu cho tập Train
train_ent_ema, train_ext_ema, train_ema_val = get_ema_signals(train_df, price_col, ema_period)
train_ent_obv, train_ext_obv, train_obv_val, train_obvs_val = get_obv_signals(train_df, price_col, obv_slope_period)
train_ent_comb, train_ext_comb, _, _, _ = get_ema_obv_combined_signals(train_df, price_col, ema_period, obv_slope_period)

# Backtest trên tập Train
res_train_ema = run_backtest_simulation(train_df, price_col, train_ent_ema, train_ext_ema, initial_capital, fees_pct, slippage_pct, stop_loss_pct)
res_train_obv = run_backtest_simulation(train_df, price_col, train_ent_obv, train_ext_obv, initial_capital, fees_pct, slippage_pct, stop_loss_pct)
res_train_comb = run_backtest_simulation(train_df, price_col, train_ent_comb, train_ext_comb, initial_capital, fees_pct, slippage_pct, stop_loss_pct)

# Tính toán tín hiệu cho tập Test (nếu có dữ liệu Test)
has_test = len(test_df) >= 30 and preset_choice != "Toàn Bộ Dữ Liệu (Full Sample)"
if has_test:
    test_ent_ema, test_ext_ema, test_ema_val = get_ema_signals(test_df, price_col, ema_period)
    test_ent_obv, test_ext_obv, test_obv_val, test_obvs_val = get_obv_signals(test_df, price_col, obv_slope_period)
    test_ent_comb, test_ext_comb, _, _, _ = get_ema_obv_combined_signals(test_df, price_col, ema_period, obv_slope_period)
    
    res_test_ema = run_backtest_simulation(test_df, price_col, test_ent_ema, test_ext_ema, initial_capital, fees_pct, slippage_pct, stop_loss_pct)
    res_test_obv = run_backtest_simulation(test_df, price_col, test_ent_obv, test_ext_obv, initial_capital, fees_pct, slippage_pct, stop_loss_pct)
    res_test_comb = run_backtest_simulation(test_df, price_col, test_ent_comb, test_ext_comb, initial_capital, fees_pct, slippage_pct, stop_loss_pct)


# ==============================================================================
# 6. HEADER CHÍNH CỦA ỨNG DỤNG
# ==============================================================================

st.markdown('<div class="main-title">Hệ Thống Kiểm Định Chiến Lược Giao Dịch: EMA & OBV</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Nghiên cứu & Đánh giá định lượng trên Cổ phiếu ACB — Hạch toán vị thế chuẩn xác, Phòng tránh Look-ahead Bias & Bẫy Sharpe ảo</div>', unsafe_allow_html=True)

# Khuyến nghị Tín hiệu Thực chiến Phiên Mới Nhất
latest_date = df_full.index[-1].strftime('%d/%m/%Y')
latest_close = df_full[price_col].iloc[-1]
full_ent_comb, full_ext_comb, full_ema, full_obv, full_obv_slope = get_ema_obv_combined_signals(df_full, price_col, ema_period, obv_slope_period)
pos_full, buy_orders_full, sell_orders_full = get_positions(full_ent_comb, full_ext_comb)
curr_pos = pos_full.iloc[-1]
today_entry = full_ent_comb.iloc[-1]
today_exit = full_ext_comb.iloc[-1]

if curr_pos == 1:
    if today_exit:
        signal_status = "🔴 BÁN RA (SELL) — Tín hiệu đảo chiều vi phạm đường EMA, đóng vị thế ngay!"
        css_class = "signal-sell"
    else:
        signal_status = "🟢 TIẾP TỤC NẮM GIỮ (HOLD) — Giá duy trì trên EMA và xu hướng thuận lợi."
        css_class = "signal-hold"
else:
    if today_entry:
        signal_status = "🚀 MUA VÀO (BUY) — Thỏa mãn đồng thời Giá vượt EMA và Độ dốc OBV tăng!"
        css_class = "signal-buy"
    else:
        signal_status = "⚪ ĐỨNG NGOÀI QUAN SÁT (STAND ASIDE) — Đang giữ tiền mặt, chưa xuất hiện điểm mua."
        css_class = "signal-aside"

st.markdown(f"""
<div class="signal-card {css_class}">
    <strong>📅 Cập nhật phiên {latest_date} | Giá đóng cửa: {latest_close:,.1f} VND</strong><br>
    Trạng thái vị thế hiện tại: <strong>{"ĐANG NẮM GIỮ CỔ PHIẾU (LONG)" if curr_pos == 1 else "ĐANG GIỮ TIỀN MẶT (CASH)"}</strong><br>
    Khuyến nghị hệ thống: <strong>{signal_status}</strong>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# 7. CÁC TABS CHỨC NĂNG CHÍNH
# ==============================================================================

tabs = st.tabs([
    "📊 1. Tổng Quan & Tín Hiệu",
    "🧪 2. Kiểm Định 3 Chiến Lược",
    "⚖️ 3. Đối Chiếu Train vs Test (Tránh Overfitting)",
    "📝 4. Sổ Lệnh (Trade Log)",
    "⚙️ 5. Tối Ưu Hóa Tham Số (Studio)"
])


# ------------------------------------------------------------------------------
# TAB 1: TỔNG QUAN & TÍN HIỆU THỜI GIAN THỰC
# ------------------------------------------------------------------------------
with tabs[0]:
    st.subheader("📌 Chỉ Số Hiệu Suất Chiến Lược Kết Hợp (EMA + OBV) trên Tập Kiểm Thử")
    
    active_res = res_test_comb if has_test else res_train_comb
    active_dataset_name = "Tập Test (Out-of-sample)" if has_test else "Tập Train (In-sample)"
    st.caption(f"Dữ liệu hiển thị bên dưới áp dụng cho: **{active_dataset_name}** | EMA = {ema_period}, OBV Slope = {obv_slope_period}")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            label="Tổng Lợi Nhuận (%)",
            value=f"{active_res['stats']['Tổng Lợi Nhuận (%)']}%",
            delta=f"{round(active_res['stats']['Tổng Lợi Nhuận (%)'] - active_res['stats']['Lợi Nhuận Benchmark (%)'], 2)}% vs Buy&Hold"
        )
    with col2:
        st.metric(
            label="Sharpe Ratio",
            value=f"{active_res['stats']['Sharpe Ratio']}",
            delta="Hàng năm hóa (252 ngày)"
        )
    with col3:
        st.metric(
            label="Max Drawdown (%)",
            value=f"{active_res['stats']['Max Drawdown (%)']}%",
            delta="Sụt giảm lớn nhất",
            delta_color="inverse"
        )
    with col4:
        st.metric(
            label="Tỷ Lệ Thắng (Win Rate)",
            value=f"{active_res['stats']['Tỷ Lệ Thắng (%)']}%",
            delta=f"{active_res['stats']['Số Giao Dịch']} lệnh đã đóng"
        )
    with col5:
        st.metric(
            label="Profit Factor",
            value=f"{active_res['stats']['Profit Factor']}",
            delta=f"Kỳ vọng: {active_res['stats']['Lợi Nhuận Trung Bình / Lệnh (%)']}%/lệnh"
        )

    st.markdown("---")
    st.subheader("📈 Biểu Đồ Giá Kỹ Thuật, Chỉ Báo & Điểm Mua/Bán Thực Tế")
    
    plot_df = test_df if has_test else train_df
    plot_ema = test_ema_val if has_test else train_ema_val
    plot_obv_slope = test_obvs_val if has_test else train_obvs_val
    plot_trades = active_res['trades']

    # VẼ BIỂU ĐỒ TƯƠNG TÁC (PLOTLY HOẶC MATPLOTLIB FALLBACK)
    if HAS_PLOTLY:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=("Biểu đồ Giá ACB & Đường Trung Bình Động EMA kèm Điểm Giao Dịch", "Chỉ báo Độ dốc On-Balance Volume (OBV Slope)")
        )

        fig.add_trace(go.Scatter(
            x=plot_df.index, y=plot_df[price_col],
            mode='lines', name='Giá Đóng Cửa (Close)',
            line=dict(color='#2962FF', width=1.5)
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=plot_df.index, y=plot_ema,
            mode='lines', name=f'EMA ({ema_period})',
            line=dict(color='#FF6D00', width=1.5, dash='dash')
        ), row=1, col=1)

        if len(plot_trades) > 0:
            buy_dates = pd.to_datetime(plot_trades['Ngày Mua'])
            buy_prices = plot_trades['Giá Mua']
            sell_dates = pd.to_datetime(plot_trades['Ngày Bán'])
            sell_prices = plot_trades['Giá Bán']

            fig.add_trace(go.Scatter(
                x=buy_dates, y=buy_prices,
                mode='markers', name='Điểm MUA (Buy)',
                marker=dict(symbol='triangle-up', size=11, color='#00C853', line=dict(width=1, color='black'))
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=sell_dates, y=sell_prices,
                mode='markers', name='Điểm BÁN (Sell)',
                marker=dict(symbol='triangle-down', size=11, color='#D50000', line=dict(width=1, color='black'))
            ), row=1, col=1)

        colors = ['#00C853' if v > 0 else '#D50000' for v in plot_obv_slope.fillna(0)]
        fig.add_trace(go.Bar(
            x=plot_df.index, y=plot_obv_slope,
            name=f'OBV Slope ({obv_slope_period})',
            marker_color=colors
        ), row=2, col=1)

        fig.update_layout(
            height=600,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        fig.update_yaxes(title_text="Giá (VND)", row=1, col=1)
        fig.update_yaxes(title_text="Độ dốc OBV", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)
    elif HAS_MPL:
        # Fallback bằng Matplotlib nếu máy chủ chưa có Plotly
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        ax1.plot(plot_df.index, plot_df[price_col], label='Giá Đóng Cửa', color='#1E88E5', lw=1.5)
        ax1.plot(plot_df.index, plot_ema, label=f'EMA ({ema_period})', color='#FF8F00', linestyle='--', lw=1.5)
        
        if len(plot_trades) > 0:
            ax1.scatter(pd.to_datetime(plot_trades['Ngày Mua']), plot_trades['Giá Mua'], marker='^', color='green', s=60, label='MUA', zorder=5)
            ax1.scatter(pd.to_datetime(plot_trades['Ngày Bán']), plot_trades['Giá Bán'], marker='v', color='red', s=60, label='BÁN', zorder=5)
            
        ax1.set_title("Biểu đồ Giá ACB, EMA và Điểm Mua/Bán", fontsize=12, fontweight='bold')
        ax1.set_ylabel("Giá (VND)")
        ax1.legend(loc='upper left')
        ax1.grid(True, linestyle=':', alpha=0.6)
        
        colors = ['green' if v > 0 else 'red' for v in plot_obv_slope.fillna(0)]
        ax2.bar(plot_df.index, plot_obv_slope, color=colors, width=1.5)
        ax2.set_title(f"Độ dốc OBV ({obv_slope_period} phiên)", fontsize=10)
        ax2.grid(True, linestyle=':', alpha=0.6)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.line_chart(pd.DataFrame({'Giá ACB': plot_df[price_col], f'EMA ({ema_period})': plot_ema}))


# ------------------------------------------------------------------------------
# TAB 2: KIỂM ĐỊNH HIỆU SUẤT & SO SÁNH 3 CHIẾN LƯỢC
# ------------------------------------------------------------------------------
with tabs[1]:
    st.subheader("⚖️ So Sánh Hiệu Quả: EMA Riêng Lẻ vs OBV Riêng Lẻ vs EMA+OBV Kết Hợp")
    st.caption("Cả 3 chiến lược được kiểm tra trong cùng điều kiện: Long-only, chi phí 0.2%, trượt giá 0.1%, cắt lỗ 7%.")
    
    target_data_type = st.radio("Chọn tập dữ liệu đánh giá:", options=["Tập Train (2014-2020)", "Tập Test (2021-2023)"] if has_test else ["Tập Train (In-sample)"], horizontal=True)
    
    if "Train" in target_data_type:
        eval_ema, eval_obv, eval_comb = res_train_ema, res_train_obv, res_train_comb
        eval_df = train_df
    else:
        eval_ema, eval_obv, eval_comb = res_test_ema, res_test_obv, res_test_comb
        eval_df = test_df

    # 1. Bảng So Sánh Chỉ Số Chi Tiết
    metrics_summary = pd.DataFrame({
        'Chỉ Số Đánh Giá': [
            'Tổng Lợi Nhuận (%)',
            'Lợi Nhuận Benchmark Buy&Hold (%)',
            'Sharpe Ratio (Hàng năm)',
            'Sortino Ratio',
            'Max Drawdown (%)',
            'Calmar Ratio',
            'Tỷ Lệ Thắng (Win Rate %)',
            'Số Lệnh Đã Đóng',
            'Profit Factor',
            'Lãi TB / Lệnh (%)',
            'Thời Gian Giữ Lệnh TB (ngày)',
            'Vốn Cuối Kỳ (VND)'
        ],
        'Chiến Lược EMA Riêng': [
            f"{eval_ema['stats']['Tổng Lợi Nhuận (%)']}%",
            f"{eval_ema['stats']['Lợi Nhuận Benchmark (%)']}%",
            eval_ema['stats']['Sharpe Ratio'],
            eval_ema['stats']['Sortino Ratio'],
            f"{eval_ema['stats']['Max Drawdown (%)']}%",
            eval_ema['stats']['Calmar Ratio'],
            f"{eval_ema['stats']['Tỷ Lệ Thắng (%)']}%",
            eval_ema['stats']['Số Giao Dịch'],
            eval_ema['stats']['Profit Factor'],
            f"{eval_ema['stats']['Lợi Nhuận Trung Bình / Lệnh (%)']}%",
            eval_ema['stats']['Thời Gian Nắm Giữ TB (ngày)'],
            f"{eval_ema['stats']['Vốn Cuối Kỳ (VND)']:,.0f}"
        ],
        'Chiến Lược OBV Riêng': [
            f"{eval_obv['stats']['Tổng Lợi Nhuận (%)']}%",
            f"{eval_obv['stats']['Lợi Nhuận Benchmark (%)']}%",
            eval_obv['stats']['Sharpe Ratio'],
            eval_obv['stats']['Sortino Ratio'],
            f"{eval_obv['stats']['Max Drawdown (%)']}%",
            eval_obv['stats']['Calmar Ratio'],
            f"{eval_obv['stats']['Tỷ Lệ Thắng (%)']}%",
            eval_obv['stats']['Số Giao Dịch'],
            eval_obv['stats']['Profit Factor'],
            f"{eval_obv['stats']['Lợi Nhuận Trung Bình / Lệnh (%)']}%",
            eval_obv['stats']['Thời Gian Nắm Giữ TB (ngày)'],
            f"{eval_obv['stats']['Vốn Cuối Kỳ (VND)']:,.0f}"
        ],
        'Chiến Lược KẾT HỢP (EMA+OBV)': [
            f"{eval_comb['stats']['Tổng Lợi Nhuận (%)']}%",
            f"{eval_comb['stats']['Lợi Nhuận Benchmark (%)']}%",
            eval_comb['stats']['Sharpe Ratio'],
            eval_comb['stats']['Sortino Ratio'],
            f"{eval_comb['stats']['Max Drawdown (%)']}%",
            eval_comb['stats']['Calmar Ratio'],
            f"{eval_comb['stats']['Tỷ Lệ Thắng (%)']}%",
            eval_comb['stats']['Số Giao Dịch'],
            eval_comb['stats']['Profit Factor'],
            f"{eval_comb['stats']['Lợi Nhuận Trung Bình / Lệnh (%)']}%",
            eval_comb['stats']['Thời Gian Nắm Giữ TB (ngày)'],
            f"{eval_comb['stats']['Vốn Cuối Kỳ (VND)']:,.0f}"
        ]
    })
    
    st.dataframe(metrics_summary, use_container_width=True, hide_index=True)

    # 2. Biểu đồ Đường Cong Vốn (Equity Curve)
    st.markdown("#### 💰 Biểu Đồ Tăng Trưởng Tài Khoản (Equity Curve)")
    if HAS_PLOTLY:
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(x=eval_df.index, y=eval_comb['equity'], mode='lines', name=f'EMA+OBV Kết Hợp', line=dict(color='#00C853', width=2.5)))
        fig_equity.add_trace(go.Scatter(x=eval_df.index, y=eval_ema['equity'], mode='lines', name=f'EMA Riêng Lẻ', line=dict(color='#2962FF', width=1.5, dash='dot')))
        fig_equity.add_trace(go.Scatter(x=eval_df.index, y=eval_obv['equity'], mode='lines', name=f'OBV Riêng Lẻ', line=dict(color='#FF6D00', width=1.5, dash='dash')))
        fig_equity.add_trace(go.Scatter(x=eval_df.index, y=eval_comb['benchmark_equity'], mode='lines', name=f'Mua & Nắm Giữ (Buy & Hold)', line=dict(color='#757575', width=1.5, dash='dashdot')))
        fig_equity.update_layout(height=450, margin=dict(l=20, r=20, t=30, b=20), xaxis_title="Thời Gian", yaxis_title="Giá Trị Danh Mục (VND)", hovermode="x unified")
        st.plotly_chart(fig_equity, use_container_width=True)
    elif HAS_MPL:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(eval_df.index, eval_comb['equity'], label='EMA+OBV Kết Hợp', color='green', lw=2)
        ax.plot(eval_df.index, eval_ema['equity'], label='EMA Riêng', color='blue', lw=1.2, linestyle=':')
        ax.plot(eval_df.index, eval_obv['equity'], label='OBV Riêng', color='orange', lw=1.2, linestyle='--')
        ax.plot(eval_df.index, eval_comb['benchmark_equity'], label='Buy & Hold', color='gray', lw=1.2, linestyle='-.')
        ax.set_ylabel("Giá Trị Danh Mục (VND)")
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.6)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.line_chart(pd.DataFrame({'EMA+OBV': eval_comb['equity'], 'EMA': eval_ema['equity'], 'OBV': eval_obv['equity'], 'Buy&Hold': eval_comb['benchmark_equity']}))

    # 3. Biểu đồ Sụt Giảm Vốn (Drawdown Underwater Plot)
    st.markdown("#### 🌊 Biểu Đồ Mức Sụt Giảm Vốn Tối Đa (Drawdown Underwater)")
    if HAS_PLOTLY:
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(x=eval_df.index, y=eval_comb['drawdown'], mode='lines', fill='tozeroy', name='EMA + OBV Kết Hợp', line=dict(color='#00C853', width=1)))
        fig_dd.add_trace(go.Scatter(x=eval_df.index, y=eval_ema['drawdown'], mode='lines', name='EMA Riêng', line=dict(color='#2962FF', width=1)))
        fig_dd.add_trace(go.Scatter(x=eval_df.index, y=eval_obv['drawdown'], mode='lines', name='OBV Riêng', line=dict(color='#FF6D00', width=1)))
        fig_dd.update_layout(height=320, margin=dict(l=20, r=20, t=30, b=20), xaxis_title="Thời Gian", yaxis_title="Sụt Giảm (%)", hovermode="x unified")
        st.plotly_chart(fig_dd, use_container_width=True)
    elif HAS_MPL:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.fill_between(eval_df.index, eval_comb['drawdown'], 0, color='green', alpha=0.3, label='EMA+OBV')
        ax.plot(eval_df.index, eval_ema['drawdown'], color='blue', lw=1, label='EMA')
        ax.plot(eval_df.index, eval_obv['drawdown'], color='orange', lw=1, label='OBV')
        ax.set_ylabel("Sụt Giảm (%)")
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.6)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.area_chart(pd.DataFrame({'EMA+OBV Drawdown (%)': eval_comb['drawdown']}))


# ------------------------------------------------------------------------------
# TAB 3: ĐỐI CHIẾU TRAIN VS TEST (TÁI HIỆN NOTEBOOK CELL 23)
# ------------------------------------------------------------------------------
with tabs[2]:
    st.subheader("⚖️ Kiểm Định Ngoài Mẫu (Out-of-Sample): Tập Train vs Tập Test")
    st.markdown("""
    > **Mục tiêu học thuật:** Một chiến lược tốt không chỉ có chỉ số cao trên dữ liệu đã biết (Train 2014-2020) 
    > mà phải duy trì được hiệu quả hoặc kiểm soát tốt rủi ro trên dữ liệu chưa từng thấy (Test 2021-2023), 
    > giúp phát hiện hiện tượng **Overfitting (Khớp quá mức)**.
    """)

    if not has_test:
        st.warning("Vui lòng chọn chế độ phân chia có cả tập Train và tập Test ở thanh bên trái để hiển thị bảng so sánh.")
    else:
        comparison_records = [
            {'Chiến lược': 'EMA Riêng lẻ', 'Tập dữ liệu': 'Train', 'Tham số': f'EMA={ema_period}', 
             'Sharpe Ratio': res_train_ema['stats']['Sharpe Ratio'], 'Tổng lợi nhuận (%)': res_train_ema['stats']['Tổng Lợi Nhuận (%)'], 
             'Max Drawdown (%)': res_train_ema['stats']['Max Drawdown (%)'], 'Số giao dịch đã đóng': res_train_ema['stats']['Số Giao Dịch']},
            {'Chiến lược': 'EMA Riêng lẻ', 'Tập dữ liệu': 'Test', 'Tham số': f'EMA={ema_period}', 
             'Sharpe Ratio': res_test_ema['stats']['Sharpe Ratio'], 'Tổng lợi nhuận (%)': res_test_ema['stats']['Tổng Lợi Nhuận (%)'], 
             'Max Drawdown (%)': res_test_ema['stats']['Max Drawdown (%)'], 'Số giao dịch đã đóng': res_test_ema['stats']['Số Giao Dịch']},
            
            {'Chiến lược': 'OBV Riêng lẻ', 'Tập dữ liệu': 'Train', 'Tham số': f'OBV_Slope={obv_slope_period}', 
             'Sharpe Ratio': res_train_obv['stats']['Sharpe Ratio'], 'Tổng lợi nhuận (%)': res_train_obv['stats']['Tổng Lợi Nhuận (%)'], 
             'Max Drawdown (%)': res_train_obv['stats']['Max Drawdown (%)'], 'Số giao dịch đã đóng': res_train_obv['stats']['Số Giao Dịch']},
            {'Chiến lược': 'OBV Riêng lẻ', 'Tập dữ liệu': 'Test', 'Tham số': f'OBV_Slope={obv_slope_period}', 
             'Sharpe Ratio': res_test_obv['stats']['Sharpe Ratio'], 'Tổng lợi nhuận (%)': res_test_obv['stats']['Tổng Lợi Nhuận (%)'], 
             'Max Drawdown (%)': res_test_obv['stats']['Max Drawdown (%)'], 'Số giao dịch đã đóng': res_test_obv['stats']['Số Giao Dịch']},
            
            {'Chiến lược': 'EMA + OBV Kết hợp', 'Tập dữ liệu': 'Train', 'Tham số': f'EMA={ema_period}, OBV_Slope={obv_slope_period}', 
             'Sharpe Ratio': res_train_comb['stats']['Sharpe Ratio'], 'Tổng lợi nhuận (%)': res_train_comb['stats']['Tổng Lợi Nhuận (%)'], 
             'Max Drawdown (%)': res_train_comb['stats']['Max Drawdown (%)'], 'Số giao dịch đã đóng': res_train_comb['stats']['Số Giao Dịch']},
            {'Chiến lược': 'EMA + OBV Kết hợp', 'Tập dữ liệu': 'Test', 'Tham số': f'EMA={ema_period}, OBV_Slope={obv_slope_period}', 
             'Sharpe Ratio': res_test_comb['stats']['Sharpe Ratio'], 'Tổng lợi nhuận (%)': res_test_comb['stats']['Tổng Lợi Nhuận (%)'], 
             'Max Drawdown (%)': res_test_comb['stats']['Max Drawdown (%)'], 'Số giao dịch đã đóng': res_test_comb['stats']['Số Giao Dịch']}
        ]
        comp_df = pd.DataFrame(comparison_records)

        st.markdown("#### 📋 Bảng Đối Chiếu Hiệu Suất Train vs Test")
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        st.markdown("#### 📊 Đồ Thị So Sánh Trực Quan: Sharpe, Lợi Nhuận & Sụt Giảm Tối Đa")
        
        if HAS_PLOTLY:
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                fig_bar_sharpe = px.bar(comp_df, x='Chiến lược', y='Sharpe Ratio', color='Tập dữ liệu', barmode='group', text_auto='.2f', title='Sharpe Ratio (Hàng năm)')
                st.plotly_chart(fig_bar_sharpe, use_container_width=True)
            with c_p2:
                fig_bar_ret = px.bar(comp_df, x='Chiến lược', y='Tổng lợi nhuận (%)', color='Tập dữ liệu', barmode='group', text_auto='.1f', title='Tổng Lợi Nhuận (%)')
                st.plotly_chart(fig_bar_ret, use_container_width=True)
            with c_p3:
                fig_bar_mdd = px.bar(comp_df, x='Chiến lược', y='Max Drawdown (%)', color='Tập dữ liệu', barmode='group', text_auto='.1f', title='Max Drawdown (%)')
                st.plotly_chart(fig_bar_mdd, use_container_width=True)
        elif HAS_MPL:
            fig, axes = plt.subplots(1, 3, figsize=(14, 4))
            for i, (metric, title) in enumerate([('Sharpe Ratio', 'Sharpe Ratio'), ('Tổng lợi nhuận (%)', 'Tổng Lợi Nhuận (%)'), ('Max Drawdown (%)', 'Max Drawdown (%)')]):
                ax = axes[i]
                pivot_m = comp_df.pivot(index='Chiến lược', columns='Tập dữ liệu', values=metric)
                pivot_m.plot(kind='bar', ax=ax, colormap='viridis')
                ax.set_title(title, fontweight='bold')
                ax.grid(True, linestyle=':', alpha=0.6)
                ax.tick_params(axis='x', rotation=15)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        st.info("""
        💡 **Nhận định định lượng từ kết quả nghiên cứu:**
        - **Giai đoạn Train (2014-2020)**: Thị trường chứng khoán Việt Nam và ACB trải qua xu hướng tăng trưởng mạnh (Uptrend), cả 3 chiến lược đều mang lại lợi nhuận vượt trội (> 200%) với Sharpe Ratio > 1.0.
        - **Giai đoạn Test (2021-2023)**: Bao gồm chu kỳ suy thoái mạnh năm 2022 (Downtrend sâu). Lợi nhuận của các chiến lược bám theo xu hướng (Trend Following) đều bị ảnh hưởng sụt giảm, dẫn tới Sharpe âm.
        - **Chiến lược Kết Hợp EMA + OBV** phát huy vai trò phòng thủ khi **hạn chế số lượng lệnh giao dịch sai (whipsaw)** và giảm thiểu độ sâu sụt giảm tài khoản (Max Drawdown) so với việc chỉ sử dụng một chỉ báo đơn lẻ.
        """)


# ------------------------------------------------------------------------------
# TAB 4: SỔ LỆNH & NHẬT KÝ GIAO DỊCH (TRADE LOG)
# ------------------------------------------------------------------------------
with tabs[3]:
    st.subheader("📑 Nhật Ký Lệnh Giao Dịch Chi Tiết (Trade Log)")
    st.caption("Minh bạch hóa toàn bộ các lệnh Mua/Bán đã đóng trong suốt thời gian kiểm định.")
    
    trade_source = st.radio("Xem sổ lệnh của:", options=["Chiến Lược Kết Hợp (EMA+OBV)", "Chiến Lược EMA Riêng", "Chiến Lược OBV Riêng"], horizontal=True)
    
    if trade_source == "Chiến Lược Kết Hợp (EMA+OBV)":
        active_trades_df = active_res['trades']
    elif trade_source == "Chiến Lược EMA Riêng":
        active_trades_df = (res_test_ema if has_test else res_train_ema)['trades']
    else:
        active_trades_df = (res_test_obv if has_test else res_train_obv)['trades']

    if len(active_trades_df) == 0:
        st.warning("Không có giao dịch nào được đóng trong khoảng thời gian này.")
    else:
        c_tr1, c_tr2, c_tr3, c_tr4 = st.columns(4)
        with c_tr1:
            st.metric("Tổng Số Lệnh", f"{len(active_trades_df)}")
        with c_tr2:
            win_count = len(active_trades_df[active_trades_df['Lợi nhuận (%)'] > 0])
            st.metric("Lệnh Thắng", f"{win_count} ({round(win_count/len(active_trades_df)*100, 1)}%)")
        with c_tr3:
            loss_count = len(active_trades_df[active_trades_df['Lợi nhuận (%)'] <= 0])
            st.metric("Lệnh Thua", f"{loss_count} ({round(loss_count/len(active_trades_df)*100, 1)}%)")
        with c_tr4:
            st.metric("Lợi Nhuận Tốt Nhất", f"{active_trades_df['Lợi nhuận (%)'].max()}%")

        csv_buffer = io.StringIO()
        active_trades_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Tải xuống Sổ Lệnh (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"ACB_Trade_Log_{trade_source.replace(' ', '_')}.csv",
            mime="text/csv"
        )

        st.dataframe(
            active_trades_df.style.map(
                lambda val: 'color: #00C853; font-weight: bold;' if isinstance(val, (int, float)) and val > 0 
                else ('color: #D50000; font-weight: bold;' if isinstance(val, (int, float)) and val < 0 else ''),
                subset=['Lợi nhuận (%)', 'PnL (VND)']
            ),
            use_container_width=True,
            height=380
        )

        st.markdown("#### 📊 Phân Bổ Lợi Nhuận Từng Giao Dịch (%)")
        if HAS_PLOTLY:
            fig_hist = px.histogram(active_trades_df, x="Lợi nhuận (%)", nbins=25, color_discrete_sequence=['#1E88E5'], marginal="box")
            fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig_hist, use_container_width=True)
        elif HAS_MPL:
            fig, ax = plt.subplots(figsize=(8, 3.5))
            ax.hist(active_trades_df['Lợi nhuận (%)'], bins=20, color='#1E88E5', edgecolor='black', alpha=0.7)
            ax.axvline(0, color='red', linestyle='--')
            ax.set_xlabel("Lợi Nhuận (%)")
            ax.set_ylabel("Số Lệnh")
            ax.grid(True, linestyle=':', alpha=0.6)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)


# ------------------------------------------------------------------------------
# TAB 5: STUDIO TỐI ƯU HÓA THAM SỐ (HYPERPARAMETER OPTIMIZATION)
# ------------------------------------------------------------------------------
with tabs[4]:
    st.subheader("🎯 Tối Ưu Hóa Tham Số Chiến Lược (Hyperparameter Optimization)")
    st.markdown("""
    Tìm kiếm cặp tham số `(EMA Period, OBV Slope)` tối ưu hóa **Sharpe Ratio** 
    trên tập **Train**, đồng thời ràng buộc **`MIN_TRADES >= 5`** để loại bỏ các tham số ảo 
    không thực hiện giao dịch (đúng theo góp ý sửa lỗi của Giảng viên).
    """)

    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        ema_min = st.number_input("EMA tối thiểu", min_value=5, max_value=40, value=10)
        ema_max = st.number_input("EMA tối đa", min_value=15, max_value=80, value=40)
        ema_step = st.number_input("Bước nhảy EMA", min_value=1, max_value=10, value=2)
    with opt_col2:
        obv_min = st.number_input("OBV Slope tối thiểu", min_value=2, max_value=10, value=2)
        obv_max = st.number_input("OBV Slope tối đa", min_value=5, max_value=30, value=20)
        obv_step = st.number_input("Bước nhảy OBV Slope", min_value=1, max_value=5, value=2)

    if st.button("🚀 Bắt Đầu Quét Tối Ưu Lưới Tham Số (Grid Search)", type="primary"):
        ema_range = range(int(ema_min), int(ema_max) + 1, int(ema_step))
        obv_range = range(int(obv_min), int(obv_max) + 1, int(obv_step))
        total_combos = len(ema_range) * len(obv_range)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        counter = 0
        start_time = time.time()
        
        for e in ema_range:
            for o in obv_range:
                counter += 1
                progress_bar.progress(counter / total_combos)
                status_text.text(f"Đang kiểm tra {counter}/{total_combos}: EMA={e}, OBV_Slope={o}...")
                
                ent, ext, _, _, _ = get_ema_obv_combined_signals(train_df, price_col, e, o)
                sim = run_backtest_simulation(train_df, price_col, ent, ext, initial_capital, fees_pct, slippage_pct, stop_loss_pct)
                
                n_trades = sim['stats']['Số Giao Dịch']
                sharpe = sim['stats']['Sharpe Ratio']
                tot_ret = sim['stats']['Tổng Lợi Nhuận (%)']
                mdd = sim['stats']['Max Drawdown (%)']
                
                is_valid = (n_trades >= min_trades) and np.isfinite(sharpe)
                
                results.append({
                    'EMA': e,
                    'OBV_Slope': o,
                    'Sharpe Ratio': sharpe if is_valid else -999.0,
                    'Tổng Lợi Nhuận (%)': tot_ret,
                    'Max Drawdown (%)': mdd,
                    'Số Giao Dịch': n_trades,
                    'Hợp Lệ': is_valid
                })
                
        elapsed = round(time.time() - start_time, 2)
        progress_bar.empty()
        status_text.empty()
        st.success(f"✅ Hoàn thành quét {total_combos} bộ tham số trong {elapsed} giây!")
        
        opt_df = pd.DataFrame(results)
        valid_opt_df = opt_df[opt_df['Hợp Lệ'] == True].sort_values(by='Sharpe Ratio', ascending=False)
        
        if len(valid_opt_df) > 0:
            best_row = valid_opt_df.iloc[0]
            st.markdown(f"""
            ### 🏆 Bộ Tham Số Tối Ưu Tìm Được (Train):
            - **Chu kỳ EMA**: `{int(best_row['EMA'])}`
            - **Chu kỳ OBV Slope**: `{int(best_row['OBV_Slope'])}`
            - **Sharpe Ratio**: `{best_row['Sharpe Ratio']:.4f}`
            - **Tổng Lợi Nhuận**: `{best_row['Tổng Lợi Nhuận (%)']:.2f}%`
            - **Max Drawdown**: `{best_row['Max Drawdown (%)']:.2f}%`
            - **Số Giao Dịch**: `{int(best_row['Số Giao Dịch'])}` (thỏa mãn >= {min_trades} lệnh)
            """)

            pivot_sharpe = opt_df.pivot(index='OBV_Slope', columns='EMA', values='Sharpe Ratio')
            if HAS_PLOTLY:
                fig_heat = px.imshow(
                    pivot_sharpe,
                    labels=dict(x="Chu kỳ EMA", y="Chu kỳ OBV Slope", color="Sharpe Ratio"),
                    x=pivot_sharpe.columns, y=pivot_sharpe.index,
                    color_continuous_scale="Viridis",
                    title="Bản Đồ Nhiệt Sharpe Ratio theo Bộ Tham Số (EMA vs OBV Slope)"
                )
                st.plotly_chart(fig_heat, use_container_width=True)
            elif HAS_MPL:
                fig, ax = plt.subplots(figsize=(8, 5))
                cax = ax.imshow(pivot_sharpe.values, cmap='viridis', aspect='auto')
                ax.set_xticks(range(len(pivot_sharpe.columns)))
                ax.set_xticklabels(pivot_sharpe.columns)
                ax.set_yticks(range(len(pivot_sharpe.index)))
                ax.set_yticklabels(pivot_sharpe.index)
                ax.set_xlabel("Chu kỳ EMA")
                ax.set_ylabel("Chu kỳ OBV Slope")
                ax.set_title("Bản Đồ Nhiệt Sharpe Ratio")
                fig.colorbar(cax)
                plt.tight_layout()
                st.pyplot(fig)
                plt.close(fig)

            st.markdown("#### 📋 Top 10 Bộ Tham Số Tốt Nhất:")
            st.dataframe(valid_opt_df.head(10).drop(columns=['Hợp Lệ']), use_container_width=True, hide_index=True)
        else:
            st.error("Không tìm thấy bộ tham số nào thỏa mãn điều kiện số lệnh tối thiểu.")


# ==============================================================================
# 8. FOOTER THÔNG TIN
# ==============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.85rem;">
    Ứng dụng Xây dựng Phục vụ Nghiên cứu Định Lượng & Báo Cáo Chiến Lược EMA + OBV trên Cổ Phiếu ACB.<br>
    Được tối ưu hóa để triển khai trực tiếp trên <strong>Streamlit Cloud</strong> & <strong>GitHub</strong>.
</div>
""", unsafe_allow_html=True)
