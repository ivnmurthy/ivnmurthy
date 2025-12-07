import streamlit as st
import requests

# Constants
DEFAULT_INTEREST_RATE = 0.05  # 5% annual interest
DEFAULT_CONVERSION_RATE = 100  # Default GBP to INR rate if API fails
GOVT_PENSION_AGE = 68  # Age when government pension starts


def get_conversion_rate():
    """Fetch latest GBP to INR conversion rate."""
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/GBP")
        data = response.json()
        return data['rates'].get('INR', DEFAULT_CONVERSION_RATE)
    except:
        return DEFAULT_CONVERSION_RATE


def calculate_accumulated_pension(monthly_pension, age, retirement_age, interest_rate):
    """Calculate accumulated pension pot by retirement."""
    years_to_retirement = max(0, retirement_age - age)
    total_months = years_to_retirement * 12
    balance = 0

    for _ in range(total_months):
        balance = (balance + monthly_pension) * (1 + interest_rate / 12)

    return balance


def main():
    st.title("💰 Pension Calculator")
    st.write("Estimate your accumulated pension and monthly income after retirement.")

    # User Inputs
    age = st.number_input("Enter your current age:", min_value=18, max_value=100, step=1)
    retirement_age = st.number_input("Enter your expected retirement age:", min_value=50, max_value=100, step=1)
    monthly_pension = st.number_input("Enter your monthly pension contributions (including employer) in GBP:",
                                      min_value=0.0, step=50.0)
    interest_rate = st.number_input("Enter the annual interest rate on pension savings (%):", min_value=0.0, step=0.1,
                                    value=DEFAULT_INTEREST_RATE * 100) / 100
    govt_pension_yearly = st.number_input("Estimated government pension per year (GBP):", min_value=0.0, step=100.0)

    # Residency input
    residency = st.selectbox("Are you staying in the UK or abroad?", ["UK", "India", "Other"])
    conversion_rate = get_conversion_rate() if residency == "India" else 1

    # Pension Accumulation Calculation
    accumulated_pension = calculate_accumulated_pension(monthly_pension, age, retirement_age, interest_rate)

    # Monthly pension calculation at retirement
    monthly_income = accumulated_pension * (interest_rate / 12)  # Monthly drawdown

    # Government pension logic
    govt_pension_monthly = govt_pension_yearly / 12 if age >= GOVT_PENSION_AGE else 0

    # Display Results
    if st.button("Calculate Pension"):
        st.subheader("🔹 Accumulated Pension Pot at Retirement")
        st.write(f"💰 **Total Accumulated Pension**: £{accumulated_pension:,.2f}")

        st.subheader("📆 Monthly Pension Income")
        st.write(f"🏦 **Before Age {GOVT_PENSION_AGE}:** £{monthly_income:,.2f}/month")
        st.write(
            f"🟢 **After Age {GOVT_PENSION_AGE} (With Government Pension):** £{(monthly_income + govt_pension_monthly):,.2f}/month")

        # Conversion to INR if applicable
        if residency == "India":
            converted_income_before_68 = monthly_income * conversion_rate
            converted_income_after_68 = (monthly_income + govt_pension_monthly) * conversion_rate

            st.subheader("🇮🇳 Pension in INR")
            st.write(f"💵 **Before Age {GOVT_PENSION_AGE}:** ₹{converted_income_before_68:,.2f}/month")
            st.write(f"💵 **After Age {GOVT_PENSION_AGE}:** ₹{converted_income_after_68:,.2f}/month")


if __name__ == "__main__":
    main()
