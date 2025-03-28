import pandas as pd
import numpy as np
import re
import strsimpy
import requests
import io
from time import time

def create_excel_template():
    """
    Creates an Excel template with columns part_number, product, category, brand (case-sensitive).

    Returns:
        - df (pd.DataFrame): The DataFrame representation of the template.
        - excel_data (bytes): The Excel file in binary format.
    """
    df = pd.DataFrame([["" for i in range(4)]for j in range(20)], columns=["part_number", "product", "category", "brand"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
        writer.sheets["Sheet1"].set_column("A:D", 15)

    excel_data = output.getvalue()
    return df, excel_data

def convert_result_to_excel(df_result):
    """
    Converts the result DataFrame into an Excel file.

    Args:
        df_result (pd.DataFrame): The DataFrame containing the results.

    Returns:
        excel_data (bytes): The Excel file in binary format.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_result[["details", "match1", "match2", "match1_cost", "match1_tier_1", "match2_cost", "match2_tier_1"]].to_excel(writer, sheet_name="results", index=False)
        df_result.to_excel(writer, sheet_name="result_details", index=False)
        writer.sheets["results"].set_column("A:C", 30)
        writer.sheets["results"].set_column("D:G", 15)

    excel_data = output.getvalue()

    return excel_data

def request_redash_goparts_product_query(api_call):
    """
    Fetches product data from a Redash API call and formats it into a DataFrame.

    Args:
        api_call (str): The API endpoint URL.

    Returns:
        df (pd.DataFrame): The DataFrame containing the fetched product data.
    """
    response = requests.get(str(api_call)).json()
    cols = ["part_number", "product", "category", "brand", "cost", "tier_1", "p_id", "pc_id", "ib_id"]
    df = pd.DataFrame(response["query_result"]["data"]["rows"])[cols]

    return df

def clean_str(text):
    """
    Cleans a string by removing non-alphanumeric characters and normalizing case.

    Args:
        text (str): The input string.

    Returns:
        cleaned_text (str): The cleaned string, or None if the input is NaN.
    """
    if pd.isna(text):
        return
    cleaned_text = re.sub(r"[^a-zA-Z0-9]", "", text).replace("ñ", "n").replace("Ñ", "N").lower()

    return cleaned_text

def setup_df_needle(df1):
    """
    Prepares the input DataFrame by cleaning and adding new columns for matching.

    Args:
        df1 (pd.DataFrame): The input DataFrame.

    Returns:
        df1 (pd.DataFrame): The modified DataFrame with cleaned columns.
    """
    df1["part_number_clean"] = df1["part_number"].map(clean_str)
    df1["product_clean"] = df1["product"].map(clean_str)
    df1["category_clean"] = df1["category"].map(clean_str)
    df1["brand_clean"] = df1["brand"].map(clean_str)

    return df1

def setup_df_haystack(api_call):
    """
    Prepares the haystack DataFrame by fetching, cleaning, and structuring data.

    Args:
        api_call (str): The API endpoint URL.

    Returns:
        df2 (pd.DataFrame): The part_number and product DataFrame.
        df2_category (pd.DataFrame): The category DataFrame.
        df2_brand (pd.DataFrame): The brand DataFrame.
    """
    df2 = request_redash_goparts_product_query(api_call)
    df2_category =  df2[["pc_id", "category"]].drop_duplicates()
    df2_brand = df2[["ib_id", "brand"]].drop_duplicates()

    df2["part_number_clean"] = df2["part_number"].map(clean_str)
    df2["product_clean"] = df2["product"].map(clean_str)
    df2_category["category_clean"] = df2_category["category"].map(clean_str)
    df2_brand["brand_clean"] = df2_brand["brand"].map(clean_str)

    df2_category.drop(columns=["category"], inplace=True)
    df2_brand.drop(columns=["brand"], inplace=True)

    return df2, df2_category, df2_brand

def jaccard(str1, str2):
    """
    Computes the Jaccard similarity score between two strings.
    similarity score is between 0 and 1.

    Args:
        str1 (str): The first string.
        str2 (str): The second string.

    Returns:
        score (float): The Jaccard similarity score, or None if either string is NaN.
    """
    if pd.isna(str1) or pd.isna(str2):
        return
    score = strsimpy.Jaccard(3).similarity(str1, str2)

    return score

def row_average(row2):
    """
    Computes a weighted average score for a row based on matching scores.
    ignores blank product details.

    Args:
        row2 (pd.DataFrame Row): The row containing matching scores.

    Returns:
        weighted_average (float): The weighted average similarity score.
    """
    sum_row = 0
    n = 0

    part_number_score = row2["part_number_score"]
    product_score = row2["product_score"]
    category_score = row2["category_score"]
    brand_score = row2["brand_score"]

    if not pd.isna(part_number_score):
        weight = 4
        sum_row += weight*part_number_score
        n += weight

    if not pd.isna(product_score):
        weight = 4
        sum_row += weight*product_score
        n += weight

    if not pd.isna(category_score):
        weight = 1
        sum_row += weight*category_score
        n += weight

    if not pd.isna(brand_score):
        weight = 1
        sum_row += weight*brand_score
        n += weight

    weighted_average = sum_row/max(1, n)

    return weighted_average

def details_concat(row1):
    """
    Concatenates product details from a row into a single string.

    Args:
        row1 (pd.DataFrame Row): The row containing details.

    Returns:
        details_concat_str (str): The concatenated details string.
    """
    part_number = row1["part_number"]
    product = row1["product"]
    category = row1["category"]
    brand = row1["brand"]

    details_concat_str = "|"
    if not pd.isna(part_number):
        details_concat_str += part_number + "|"

    if not pd.isna(product):
        details_concat_str += product + "|"

    if not pd.isna(category):
        details_concat_str += category + "|"

    if not pd.isna(brand):
        details_concat_str += brand + "|"

    return details_concat_str

def match_concat(row1, row2):
    """
    Concatenates matched details in row2 if it is given in row1.

    Args:
        row1 (pd.DataFramae Row): The row of the needle DataFrame.
        row2 (pd.DataFramae Row): The row of the matched DataFrame.

    Returns:
        (str): The concatenated matching details string.
    """
    match_concat_str = "|"
    if not pd.isna(row1["part_number"]):
        match_concat_str += row2["part_number"] + "|"

    if not pd.isna(row1["product"]):
        match_concat_str += row2["product"] + "|"

    if not pd.isna(row1["category"]):
        match_concat_str += row2["category"] + "|"

    if not pd.isna(row1["brand"]):
        match_concat_str += row2["brand"] + "|"

    return match_concat_str

def match_string(row1, df2, df2_category, df2_brand):
    """
    Matches a single row against the haystack DataFrame and computes scores.

    Args:
        row1 (pd.Series): The row to match.
        df2 (pd.DataFrame): The main haystack DataFrame.
        df2_category (pd.DataFrame): The category DataFrame.
        df2_brand (pd.DataFrame): The brand DataFrame.

    Returns:
        tuple: A tuple containing match details, scores, and other metrics.
    """
    df2["part_number_score"] = df2["part_number_clean"].map(lambda row2: jaccard(row1["part_number_clean"], row2))
    df2["product_score"] = df2["product_clean"].map(lambda row2: jaccard(row1["product_clean"], row2))
    df2_category["category_score"] = df2_category["category_clean"].map(lambda row2: jaccard(row1["category_clean"], row2))
    df2_brand["brand_score"] = df2_brand["brand_clean"].map(lambda row2: jaccard(row1["brand_clean"], row2))

    df_result = df2.merge(df2_category, on="pc_id", how="left").merge(df2_brand, on="ib_id", how="left")

    df2.drop(columns=["part_number_score", "product_score"], inplace=True)
    df2_category.drop(columns=["category_score"], inplace=True)
    df2_brand.drop(columns=["brand_score"], inplace=True)

    df_result["average_score"] = df_result.apply(row_average, axis=1)
    df_result.sort_values(by=["average_score", "tier_1"], ascending=[False, True], inplace=True)
    df_first2 = df_result.head(2)
    df_first2["match_concat"] = df_first2.apply(lambda row2: match_concat(row1, row2), axis=1)
    df_first2 = df_first2[["match_concat", "p_id", "average_score", "cost", "tier_1"]]
    str_high2, id_high2, score2, cost2, tier1_2 = df_first2.iloc[0]
    str_high3, id_high3, score3, cost3, tier1_3 = df_first2.iloc[1]
    delta = score2 - score3

    return str_high2, str_high3, cost2, tier1_2, cost3, tier1_3, id_high2, id_high3, score2, score3, delta

def match_strings(df1, api_call):
    """
    Matches all rows in the input DataFrame against the haystack and computes results.

    Args:
        df1 (pd.DataFrame): The input DataFrame.
        api_call (str): The API endpoint URL.

    Returns:
        pd.DataFrame: The DataFrame containing match results and metrics.
    """
    df1 = setup_df_needle(df1)
    df2, df2_category, df2_brand = setup_df_haystack(api_call)
    ti = time()
    results = df1.apply(lambda row1: match_string(row1, df2, df2_category, df2_brand), axis=1)
    df1[["match1", "match2", "match1_cost", "match1_tier_1", "match2_cost", "match2_tier_1", "id1", "id2", "score1", "score2", "delta_score"]] = pd.DataFrame(results.to_list(), index=results.index)

    df1["score1"] = np.round(100*df1["score1"], 2)
    df1["score2"] = np.round(100*df1["score2"], 2)
    df1["delta_score"] = np.round(100*df1["delta_score"], 2)
    df1["relative_error"] = np.round(100*(df1["score1"] - df1["score2"])/df1["score1"], 2)

    df1["details"] = df1.apply(details_concat, axis=1)
    df1 = df1[["details", "match1", "match2", "match1_cost", "match1_tier_1", "match2_cost", "match2_tier_1", "id1", "id2", "score1", "score2", "delta_score", "relative_error" ]]
    tf = time()
    print("total time:", tf-ti)
    return df1