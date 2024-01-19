from flask import Flask, render_template, request
from bs4 import BeautifulSoup
import requests
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from googlesearch import search
from itertools import islice
import json
import re

app = Flask(__name__)


def extract_keywords(text, num_keywords=25):
    words = word_tokenize(text)
    stop_words = set(stopwords.words('english'))
    filtered_words = [word.lower() for word in words if word.isalnum() and word.lower() not in stop_words]
    return filtered_words[:num_keywords]

def search_product(keywords, num_results=5):
    query = ' '.join(keywords)
    search_results = list(islice(search(query), num_results))
    return search_results

def check_drip_pricing(prod_features):
    drip_indicators = ["fee", "charge", "tax", "shipping", "total"]
    return any(indicator in prod_features.lower() for indicator in drip_indicators)

def check_actual_drip_pricing(script_content):
    if isinstance(script_content, list) and script_content:
        for element in script_content:
            if "requires_shipping" in element and "taxable" in element:
                requires_shipping = str(element["requires_shipping"]).lower()
                taxable = str(element["taxable"]).lower()

                if requires_shipping == "true" and taxable == "true":
                    return True

    return False

def extract_script_content(soup):
    script_element = soup.find("script", id="em_product_variants", type="application/json")
    script_content = []
    if script_element:
        try:
            script_content = json.loads(script_element.string)
        except json.JSONDecodeError as e:
            print("Error decoding JSON:", e)
            print("JSON Content:", script_element.string)
    return script_content

@app.route('/', methods=['GET', 'POST'])
def index():
    prod_name = "N/A"  # Initialize prod_name
    search_results = []  # Initialize search_results

    if request.method == 'POST':
        url = request.form['url']
        source = request.form.get('source', 'deodap')  # Default to 'deodap' if not selected

        HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                   'Accept-Language': 'en-US,en;q=0.5', 'Content-Type': 'application/json', 'tz': 'GMT+00:00'}

        webpage = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(webpage.content, 'html.parser')

        shipping_details = None  # Initialize shipping_details

        if source == 'ebay':
            prod_name_element = soup.find("div", class_="vim x-item-title").find("span", class_="ux-textspans ux-textspans--BOLD")
            prod_name = prod_name_element.text.strip() if prod_name_element else "N/A"

            # Searching the product name in Google
            keywords = extract_keywords(prod_name, num_keywords=25)
            search_results = search_product(keywords, num_results=5)

            # Extracting shipping details
            shipping_details_container = soup.find("div", class_="ux-labels-values__values-content")
            if shipping_details_container:
                shipping_details_elements = shipping_details_container.find_all("span", class_="ux-textspans")
    
            # Iterate through the elements and look for the one with the specific class
                for element in shipping_details_elements:
                    if "ux-textspans--BOLD" in element.get("class", []):
                        shipping_details = element.get_text(strip=True)
                        break
                    else:
                        shipping_details = None
            else:
               shipping_details = None

            print("Shipping Charges")
            print(shipping_details)



        if source == 'ebay':
            prod_price_element = soup.find("div", class_="x-price-primary").find("span", class_="ux-textspans")
            prod_features_element = soup.find("div", class_="ux-layout-section-evo ux-layout-section--features")
            img_src_element = soup.find("img", class_="img-scale-down")
        else:  # Default to 'deodap' if source is not 'ebay'
            prod_price_element = soup.find("div", class_="price__current price__current--on-sale").find("span", class_="money")
            prod_features_element = soup.find("div", class_="product-description rte")
            # Fetching search results using product features
            keywords = extract_keywords(prod_features_element.text.strip(), num_keywords=25)
            search_results = search_product(keywords, num_results=5)
            img_src_element = soup.find("img", class_="product-gallery--loaded-image")

        prod_price = prod_price_element.text.strip()[4:] if prod_price_element else "N/A"
        prod_features = prod_features_element.text.strip() if prod_features_element else "N/A"
        img_src = img_src_element["src"] if img_src_element else "N/A"

        nltk.download('punkt')
        nltk.download('stopwords')

        keywords = extract_keywords(prod_features, num_keywords=25)

        drip_pricing_detected = check_drip_pricing(prod_features)

        # Extracting script content
        script_content = extract_script_content(soup)

        actual_drip_pricing_detected = check_actual_drip_pricing(script_content)

        # Calculate predicted_price
        if prod_price != "N/A":
            prod_price_numeric = float(prod_price.replace(',', ''))
            predicted_price = prod_price_numeric + (prod_price_numeric * 0.18) + 99 + 17.82
            predicted_price = round(predicted_price, 2)
        else:
            predicted_price = "N/A"

        return render_template('result.html', url=url, prod_name=prod_name, prod_price=prod_price,
                               prod_features=prod_features, search_results=search_results,
                               drip_pricing_detected=drip_pricing_detected,
                               actual_drip_pricing_detected=actual_drip_pricing_detected,
                               predicted_price=predicted_price, img_src=img_src, shipping_details=shipping_details, selected_option=source)

    return render_template('index.html')



if __name__ == '__main__':
    app.run(debug=True)
