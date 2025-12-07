import streamlit as st

st.title("Streamlit Test")
st.write("This is a test app.")
name = st.text_input("Enter your name:")
st.write(f"Hello, {name}!")
