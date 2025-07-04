import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from csv import writer
import traceback # For more detailed error reporting

# Base URL for the real estate listing site
base_site = "https://bina.az/baki/alqi-satqi/menziller"

# Configure Chrome WebDriver options
options = webdriver.ChromeOptions()
options.add_argument("--headless=new") # Run browser in headless mode, i.e., without a visible UI

# List to store data from all processed ads
all_ad_data = []

# Initialize driver variable to None, so it can be accessed in the finally block even if try fails
driver = None

try:
    # Initialize the Chrome WebDriver
    driver = webdriver.Chrome(options=options)
    # Navigate to the base URL
    driver.get(base_site)
    print(f"Navigated to: {base_site}")

    # Use a set to keep track of unique ad links to avoid processing the same ad multiple times
    unique_ad_links = set()

    # Loop through a maximum of 300 pages (can be adjusted)
    page_num = 1
    while page_num < 301:
        print(f"\n--- Processing Page {page_num} ---")

        # Wait for the main listing cards to load on the current page.
        # This ensures the page content is available before attempting to scrape.
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "items-i"))
            )
            print("Main listing cards loaded successfully on current page.")
        except Exception as e:
            print(f"Error waiting for listing cards on page {page_num}: {e}")
            break # If cards don't load, something is wrong, stop the pagination loop.

        # --- First pass: Extract basic data and links from the current page ---
        # Find all individual ad cards on the page
        ad_cards = driver.find_elements(By.CLASS_NAME, 'items-i')
        print(f"Found {len(ad_cards)} individual listing cards on page {page_num}.")

        # If no ad cards are found on a subsequent page, it typically means we've reached the end of listings
        if not ad_cards and page_num > 1:
            print(f"No ad cards found on page {page_num}. Assuming end of listings.")
            break

        current_page_ad_data = [] # Temporarily store data for current page to check for duplicates
        for i, card in enumerate(ad_cards):
            # Initialize a dictionary for each ad with default empty values
            ad_info = {
                'Ad ID': '',
                'Category': '',
                'Price': '',
                'Currency': '',
                'Price per m2': '',
                'Floor Number': '',
                'Room Count': '',
                'Area': '',
                'Location': '',
                'Excerpt': '',
                'Last Updated': '',
                'State of Repair': '',
                'Link': ''
            }

            # Extract Location
            try:
                location_elem = card.find_element(By.CLASS_NAME, 'location')
                ad_info['Location'] = location_elem.text.strip()
            except Exception:
                # Pass if element not found, value will remain empty string
                pass

            # Extract Ad Link and add to unique_ad_links set
            try:
                link_elem = card.find_element(By.CLASS_NAME, 'item_link')
                link = link_elem.get_attribute('href')
                # Check if link is valid and has not been added before
                if link and link not in unique_ad_links:
                    ad_info['Link'] = link
                    current_page_ad_data.append(ad_info)
                    unique_ad_links.add(link)
                else:
                    # print(f"Skipping duplicate or invalid link: {link}") # Uncomment for debugging duplicates
                    pass
            except Exception:
                pass

        # Add only the new, unique ads found on this page to the main list
        all_ad_data.extend(current_page_ad_data)
        print(f"Collected {len(current_page_ad_data)} new unique ads from page {page_num}. Total unique ads so far: {len(all_ad_data)}")

        # --- Try to find and click the "Next" pagination link ---
        next_page_link = None
        try:
            # Wait for the "Next" page link to be clickable
            next_page_link = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//nav[@class='pagination']//span[@class='next']/a"))
            )
            print("Found 'Next' page link.")

            # Click the link using JavaScript for better reliability, especially for hidden or overlaid elements
            driver.execute_script("arguments[0].click();", next_page_link)
            page_num += 1 # Increment page number for the next iteration
            time.sleep(3) # Give time for the next page to load completely. Adjust as needed.

        except Exception as e:
            print(f"No 'Next' page link found or clickable. Assuming all pages processed. Error: {e}")
            break # Exit loop if no next page link is found or clickable

    print("\n300 main page data collected.") # Indicates completion of the first pass

    # --- Second pass: Visit each ad's detail page and extract more specific data ---
    print(f"\nStarting detail page extraction for {len(all_ad_data)} unique ads.")
    for i, ad_entry in enumerate(all_ad_data):
        link = ad_entry['Link']
        if not link:
            print(f"Skipping ad {i+1} due to missing link.")
            continue # Skip to the next ad if the link is somehow missing

        try:
            # Navigate to the individual ad's detail page
            driver.get(link)
            print(f"Navigating to detail page for ad {i+1}/{len(all_ad_data)}: {link}")

            # Wait for a key element on the detail page to load, indicating the page is ready
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "product-sidebar__box"))
            )
            print(f"Detail page for ad {i+1} loaded.")

            # -- Extracting Ad ID --
            try:
                ad_id_div = driver.find_element(By.CLASS_NAME, 'product-actions__id')
                ad_id_full_text = ad_id_div.text.strip()
                # Split the text by ':' and take the second part to get the actual ID
                ad_entry['Ad ID'] = ad_id_full_text.split(':')[-1].strip()
            except Exception as e:
                print(f"Detail Page {link}: Error extracting Ad ID: {e}")
                ad_entry['Ad ID'] = 'N/A (Not found)'

            #--- EXTRACT Price, Currency, Price per m2 from DETAIL PAGE ---
            try:
                product_price_box = driver.find_element(By.CLASS_NAME, 'product-price')
                # Extract Price Value
                price_val_elem = product_price_box.find_element(By.CLASS_NAME, 'price-val')
                ad_entry['Price'] = price_val_elem.text.strip()

                # Extract Currency
                price_cur_elem = product_price_box.find_element(By.CLASS_NAME, 'price-cur')
                ad_entry['Currency'] = price_cur_elem.text.strip()

                # Extract Price per m2. It's typically the second element with class 'product-price__i'
                price_per_m2_elems = product_price_box.find_elements(By.CLASS_NAME, 'product-price__i')
                if len(price_per_m2_elems) > 1:
                    ad_entry['Price per m2'] = price_per_m2_elems[1].text.strip()
                else:
                    ad_entry['Price per m2'] = 'N/A (Not found)'

            except Exception as e:
                print(f"Detail Page {link}: Error extracting price details: {e}")
                # Assign 'ERROR' if any price-related extraction fails
                ad_entry['Price'] = 'ERROR'
                ad_entry['Currency'] = 'ERROR'
                ad_entry['Price per m2'] = 'ERROR'

            # --- Extract various properties like Category, Floor Number, Area, Room Count, Excerpt, State of Repair ---
            try:
                product_properties_div = driver.find_element(By.CLASS_NAME, 'product-properties__column')
                property_items = product_properties_div.find_elements(By.CLASS_NAME, 'product-properties__i')

                for prop_item in property_items:
                    try:
                        label_elem = prop_item.find_element(By.CLASS_NAME, 'product-properties__i-name')
                        value_elem = prop_item.find_element(By.CLASS_NAME, 'product-properties__i-value')
                        label = label_elem.text.strip()
                        value = value_elem.text.strip()

                        # Map extracted labels to the corresponding dictionary keys
                        if label == "Kateqoriya":
                            ad_entry['Category'] = value
                        elif label == "Mərtəbə":
                            ad_entry['Floor Number'] = value
                        elif label == "Sahə":
                            ad_entry['Area'] = value
                        elif label == "Otaq sayı":
                            ad_entry['Room Count'] = value
                        elif label == "Çıxarış":
                            ad_entry['Excerpt'] = value
                        elif label == "Təmir":
                            ad_entry['State of Repair'] = value

                    except Exception as prop_e:
                        # print(f"Error extracting property item: {prop_e}") # Uncomment for debugging individual property extraction errors
                        pass # Continue processing other properties even if one fails

            except Exception as e:
                print(f"Detail Page {link}: Error extracting 'product-properties' section: {e}")
                # Assign 'ERROR' to all related fields if the main properties section cannot be found
                ad_entry['Category'] = 'ERROR'
                ad_entry['Floor Number'] = 'ERROR'
                ad_entry['Room Count'] = 'ERROR'
                ad_entry['Area'] = 'ERROR'
                ad_entry['Excerpt'] = 'ERROR'
                ad_entry['State of Repair'] = 'ERROR'
            
            # --- EXTRACT 'Last Updated' Date/Time ---
            try:
                # Find the main product-statistics div
                product_statistics_div = driver.find_element(By.CLASS_NAME, 'product-statistics')
                try:
                    # Find the span containing "Yeniləndi:" (Updated:) text
                    last_updated_span = product_statistics_div.find_element(By.XPATH, ".//span[contains(text(), 'Yeniləndi:')]")
                    full_date_time_text = last_updated_span.text.strip()
                    # Remove the "Yeniləndi:" prefix to get just the date and time
                    ad_entry['Last Updated'] = full_date_time_text.replace("Yeniləndi:", "").strip()
                except Exception as e:
                    # print(f"Detail Page {link}: Error extracting Last Updated date: {e}") # Uncomment for debugging
                    ad_entry['Last Updated'] = 'N/A (Not found)'

            except Exception as e:
                print(f"Detail Page {link}: Error locating product-statistics section: {e}")
                ad_entry['Last Updated'] = 'ERROR'

            time.sleep(0.1) # Small delay after processing each detail page to avoid overwhelming the server

        except Exception as e:
            print(f"Error navigating to or processing detail page for ad {i+1} ({link}): {e}")
            traceback.print_exc() # Print full traceback for detailed error analysis
            # Mark all fields as 'ERROR' if navigation or main detail page load fails
            ad_entry['Ad ID'] = 'ERROR (Navigation/Page Load)'
            ad_entry['State of Repair'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Price'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Currency'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Price per m2'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Category'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Floor Number'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Room Count'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Excerpt'] = 'ERROR (Navigation/Page Load)'
            ad_entry['Last Updated'] = 'ERROR (Navigation/Page Load)'

    print("\nData extraction from detail pages complete.")

    # --- Write all collected data to CSV ---
    # Open a CSV file in write mode, with utf-8 encoding for proper character handling
    with open('bina_data.csv', 'w', newline='', encoding='utf-8') as bina_csv:
        csv_writer = writer(bina_csv)
        if all_ad_data: # Ensure there's data to get headers from
            # Write the header row using the keys from the first ad entry
            csv_writer.writerow(list(all_ad_data[0].keys()))
            # Write data rows
            for row_data in all_ad_data:
                csv_writer.writerow(list(row_data.values()))
        else:
            print("No data collected to write to CSV.")
    print("All collected data written to bina_data.csv")

except Exception as e:
    # Catch any unexpected errors that occur during the entire scraping process
    print(f"An error occurred during overall scraping: {e}")
    traceback.print_exc() # Print the full traceback for debugging

finally:
    # Ensure the browser is closed even if an error occurs
    if driver: # Check if the driver was successfully initialized
        driver.quit()
        print("Browser closed.")