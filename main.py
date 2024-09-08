import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm

# Function to save models to CSV file
def save_models_to_csv(models, csv_file):
    df = pd.DataFrame(models)
    df.to_csv(csv_file, index=False)
    print(f"Models saved to {csv_file}")

# Function to get models
def get_models(url):
    csv_file = "models.csv"
    if os.path.exists(csv_file):
        print("Models already saved to file.")
    else:
        models = []
        # Send a GET request to the URL
        response = requests.get(url)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the HTML content of the webpage
            soup = BeautifulSoup(response.content, 'html.parser')
            # Find all elements with class "col-6 col-lg-3 px-4" inside div with class "row category-products"
            product_divs = soup.find_all('div', class_='row category-products')[0].find_all('div', class_='col-6 col-lg-3 px-4')
            # Iterate through each product div
            for div in product_divs:
                #Find h2 for name of the model
                h2_tag = div.find('h2')
                # Find the <a> tag inside the div
                a_tag = h2_tag.find('a')
                # Extract the href attribute
                model_link = a_tag['href']
                model_name = a_tag.get_text()
                model = {
                    "model_name": model_name,
                    "model_link": model_link,
                    "status": "Pending"
                }
                # Append the model to the list of models
                models.append(model)
            # Save models to CSV file
            save_models_to_csv(models, csv_file)
        else:
            print("Failed to retrieve webpage")


# Function to get spare parts for each model
def get_spare_parts(model_link):
    response = requests.get(model_link)
    soup = BeautifulSoup(response.text, 'html.parser')
    spare_part_links = []
    for div in soup.find_all('div', class_='col-6 col-md-3 item product'):
        spare_part_link = div.find('a', class_='product-item-link')['href']
        spare_part_links.append(spare_part_link)
    return spare_part_links

# Function to get spare part details from a spare part link
def get_spare_part_details(spare_part_link, model_name):
    # Setting up Chrome driver (you need to have chromedriver installed: https://sites.google.com/a/chromium.org/chromedriver/)
    # Initialize Chrome options and set headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")

    # Initialize Selenium webdriver with Chrome options
    driver = webdriver.Chrome(options=chrome_options)

    # Getting the page with Selenium
    driver.get(spare_part_link)
    
    # Waiting for the page to fully render
    wait = WebDriverWait(driver, 10)  # Adjust the timeout as needed
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "fotorama__nav__shaft")))
    
    # Parsing the page source with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Extracting title of part
    title = soup.find('div', class_='product-info-main').find('h1').text.strip()
    
    # Extracting SKU
    sku = soup.find('div', class_='product attribute sku').find('div', class_='value').text.strip()
    
    # Extracting price
    price = ''
    price_wrapper = soup.find('span', class_='price-wrapper')
    if price_wrapper:
        price_tag = price_wrapper.find('span', class_='price')
        if price_tag:
            price = price_tag.text.strip()
    
    # Extracting images
    images = soup.find('div', class_='product media').find_all('img')
    image_links_set = {img['src'] for img in images if 'video' not in img.get('src', '')}
    image_links = list(image_links_set)

    output_folder = 'images'
    # Create the output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Downloading images and saving references in Excel
    image_paths = []
    for i, image_link in enumerate(image_links, 1):
        image = image_link.split('/')[-1]
        image_path = os.path.join(output_folder, image)
        response = requests.get(image_link)
        with open(image_path, 'wb') as f:
            f.write(response.content)
        image_paths.append(image)
    images = set(image_paths)
    images = ' , '.join(images)
    # Extracting details
    details = soup.find('div', class_='product attribute description').text.strip()
    
    return {
        'Model': model_name,
        'Title': title,
        'SKU': sku,
        'Price': price,
        'Image Links': images,
        'Details': details
    }

# Function to save data to CSV file
def save_to_csv(data, filename='spare_parts.csv'):
    columns = ['Model', 'Title', 'SKU', 'Price', 'Image Links', 'Details']
    df = pd.DataFrame(data, columns=columns)
    
    # Check if the file exists
    file_exists = os.path.isfile(filename)
    
    # If the file exists and is not empty, append the data without header
    if file_exists and os.stat(filename).st_size > 0:
        df.to_csv(filename, mode='a', index=False, header=False)
    else:  # Otherwise, write the header
        df.to_csv(filename, mode='a', index=False)
    
    print(f"Data saved to {filename}")


def main():
    # URL of the webpage to scrape
    url = "https://www.zavattishop.com/en/pool-robots/accessories/dolphin-spare-parts.html"
    models_csv = "models.csv"
    output_csv = "spare_parts.csv"

    # Get models and create models.csv if it doesn't exist
    get_models(url)

    # Read models from models.csv
    models_df = pd.read_csv(models_csv)

    # Iterate through each model row
    for index, model in models_df.iterrows():
        if model['status'] == 'Pending':
            # Get all spare parts for the current model
            model_link = model['model_link']
            model_name = model['model_name']
            spare_parts = get_spare_parts(model_link)

            # Initialize the progress bar
            progress_bar = tqdm(total=len(spare_parts), desc=f"Processing {model_name}")

            # Get details for each spare part and store in a list
            spare_part_details = []
            for spare_part_link in spare_parts:
                spare_part_detail = get_spare_part_details(spare_part_link, model_name)
                spare_part_details.append(spare_part_detail)

                # Update the progress bar
                progress_bar.update(1)

            # Close the progress bar
            progress_bar.close()

            # Save spare part details to output_csv
            save_to_csv(spare_part_details, output_csv)
            # Update model status to 'Done'
            models_df.at[index, 'status'] = 'Done'

            # Update the number of parts for the model
            models_df.at[index, 'num_parts'] = len(spare_parts)

            # Update models.csv with model status and number of parts
            models_df.to_csv(models_csv, index=False)

    print("Scraping completed.")

if __name__ == "__main__":
    main()
