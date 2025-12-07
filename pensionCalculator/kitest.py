
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np

# Constants
DEVEX_RATE = 0.0035  # 1 Robux = $0.0035 USD (subject to change)
MIN_DEVEX_ROBUX = 30000  # Minimum Robux required to exchange for USD

# Streamlit Title & Description
st.title("💰 Roblox Creator Income Calculator")
st.subheader("Estimate your potential earnings as a Roblox developer!")

st.markdown("""
🔹 Enter your **monthly** earnings in Robux  
🔹 Get an **estimated USD conversion** based on DevEx rates  
🔹 See a **detailed breakdown** of income sources  
🔹 Get **tips** on increasing your earnings! 🚀
""")

# User Inputs
robux_earned = st.number_input("🎮 Total Robux Earned (Monthly):", min_value=0, value=50000, step=5000)
payout_type = st.selectbox("💵 Main Income Source:", ["Game Passes", "Premium Payouts", "UGC Sales", "Dev Products", "Ads", "Donations"])

# Additional Revenue Streams (Percentage Split)
st.subheader("📊 Income Breakdown (Percentage)")
game_pass_pct = st.slider("Game Passes (%)", 0, 100, 40)
premium_payout_pct = st.slider("Premium Payouts (%)", 0, 100, 25)
ugc_sales_pct = st.slider("UGC Sales (%)", 0, 100, 15)
dev_products_pct = st.slider("Dev Products (%)", 0, 100, 10)
ads_pct = st.slider("Ad Revenue (%)", 0, 100, 5)
donations_pct = st.slider("Donations (%)", 0, 100, 5)

# Ensure total is 100%
total_percentage = game_pass_pct + premium_payout_pct + ugc_sales_pct + dev_products_pct + ads_pct + donations_pct
if total_percentage != 100:
    st.warning("⚠️ The total percentage must add up to 100%! Adjust sliders accordingly.")

# Convert Robux to USD
usd_earnings = robux_earned * DEVEX_RATE
st.subheader("💵 Estimated Earnings")
st.write(f"**🎯 Robux Earned:** {robux_earned:,} R$")
st.write(f"**💰 USD Equivalent:** ${usd_earnings:,.2f}")

# Earnings Breakdown (in Robux)
earnings_breakdown = {
    "Game Passes": (game_pass_pct / 100) * robux_earned,
    "Premium Payouts": (premium_payout_pct / 100) * robux_earned,
    "UGC Sales": (ugc_sales_pct / 100) * robux_earned,
    "Dev Products": (dev_products_pct / 100) * robux_earned,
    "Ads": (ads_pct / 100) * robux_earned,
    "Donations": (donations_pct / 100) * robux_earned,
}

# Convert Breakdown to USD
usd_breakdown = {key: value * DEVEX_RATE for key, value in earnings_breakdown.items()}

# Display Breakdown
st.subheader("📊 Income Breakdown")
st.write("**Robux Breakdown:**")
for source, amount in earnings_breakdown.items():
    st.write(f"🔹 **{source}:** {int(amount):,} R$")

st.write("**USD Breakdown:**")
for source, amount in usd_breakdown.items():
    st.write(f"💵 **{source}:** ${amount:,.2f}")

# Charts
fig, ax = plt.subplots(1, 2, figsize=(12, 4))

# Pie Chart
ax[0].pie(earnings_breakdown.values(), labels=earnings_breakdown.keys(), autopct='%1.1f%%', startangle=140)
ax[0].set_title("Income Distribution")

# Bar Chart
ax[1].bar(earnings_breakdown.keys(), earnings_breakdown.values(), color=['blue', 'green', 'red', 'purple', 'orange', 'pink'])
ax[1].set_ylabel("Robux")
ax[1].set_title("Income Sources (Robux)")
ax[1].tick_params(axis='x', rotation=45)

st.pyplot(fig)

# DevEx Information
st.subheader("🔍 Understanding DevEx")
st.markdown(f"""
- **Current Rate**: **1 Robux = ${DEVEX_RATE:.4f}**
- **Minimum DevEx**: **{MIN_DEVEX_ROBUX} Robux** required to cash out
- **Estimated Earnings**: {robux_earned:,} Robux → ${usd_earnings:,.2f} USD
- **Robux Needed for $100**: {int(100 / DEVEX_RATE):,} R$
- **Robux Needed for $1,000**: {int(1000 / DEVEX_RATE):,} R$
""")

# Tips for Increasing Earnings
st.subheader("🚀 Tips to Maximize Your Earnings")
st.markdown("""
✅ **Increase Game Pass Sales** – Offer valuable in-game content  
✅ **Premium Payout Optimization** – Create engaging experiences for Premium users  
✅ **Sell UGC Items** – High-quality assets sell well in the Avatar Shop  
✅ **Monetize with Developer Products** – Allow in-game purchases for boosts/items  
✅ **Optimize Ad Revenue** – Run in-game ads effectively  
✅ **Encourage Donations** – Add donation options for loyal players  
""")

st.success("💡 **The more Robux you generate, the more you can earn! Keep building amazing experiences! 🚀**")
