import streamlit as st
import pandas as pd
import processing
import requests

# GoParts Product Details Request App

# This Streamlit app allows users to upload a list of part numbers and retrieve
# the cost and tier 1 of their closest matches. Users can download a request
# form, fill it out, and upload it to get results.


st.title("GoParts Product Details Request")
"Welcome to the GoParts Product Details Request app. Here, you can upload a list of part numbers (via the request form) to get the cost and tier 1 of their closest match."
uploaded_file = st.file_uploader("Upload the filled-out request form below.", type=".xlsx")

if uploaded_file is None:
    st.subheader("Request Form")
    """
    Displays a blank request form for users to download and fill out.
    """
    df_blank, excel_blank = processing.create_excel_template()

    st.write(df_blank)
    st.download_button(
        label="📥 Download Request Form 📥",
        data=excel_blank,
        file_name="goparts_product_request_form.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    """
    Processes the uploaded request form and displays the matching results.
    """
    df_needle = pd.read_excel(uploaded_file)
    st.write(df_needle)

    st.subheader("Results")
    st.warning("The output of this app is not 100% accurate and still needs human supervision. Make sure to double-check the results.")
    api_call = st.secrets["redash_api_call"]
    try:
        df_match = processing.match_strings(df_needle, api_call)
        st.write(df_match[["details", "match1", "match2", "match1_cost", "match1_tier_1", "match2_cost", "match2_tier_1"]])
        excel_match = processing.convert_result_to_excel(df_match)
        st.download_button(
            label="📥 Download Results 📥",
            data=excel_match,
            file_name="goparts_product_request_form_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except requests.ConnectionError:
        st.error("Failed to connect to the database API. Please check your internet connection or try again later.")

