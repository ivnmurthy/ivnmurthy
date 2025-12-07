import streamlit as st
import requests

# Set page configuration
st.set_page_config(page_title="Pension Calculator", layout="wide")

# to run this program streamlit run pensionCalculator_v4.0_chatGPT.py
"""
Requirements (Updated):
1. Calculate private pension accumulation until retirement age.
2. Calculate monthly pension need based on £3000/month per person at today’s prices.
3. Adjust pension withdrawal amounts yearly based on inflation:
      - 2% if residency is UK
      - 7% if residency is India
4. Calculate monthly pension before age 68 (only private pension).
5. Calculate monthly pension after age 68 (private + government pension).
6. Apply GBP→INR conversion if residency is India.
7. Show separate entries for self and spouse.
8. Include currency symbols and flags.
9. Display values in GBP and INR.
10. Allow % lump-sum withdrawal at retirement.
11. Display withdrawal amounts.
12. Calculate how long pension lasts when spending increases every year with inflation.

"""

def get_conversion_rate():
    """Fetch latest GBP to INR conversion rate."""
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/GBP")
        response.raise_for_status()
        data = response.json()
        if 'rates' not in data:
            st.error(f"Unexpected API response format: {data}")
            return 100
        return data['rates'].get('INR', 100)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching conversion rate: {e}")
        return 100
    except (ValueError, KeyError) as e:
        st.error(f"Error parsing API response: {e}")
        return 100

def calculate_accumulated_pension(monthly_contribution, interest_rate, years):
    """Calculate accumulated pension pot at retirement using compound interest."""
    total_months = int(years * 12)
    balance = 0
    monthly_interest = interest_rate / 12
    for _ in range(total_months):
        balance = (balance + monthly_contribution) * (1 + monthly_interest)
    return balance

def pension_calculator(principal, interest_rate, monthly_withdrawal):
    """Simulate pension withdrawals until depletion."""
    months = 0
    balance = principal
    monthly_interest = interest_rate / 12
    while balance > 0 and months < 1200:  # Max 100 years
        balance *= (1 + monthly_interest)
        balance -= monthly_withdrawal
        months += 1
    years = months // 12
    remaining_months = months % 12
    return years, remaining_months

def main():
    st.title("💰 Pension Calculator")
    st.write("Estimate your accumulated pension pot and monthly pension after retirement.")

    # User Inputs
    col1, col2 = st.columns(2)

    with col1:
        user_age = st.number_input("Your Age", min_value=18, max_value=100, value=30)
        retirement_age_user = st.number_input("Your Retirement Age", min_value=50, max_value=100, value=65)
        user_pension_contribution = st.number_input(
            "Your Monthly Pension Contribution (£)", min_value=0.0, value=500.0)
        previous_pot_user = st.number_input(
            "Your Accumulated Pension from Previous Jobs (£)", min_value=0.0, value=10000.0)
        govt_pension_user = st.number_input(
            "Your Government Pension per Year (£)", min_value=0.0, value=9000.0)
        user_withdrawal_percentage = st.number_input(
            "Your Withdrawal Percentage at Retirement (%)", min_value=0.0, max_value=100.0, value=25.0)

    with col2:
        spouse_age = st.number_input("Spouse's Age", min_value=18, max_value=100, value=30)
        retirement_age_spouse = st.number_input(
            "Spouse's Retirement Age", min_value=50, max_value=100, value=65)
        spouse_pension_contribution = st.number_input(
            "Spouse's Monthly Pension Contribution (£)", min_value=0.0, value=500.0)
        previous_pot_spouse = st.number_input(
            "Spouse's Accumulated Pension from Previous Jobs (£)", min_value=0.0, value=10000.0)
        govt_pension_spouse = st.number_input(
            "Spouse's Government Pension per Year (£)", min_value=0.0, value=9000.0)
        spouse_withdrawal_percentage = st.number_input(
            "Spouse's Withdrawal Percentage at Retirement (%)", min_value=0.0, max_value=100.0, value=25.0)

    interest_rate = st.number_input(
        "Expected Annual Interest Rate (%)", min_value=0.0, value=5.0) / 100
    residency = st.selectbox("Residency After Retirement", ["UK", "India", "Other"])
    conversion_rate = get_conversion_rate() if residency == "India" else 1

    # Button
    if st.button("Calculate Pension"):

        # Pension Accumulation Calculation
        user_years_until_retirement = max(0, retirement_age_user - user_age)
        spouse_years_until_retirement = max(0, retirement_age_spouse - spouse_age)

        user_accumulated_pension = previous_pot_user + calculate_accumulated_pension(
            user_pension_contribution, interest_rate, user_years_until_retirement)
        spouse_accumulated_pension = previous_pot_spouse + calculate_accumulated_pension(
            spouse_pension_contribution, interest_rate, spouse_years_until_retirement)
        total_accumulated_pension = user_accumulated_pension + spouse_accumulated_pension

        # Apply Withdrawal Percentage
        user_withdrawal_amount = user_accumulated_pension * (user_withdrawal_percentage / 100)
        spouse_withdrawal_amount = spouse_accumulated_pension * (spouse_withdrawal_percentage / 100)

        user_accumulated_pension -= user_withdrawal_amount
        spouse_accumulated_pension -= spouse_withdrawal_amount
        total_accumulated_pension = user_accumulated_pension + spouse_accumulated_pension

        # Monthly Pension Calculation
        user_monthly_pension_before_68 = user_accumulated_pension * (interest_rate / 12)
        spouse_monthly_pension_before_68 = spouse_accumulated_pension * (interest_rate / 12)

        user_monthly_pension_after_68 = user_monthly_pension_before_68 + (govt_pension_user / 12)
        spouse_monthly_pension_after_68 = spouse_monthly_pension_before_68 + (govt_pension_spouse / 12)

        # Apply conversion rate
        user_accumulated_pension_inr = user_accumulated_pension * conversion_rate
        spouse_accumulated_pension_inr = spouse_accumulated_pension * conversion_rate
        total_accumulated_pension_inr = total_accumulated_pension * conversion_rate

        user_withdrawal_amount_inr = user_withdrawal_amount * conversion_rate
        spouse_withdrawal_amount_inr = spouse_withdrawal_amount * conversion_rate

        user_monthly_pension_before_68_inr = user_monthly_pension_before_68 * conversion_rate
        spouse_monthly_pension_before_68_inr = spouse_monthly_pension_before_68 * conversion_rate

        user_monthly_pension_after_68_inr = user_monthly_pension_after_68 * conversion_rate
        spouse_monthly_pension_after_68_inr = spouse_monthly_pension_after_68 * conversion_rate

        # Calculate how long the pension pot will last
        user_pot_years, user_pot_months = pension_calculator(
            user_accumulated_pension, interest_rate, user_monthly_pension_after_68)
        spouse_pot_years, spouse_pot_months = pension_calculator(
            spouse_accumulated_pension, interest_rate, spouse_monthly_pension_after_68)

        # Display Results
        st.subheader("🏦 Accumulated Pension at Retirement")

        st.write(f"💵 **Your Withdrawal Amount at Retirement**: 🇬🇧 £{user_withdrawal_amount:,.2f} / "
                 f"🇮🇳 ₹{user_withdrawal_amount_inr:,.2f}")
        st.write(f"💵 **Spouse's Withdrawal Amount at Retirement**: 🇬🇧 £{spouse_withdrawal_amount:,.2f} / "
                 f"🇮🇳 ₹{spouse_withdrawal_amount_inr:,.2f}")

        st.write(f"💰 **Your Remaining Pension Pot**: 🇬🇧 £{user_accumulated_pension:,.2f} / "
                 f"🇮🇳 ₹{user_accumulated_pension_inr:,.2f}")
        st.write(f"💰 **Spouse's Remaining Pension Pot**: 🇬🇧 £{spouse_accumulated_pension:,.2f} / "
                 f"🇮🇳 ₹{spouse_accumulated_pension_inr:,.2f}")
        st.write(f"💰 **Total Remaining Pension**: 🇬🇧 £{total_accumulated_pension:,.2f} / "
                 f"🇮🇳 ₹{total_accumulated_pension_inr:,.2f}")

        st.subheader("📆 Monthly Pension Breakdown Before Age 68")
        st.write(f"🔹 **Your Monthly Pension**: 🇬🇧 £{user_monthly_pension_before_68:,.2f}/month / "
                 f"🇮🇳 ₹{user_monthly_pension_before_68_inr:,.2f}/month")
        st.write(f"🔹 **Spouse's Monthly Pension**: 🇬🇧 £{spouse_monthly_pension_before_68:,.2f}/month / "
                 f"🇮🇳 ₹{spouse_monthly_pension_before_68_inr:,.2f}/month")

        st.subheader("📆 Monthly Pension Breakdown After Age 68")
        st.write(f"🔹 **Your Monthly Pension**: 🇬🇧 £{user_monthly_pension_after_68:,.2f}/month / "
                 f"🇮🇳 ₹{user_monthly_pension_after_68_inr:,.2f}/month")
        st.write(f"🔹 **Spouse's Monthly Pension**: 🇬🇧 £{spouse_monthly_pension_after_68:,.2f}/month / "
                 f"🇮🇳 ₹{spouse_monthly_pension_after_68_inr:,.2f}/month")

        st.subheader("⏳ Pension Depletion Estimate")
        st.write(f"🕒 **Your pension lasts**: {user_pot_years} years and {user_pot_months} months")
        st.write(f"🕒 **Spouse's pension lasts**: {spouse_pot_years} years and {spouse_pot_months} months")

        if residency == "India":
            st.write(f"🛑 **Note**: All amounts have been converted using the current exchange rate "
                     f"of 1 GBP = {conversion_rate:.2f} INR.")

if __name__ == "__main__":
    main()
