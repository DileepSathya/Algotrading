import math
import streamlit as st

st.set_page_config(page_title="Stock + Put Hedge Calculator", page_icon="📈", layout="centered")
st.title("Stock + Put Hedge Calculator")
st.caption("Estimate stock quantity and combined stock + put P&L at target and stop-loss.")

st.subheader("1. Stock trade")
stock = st.text_input("Stock name", value="ETERNAL")
c1, c2 = st.columns(2)
with c1:
    entry = st.number_input("Stock entry price (₹)", min_value=0.01, value=329.0, step=0.5)
    stop_loss = st.number_input("Stock stop-loss (₹)", min_value=0.01, value=319.10, step=0.5)
with c2:
    target = st.number_input("Stock target (₹)", min_value=0.01, value=352.03, step=0.5)
    capital = st.number_input("Available capital (₹)", min_value=0.0, value=100000.0, step=5000.0)

st.subheader("2. Put option")
c3, c4 = st.columns(2)
with c3:
    delta = st.number_input("Put delta (absolute value)", min_value=0.0, max_value=1.0, value=0.40, step=0.05, format="%.2f")
    option_buy_price = st.number_input("Put entry premium per unit (₹)", min_value=0.0, value=6.10, step=0.05, format="%.2f")
with c4:
    lot_size = st.number_input("Units per lot", min_value=1, value=2425, step=1)
    lots = st.number_input("Number of lots", min_value=1, value=1, step=1)

st.markdown("### Option exit estimates")
st.caption("Enter the expected put exit premium for each stock outcome. Delta alone cannot predict these prices.")
c5, c6 = st.columns(2)
with c5:
    put_exit_at_sl = st.number_input("Put exit premium if stock hits stop-loss (₹)", min_value=0.0, value=10.0, step=0.05, format="%.2f")
with c6:
    put_exit_at_target = st.number_input("Put exit premium if stock hits target (₹)", min_value=0.0, value=0.0, step=0.05, format="%.2f", help="Use 0 only if modelling the put becoming worthless.")

st.subheader("3. Quantity adjustment")
multiplier = st.number_input("Premium-recovery multiplier", min_value=0.0, value=1.0, step=0.25,
    help="1.0 aims for stock target profit equal to the full put premium; 0.5 aims for half.")
max_stock_loss = st.number_input("Maximum allowed stock loss at stop-loss (₹; 0 = no limit)", min_value=0.0, value=0.0, step=100.0,
    help="Optional cap on stock loss before adding put P&L.")

option_units = int(lot_size * lots)
total_put_premium = option_buy_price * option_units
profit_per_share = target - entry
loss_per_share = entry - stop_loss
put_pnl_at_sl = (put_exit_at_sl - option_buy_price) * option_units
put_pnl_at_target = (put_exit_at_target - option_buy_price) * option_units

st.divider()
st.subheader("Results")
if entry <= stop_loss:
    st.error("Stop-loss must be below the stock entry price.")
elif target <= entry:
    st.error("Target must be above the stock entry price.")
else:
    uncapped_qty = math.ceil((total_put_premium * multiplier) / profit_per_share) if multiplier > 0 else 0
    calculated_qty = uncapped_qty
    if max_stock_loss > 0:
        calculated_qty = min(calculated_qty, math.floor(max_stock_loss / loss_per_share))

    stock_cost = calculated_qty * entry
    stock_loss = calculated_qty * loss_per_share
    stock_target_profit = calculated_qty * profit_per_share
    combined_pnl_sl = -stock_loss + put_pnl_at_sl
    combined_pnl_target = stock_target_profit + put_pnl_at_target

    a, b = st.columns(2)
    a.metric("Put option units", f"{option_units:,}")
    b.metric("Total put premium paid", f"₹{total_put_premium:,.2f}")
    a, b = st.columns(2)
    a.metric("Calculated stock quantity", f"{calculated_qty:,} shares")
    b.metric("Stock value at entry", f"₹{stock_cost:,.2f}")

    st.markdown("### Scenario A — Stock hits target")
    a, b = st.columns(2)
    a.metric("Stock P&L", f"₹{stock_target_profit:,.2f}")
    b.metric("Put P&L", f"₹{put_pnl_at_target:,.2f}")
    st.metric("Combined P&L at target", f"₹{combined_pnl_target:,.2f}")

    st.markdown("### Scenario B — Stock hits stop-loss")
    a, b = st.columns(2)
    a.metric("Stock P&L", f"−₹{stock_loss:,.2f}")
    b.metric("Put P&L", f"₹{put_pnl_at_sl:,.2f}")
    st.metric("Combined P&L at stop-loss", f"₹{combined_pnl_sl:,.2f}")

    st.markdown("### Risk and capital checks")
    st.write(f"Stock loss at stop-loss before hedge: **₹{stock_loss:,.2f}**")
    st.write(f"Combined stop-loss outcome as % of capital: **{combined_pnl_sl / capital * 100:.2f}%**" if capital > 0 else "Enter capital above ₹0 to calculate the percentage.")
    if max_stock_loss > 0 and uncapped_qty > calculated_qty:
        st.warning(f"The premium-recovery formula suggested {uncapped_qty:,} shares, but the stock-loss cap reduced this to {calculated_qty:,} shares.")
    if capital > 0 and stock_cost > capital:
        st.warning(f"The stock purchase value (₹{stock_cost:,.2f}) exceeds your available capital (₹{capital:,.2f}). Check margin, leverage, and broker requirements.")

    st.info("Combined P&L uses the put exit premiums you entered. These are estimates, not guaranteed market prices. Results exclude brokerage, taxes, slippage, margin costs, and other charges. The premium-recovery multiplier does not guarantee a profitable combined trade.")
