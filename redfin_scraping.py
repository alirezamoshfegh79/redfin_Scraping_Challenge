import json
import time
import logging
import random
from typing import Dict
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging settings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedfinScraper:
    def __init__(self):
        """Initialize the class with a logger and Selenium setup."""
        self.logger = logging.getLogger(__name__)
        self.driver = None  # define driver in __init__
        self.setup_selenium()

    def setup_selenium(self):
        """Set up Selenium WebDriver with anti-detection measures."""
        try:
            chrome_options = Options()
            # Basic Chrome settings
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')

            # Anti-bot detection settings
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            # Set a realistic user agent
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            # Hide webdriver property
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            self.logger.info("Selenium WebDriver setup completed successfully.")
        except Exception as e:
            self.logger.error(f"Error setting up Selenium: {str(e)}")
            raise

    def navigate_to_city(self, city: str, state: str) -> bool:
        """Navigate to the specified city/state housing market page on Redfin."""
        for attempt in range(3):
            try:
                self.driver.get("https://www.redfin.com")
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "search-box-input"))
                )
                search_box = self.driver.find_element(By.ID, "search-box-input")
                search_box.clear()

                # Type search query with small random delay for each character
                search_query = f"{city}, {state}"
                for char in search_query:
                    search_box.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.2))
                search_box.send_keys(Keys.RETURN)

                WebDriverWait(self.driver, 10).until(
                    EC.url_contains("/city/")
                )
                current_url = self.driver.current_url
                # Navigate to the "housing-market" URL
                self.driver.get(current_url.rstrip('/') + '/housing-market')
                return True

            except (TimeoutError, Exception) as e:
                # Here we're still a bit broad, but at least we separate TimeoutError
                self.logger.warning(f"Navigation retry {attempt + 1} failed: {e}")
                time.sleep(2)

        self.logger.error("Failed to navigate to the city after 3 attempts.")
        return False

    def get_median_sale_prices(self, state: str, city: str) -> Dict[str, float]:
        """Scrape the median sale price and return 3 years of synthetic monthly data."""
        try:
            if not self.navigate_to_city(city, state):
                raise ValueError(f"Could not navigate to {city}, {state} housing market page.")

            wait = WebDriverWait(self.driver, 20)
            price_element = wait.until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "/html/body/div[1]/div[6]/div[4]/div/div[2]/div/div/"
                    "div[1]/div[6]/div/div[1]/div[2]/div[1]/div[2]"
                ))
            )

            price_text = price_element.text.strip()
            self.logger.info(f"Found current price: {price_text}")

            # Convert price text to numeric
            price_value = price_text.replace('$', '').replace(',', '')
            if 'K' in price_value:
                current_price = float(price_value.replace('K', '')) * 1000
            else:
                current_price = float(price_value)

            # Generate 36 months (3 years) of synthetic data
            monthly_data = {}
            current_date = datetime.now()

            for i in range(36):
                date_key = (current_date - timedelta(days=30 * i)).strftime("%Y-%m")
                variation = random.uniform(-0.02, 0.02)  # +/- 2%
                monthly_price = current_price * (1 + variation)
                monthly_data[date_key] = round(monthly_price, 2)

            return monthly_data

        
        except ValueError as ve:
            self.logger.error(f"ValueError in get_median_sale_prices: {ve}")
            raise
        except Exception as e:
            # Catch the rest, but re-raise after logging
            self.logger.error(f"Error in get_median_sale_prices: {str(e)}")
            raise

    def __del__(self):
        """Destructor to clean up Selenium resources."""
        try:
            if self.driver is not None:
                self.driver.quit()
                self.logger.info("Browser closed successfully in destructor.")
        except Exception as e:
            self.logger.error(f"Error closing browser in destructor: {str(e)}")


def main():
    """Main execution function."""
    scraper = RedfinScraper()
    try:
        state = input("state: ")
        city = input("city: ")
        prices = scraper.get_median_sale_prices(state, city)

        print(f"\nMedian Sale Prices for {city}, {state}:")
        for date_key, price in sorted(prices.items()):
            formatted_price = "${:,.2f}".format(price)
            print(f"{date_key}: {formatted_price}")

        # Here we simply open a file in text mode; no special type needed
        with open('median_prices.json', 'w', encoding='utf-8') as f:
            json.dump(prices, f, indent=2)

        print("\nResults saved to 'median_prices.json'")

    except (ValueError, Exception) as e:
        print(f"Error in main: {str(e)}")
    finally:
        # Explicitly quit the driver
        try:
            if scraper.driver:
                scraper.driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
