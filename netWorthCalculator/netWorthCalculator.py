import streamlit as st
import pandas as pd

st.set_page_config(page_title="Family Net Worth Calculator", layout="wide")
st.title("💰 Family Net Worth Calculator")

# -----------------------------
# Utility: Future Value Formula
# -----------------------------
def future_value(current, monthly, growth, months):
    r = growth / 100 / 12
    fv_current = current * ((1 + r) ** months)
    fv_sip = monthly * (((1 + r) ** months - 1) / r) if r > 0 else monthly * months
    return fv_current + fv_sip

# -----------------------------
# Global Settings
# -----------------------------
st.sidebar.header("Global Settings")
default_growth = st.sidebar.number_input("Default Growth (%)", 0.0, 20.0, 8.0)
inflation = st.sidebar.number_input("Inflation (%)", 0.0, 10.0, 2.0)

# -----------------------------
# Instrument Entry Section
# -----------------------------
st.subheader("Add Financial Instruments")

if "rows" not in st.session_state:
    st.session_state.rows = []

with st.form("instrument_form"):
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Instrument Name")
    owner = c2.selectbox("Owner", ["Murthy", "Mrudula", "Sanjali", "Kruthik", "Other"])
    growth = c3.number_input("Growth (%)", 0.0, 20.0, default_growth)

    c4, c5, c6 = st.columns(3)
    term = c4.number_input("Term (months)", 1, 600, 120)
    monthly = c5.number_input("Monthly Savings (£)", 0, 10000, 0)
    current = c6.number_input("Current Value (£)", 0, 5000000, 0)

    submitted = st.form_submit_button("Add Instrument")

    if submitted:
        st.session_state.rows.append({
            "Instrument": name,
            "Owner": owner,
            "Growth %": growth,
            "Term (mo)": term,
            "Monthly (£)": monthly,
            "Current (£)": current
        })
        st.success(f"Added: {name}")

# -----------------------------
# Display Table & Calculate
# -----------------------------
if st.session_state.rows:
    df = pd.DataFrame(st.session_state.rows)

    # Calculate maturity values
    df["Maturity (£)"] = df.apply(
        lambda row: future_value(row["Current (£)"], row["Monthly (£)"], row["Growth %"], row["Term (mo)"]),
        axis=1
    )

    st.subheader("📊 Net Worth Summary")
    st.dataframe(df)

    total_current = df["Current (£)"].sum()
    total_future = df["Maturity (£)"].sum()

    st.metric("Total Current Value", f"£{total_current:,.2f}")
    st.metric("Total Future Value", f"£{total_future:,.2f}")

# -----------------------------
# Home Value Section
# -----------------------------
st.subheader("🏠 Home Value Projection")

home_val = st.number_input("Current Home Value (£)", 0, 5000000, 625000)
home_growth = st.number_input("Home Growth (%)", 0.0, 10.0, 2.0)
home_term = st.number_input("Home Term (months)", 1, 600, 132)

home_future = future_value(home_val, 0, home_growth, home_term)

st.metric("Future Home Value", f"£{home_future:,.2f}")

# -----------------------------
# Total Including Home
# -----------------------------
if st.session_state.rows:
    st.subheader("📘 Total Net Worth Including Home")
    st.metric("Total Current Net Worth", f"£{total_current + home_val:,.2f}")
    st.metric("Total Future Net Worth", f"£{total_future + home_future:,.2f}")
