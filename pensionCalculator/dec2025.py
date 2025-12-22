# to run this program streamlit run dec2025.py
import streamlit as st
import pandas as pd
import requests
import datetime

st.set_page_config(page_title="Pension Planner with Spouse & Yearly Table", layout="wide")


# --- Helper functions ---
def get_conversion_rate(fallback=100.0):
    """Fetch GBP to INR conversion rate."""
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/GBP", timeout=6)
        r.raise_for_status()
        data = r.json()
        return float(data.get("rates", {}).get("INR", fallback))
    except:
        return fallback


def accumulate_pot_with_tax(current_pot, monthly_contrib, annual_return, years, start_year=None):
    """
    Compound growth pre-retirement, month-by-month, but apply tax rule:
    - From April 2027 onward (i.e. for calendar year >= 2027),
      if yearly contribution > 2000 -> reduce that year's contribution by 8%.
    We simulate year-by-year and inside each year month-by-month, using monthly contribution
    adjusted for any tax that applies that calendar year.
    """
    if start_year is None:
        start_year = datetime.datetime.now().year

    bal = float(current_pot)
    monthly_r = annual_return / 12.0

    for y in range(int(years)):
        calendar_year = start_year + y
        yearly_contrib = float(monthly_contrib) * 12.0

        # Tax rule applies from April 2027 (we use calendar-year granularity)
        if calendar_year >= 2027:
            if yearly_contrib > 2000.0:
                yearly_contrib = yearly_contrib * 0.92  # deduct 8%

        monthly_effective = yearly_contrib / 12.0

        # apply month-by-month compounding for this year
        for _ in range(12):
            bal = bal * (1 + monthly_r) + monthly_effective

    return bal


def simulate_yearly_schedule(pot, post_growth, retire_age, private_start, inflation, gov_monthly, lump_sum,
                             end_age=100):
    """Generate yearly table of pension withdrawals and remaining pot."""
    rows = []
    # First row: show accumulated pot and lump sum withdrawn
    rows.append({
        "Age": retire_age,
        "PrivateMonthly": round(private_start, 2),
        "GovMonthly": round(0.0, 2),
        "TotalMonthly": round(private_start, 2),
        "TotalYearly": round(private_start * 12, 2),
        "PotEnd": round(pot, 2),
        "LumpWithdrawn": round(lump_sum, 2),
    })

    private_monthly = private_start
    for age in range(retire_age, end_age + 1):
        for m in range(12):
            pot = pot * (1 + post_growth / 12.0)
            pot -= private_monthly
        total_private_year = private_monthly * 12
        # NOTE: per your code snippet, government pension starts at age 68
        gov_income_year = (gov_monthly * 12 if age >= 68 else 0.0)
        total_yearly = total_private_year + gov_income_year
        total_monthly_income = private_monthly + (gov_monthly if age >= 68 else 0.0)
        rows.append({
            "Age": age,
            "PrivateMonthly": round(private_monthly, 2),
            "GovMonthly": round(gov_monthly if age >= 68 else 0.0, 2),
            "TotalMonthly": round(total_monthly_income, 2),
            "TotalYearly": round(total_yearly, 2),
            "PotEnd": round(pot, 2),
            "LumpWithdrawn": 0.0,
        })
        private_monthly *= (1 + inflation)
    df = pd.DataFrame(rows)
    return df


# --- Inputs ---
st.title("💰 Pension Planner with Spouse & Yearly Table")

st.info(
    "Please fill in all fields. Minimum retirement age is 57. After filling, click 'Generate Pension Table' to see results.")

st.subheader("Personal Info")
col1, col2 = st.columns(2)

with col1:
    st.write("You")
    age_u = st.number_input("Your age", 18, 100, 40, key="age_u")
    retire_u = st.number_input("Your retirement age", 57, 100, 68, key="retire_u")
    pot_u = st.number_input("Current pot (£)", 0.0, 1e12, 50000.0, key="pot_u")
    contrib_u = st.number_input("Monthly contribution (£)", 0.0, 1e6, 500.0, key="contrib_u")
    pre_growth_u = st.number_input("Pre-retirement annual growth (%)", 0.0, 20.0, 5.0, key="pre_growth_u") / 100.0
    post_growth_u = st.number_input("Post-retirement annual growth (%)", 0.0, 20.0, 4.0, key="post_growth_u") / 100.0
    gov_annual_u = st.number_input("Government pension/year (£)", 0.0, 1e6, 9000.0, key="gov_u")
    lump_pct_u = st.number_input("Lump sum at retirement (%)", 0.0, 100.0, 25.0, key="lump_u")

with col2:
    st.write("Spouse")
    age_s = st.number_input("Spouse age", 18, 100, 38, key="age_s")
    retire_s = st.number_input("Spouse retirement age", 57, 100, 68, key="retire_s")
    pot_s = st.number_input("Spouse current pot (£)", 0.0, 1e12, 40000.0, key="pot_s")
    contrib_s = st.number_input("Spouse monthly contribution (£)", 0.0, 1e6, 400.0, key="contrib_s")
    pre_growth_s = st.number_input("Spouse pre-retirement annual growth (%)", 0.0, 20.0, 5.0,
                                   key="pre_growth_s") / 100.0
    post_growth_s = st.number_input("Spouse post-retirement annual growth (%)", 0.0, 20.0, 4.0,
                                    key="post_growth_s") / 100.0
    gov_annual_s = st.number_input("Spouse government pension/year (£)", 0.0, 1e6, 9000.0, key="gov_s")
    lump_pct_s = st.number_input("Spouse lump sum at retirement (%)", 0.0, 100.0, 25.0, key="lump_s")

# Residency selection
residency = st.selectbox("Residency after retirement", ["UK", "India"], key="residency_select")
if residency == "UK":
    inflation_sel = st.number_input("UK inflation (%)", 0.0, 20.0, 2.0, key="inflation_sel") / 100.0
    conv = 1.0
    currency_sym = "£"
else:
    inflation_sel = st.number_input("India inflation (%)", 0.0, 20.0, 7.0, key="inflation_sel") / 100.0
    conv = get_conversion_rate()
    currency_sym = "₹"

if st.button("Generate Pension Table"):

    # --- Validation ---
    if retire_u < 57 or retire_s < 57:
        st.warning("⚠️ Minimum retirement age is 57. Please adjust the retirement age.")
    else:
        # current calendar year (used for tax rule)
        current_year = datetime.datetime.now().year

        # --- Accumulation (apply tax rule on contributions from 2027 onwards) ---
        years_u = retire_u - age_u
        acc_u = accumulate_pot_with_tax(pot_u, contrib_u, pre_growth_u, years_u, start_year=current_year)
        lump_u = acc_u * (lump_pct_u / 100.0)
        rem_u = acc_u - lump_u

        years_s = retire_s - age_s
        acc_s = accumulate_pot_with_tax(pot_s, contrib_s, pre_growth_s, years_s, start_year=current_year)
        lump_s = acc_s * (lump_pct_s / 100.0)
        rem_s = acc_s - lump_s

        # Private monthly pension at retirement (adjusted for inflation until retirement)
        private_u = 2000.0 * ((1 + inflation_sel) ** years_u)
        private_s = 2000.0 * ((1 + inflation_sel) ** years_s)

        # --- Adjust for INR if India ---
        acc_u_disp = acc_u * conv
        rem_u_disp = rem_u * conv
        lump_u_disp = lump_u * conv
        private_u_disp = private_u * conv
        gov_monthly_u_disp = (gov_annual_u / 12.0) * conv

        acc_s_disp = acc_s * conv
        rem_s_disp = rem_s * conv
        lump_s_disp = lump_s * conv
        private_s_disp = private_s * conv
        gov_monthly_s_disp = (gov_annual_s / 12.0) * conv

        # --- Generate yearly schedule ---
        df_u = simulate_yearly_schedule(rem_u_disp, post_growth_u, retire_u, private_u_disp, inflation_sel,
                                        gov_monthly_u_disp, lump_u_disp)
        df_s = simulate_yearly_schedule(rem_s_disp, post_growth_s, retire_s, private_s_disp, inflation_sel,
                                        gov_monthly_s_disp, lump_s_disp)

        # --- Display tables ---
        st.header(f"{'🇮🇳' if residency == 'India' else '🇬🇧'} Pension Schedule ({currency_sym})")
        st.subheader("You")
        st.dataframe(df_u)
        st.subheader("Spouse")
        st.dataframe(df_s)

        # --- Summary ---
        st.markdown("---")
        st.subheader("🔎 Summary at Retirement")
        col1, col2 = st.columns(2)
        with col1:
            st.write("You")
            st.write(f"Accumulated pot: {currency_sym}{acc_u_disp:,.2f}")
            st.write(f"Lump sum withdrawn: {currency_sym}{lump_u_disp:,.2f}")
            st.write(f"Remaining pot: {currency_sym}{rem_u_disp:,.2f}")
            st.write(f"Private monthly pension at retirement: {currency_sym}{private_u_disp:,.2f}")
            st.write(f"Gov pension monthly: {currency_sym}{gov_monthly_u_disp:,.2f}")
        with col2:
            st.write("Spouse")
            st.write(f"Accumulated pot: {currency_sym}{acc_s_disp:,.2f}")
            st.write(f"Lump sum withdrawn: {currency_sym}{lump_s_disp:,.2f}")
            st.write(f"Remaining pot: {currency_sym}{rem_s_disp:,.2f}")
            st.write(f"Private monthly pension at retirement: {currency_sym}{private_s_disp:,.2f}")
            st.write(f"Gov pension monthly: {currency_sym}{gov_monthly_s_disp:,.2f}")
