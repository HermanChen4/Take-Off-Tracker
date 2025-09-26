import asyncio
import csv
import os
import base64
import json # New import for saving structured data
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from typing import List, Dict, Optional, Any # Added Any for the FinalFlightData type hint
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# --- TYPE DEFINITIONS FOR STRUCTURED DATA ---
ReturnFlightInfo = Dict[str, str]
RoundTripOption = Dict[str, Any] # OutboundFlight and ReturnFlights
FinalFlightData = List[RoundTripOption]
# --- END TYPE DEFINITIONS ---


class FlightURLBuilder:
    """Class to handle flight URL creation with base64 encoding."""
    
    @staticmethod
    def _create_one_way_bytes(departure: str, destination: str, date: str) -> bytes:
        """Create bytes for one-way flight."""
        return (
            b'\x08\x1c\x10\x02\x1a\x1e\x12\n' + date.encode() +
            b'j\x07\x08\x01\x12\x03' + departure.encode() +
            b'r\x07\x08\x01\x12\x03' + destination.encode() +
            b'@\x01H\x01p\x01\x82\x01\x0b\x08\xfc\x06`\x04\x08'
        )
        
    @staticmethod
    def _create_round_trip_bytes(departure: str, destination: str, departure_date: str, return_date: str) -> bytes:
        """Create bytes for a round-trip flight."""
        # Byte sequence for round trip, includes both dates
        return (
            b'\x08\x1e\x10\x02\x1a\x1e\x12\n' + departure_date.encode() +
            b'*\x0e\x12\x0c\n\n' + return_date.encode() +
            b'j\x07\x08\x01\x12\x03' + departure.encode() +
            b'r\x07\x08\x01\x12\x03' + destination.encode() +
            b'@\x01H\x01p\x01\x82\x01\x0b\x08\xfc\x06`\x04\x08'
        )
    
    @staticmethod
    def _modify_base64(encoded_str: str) -> str:
        """Add underscores at the specific position in base64 string."""
        insert_index = len(encoded_str) - 6
        return encoded_str[:insert_index] + '_' * 7 + encoded_str[insert_index:]

    @classmethod
    def build_url(
        cls,
        departure: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None # Added optional return_date
    ) -> str:
        """Build a one-way or round-trip Google Flights URL."""
        if return_date:
            flight_bytes = cls._create_round_trip_bytes(departure, destination, departure_date, return_date)
            prefix = 'https://www.google.com/travel/flights/search?trip'
        else:
            flight_bytes = cls._create_one_way_bytes(departure, destination, departure_date)
            prefix = 'https://www.google.com/travel/flights/search?tfs='
            
        base64_str = base64.b64encode(flight_bytes).decode('utf-8')
        modified_str = cls._modify_base64(base64_str)
        return f'{prefix}{modified_str}'


class ProxyConfig:
    """Class to handle proxy configuration from environment variables."""
    def __init__(self):
        """Initialize proxy configuration from environment variables."""
        self.server = os.getenv('PROXY_SERVER')
        self.username = os.getenv('PROXY_USERNAME')
        self.password = os.getenv('PROXY_PASSWORD')
        self.bypass = os.getenv('PROXY_BYPASS')

    def get_proxy_settings(self) -> Optional[Dict]:
        """Return proxy settings in the format expected by Playwright."""
        if not self.server:
            return None

        proxy_settings = {
            "server": self.server
        }
        if self.username and self.password:
            proxy_settings.update({
                "username": self.username,
                "password": self.password
            })
        if self.bypass:
            proxy_settings["bypass"] = self.bypass
        return proxy_settings

    @property
    def is_configured(self) -> bool:
        """Check if proxy is properly configured."""
        return bool(self.server)


async def setup_browser():
    """Initialize and return browser and page objects with proxy settings from env."""
    p = await async_playwright().start()
    
    browser_settings = {
        "headless": False
    }
    
    # Initialize proxy configuration from environment variables
    proxy_config = ProxyConfig()
    if proxy_config.is_configured:
        proxy_settings = proxy_config.get_proxy_settings()
        if proxy_settings:
            browser_settings["proxy"] = proxy_settings
    
    browser = await p.chromium.launch(**browser_settings)
    page = await browser.new_page()
    
    return p, browser, page


async def extract_flight_element_text(flight, selector: str, aria_label: Optional[str] = None) -> str:
    """Extract text from a flight element using selector and optional aria-label."""
    if aria_label:
        element = await flight.query_selector(f'{selector}[aria-label*="{aria_label}"]')
    else:
        element = await flight.query_selector(selector)
    return await element.inner_text() if element else "N/A"

async def scrape_flight_info(flight) -> Dict[str, str]:
    """Extract all relevant information from a single flight element."""
    departure_time = await extract_flight_element_text(flight, 'span', "Departure time")
    arrival_time =  await extract_flight_element_text(flight, 'span', "Arrival time")
    airline = await extract_flight_element_text(flight, ".sSHqwe")
    duration = await extract_flight_element_text(flight, "div.gvkrdb")
    stops =  await extract_flight_element_text(flight, "div.EfT7Ae span.ogfYpf")
    price =  await extract_flight_element_text(flight, "div.FpEdX span")
    co2_emissions =  await extract_flight_element_text(flight, "div.O7CXue")
    emissions_variation =  await extract_flight_element_text(flight, "div.N6PNV")
    return {
        "Departure Time": departure_time,
        "Arrival Time": arrival_time,
        "Airline Company": airline,
        "Flight Duration": duration,
        "Stops": stops,
        "Price": price,
        "co2 emissions": co2_emissions,
        "emissions variation": emissions_variation
    }

# Retaining original functions but they are NOT used for the round-trip JSON structure
# They are only here for completeness. The main logic uses JSON saving.
def clean_csv(filename: str):
    """Clean unwanted characters from the saved CSV file."""
    try:
        data = pd.read_csv(filename, encoding="utf-8")
        
        def clean_text(value):
            if isinstance(value, str):
                return value.replace('Â', '').replace(' ', ' ').replace('Ã', '').replace('¶', '').strip()
            return value

        cleaned_data = data.applymap(clean_text)
        cleaned_file_path = f"{filename}"
        cleaned_data.to_csv(cleaned_file_path, index=False)
        print(f"Cleaned CSV saved to: {cleaned_file_path}")
    except Exception as e:
        print(f"Could not clean CSV: {e}")

def save_to_csv(data: List[Dict[str, str]], filename: str = "flight_data_proxy.csv") -> None:
    """Save flight data to a CSV file (for one-way/flat data only)."""
    if not data:
        return
    
    headers = list(data[0].keys())
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    
    # Clean the saved CSV
    clean_csv(filename)
# End of original helper functions


async def scrape_round_trip_data(round_trip_url: str) -> FinalFlightData:
    """
    Scrapes round-trip data by clicking each outbound flight to reveal and scrape 
    its corresponding return flights, saving the data as a nested structure.
    """
    final_data: FinalFlightData = []
    playwright, browser, page = await setup_browser()

    try:
        await page.goto(round_trip_url)
        
        # 1. Wait for the initial outbound flights to load
        OUTBOUND_FLIGHT_SELECTOR = ".pIav2d"
        await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=15000)

        # 2. Get all outbound flight elements
        # Note: We query the DOM here, but the list becomes stale after a reload.
        outbound_flights = await page.query_selector_all(OUTBOUND_FLIGHT_SELECTOR)

        print(f"Found {len(outbound_flights)} initial outbound flights to process...")
        
        # Loop over the NUMBER of outbound flights, handling re-fetching inside the loop
        for i in range(len(outbound_flights)):
            # Re-fetch the list of outbound flights on each iteration to handle page reloads
            outbound_flights_list = await page.query_selector_all(OUTBOUND_FLIGHT_SELECTOR)
            
            # Ensure the element for the current index still exists
            if i >= len(outbound_flights_list):
                print(f"Skipping index {i} as page state changed.")
                continue

            outbound_element = outbound_flights_list[i]
            
            # A. Scrape the information for the current outbound flight
            outbound_info = await scrape_flight_info(outbound_element)
            
            # B. Click the element to reveal return flights
            print(f"Processing outbound flight {i+1} of {len(outbound_flights)}...")
            await outbound_element.click()
            
            # C. Wait for the return flight section to load
            RETURN_FLIGHT_SELECTOR = ".pIav2d"
            RETURN_CONTAINER_SELECTOR = ".F0c0s" # The panel that appears with return options

            try:
                # Wait for the main return flight container to appear
                await page.wait_for_selector(RETURN_CONTAINER_SELECTOR, timeout=10000)
            except Exception as e:
                print(f"Warning: Could not load return flights for outbound flight {i+1}. Skipping. Error: {e}")
                
                # Try to reset the page state before continuing
                try:
                    close_button = await page.query_selector("button[aria-label='Close']")
                    if close_button:
                        await close_button.click()
                except:
                    pass # Ignore if close button fails
                continue 

            # D. Scrape all visible return flights
            # Select flights only within the newly opened return container
            return_elements = await page.query_selector_all(RETURN_CONTAINER_SELECTOR + " " + RETURN_FLIGHT_SELECTOR)
            return_flights_data: List[ReturnFlightInfo] = []
            
            for return_element in return_elements:
                return_info = await scrape_flight_info(return_element)
                return_flights_data.append(return_info)
            
            # E. Store the combined data
            final_data.append({
                "OutboundFlight": outbound_info,
                "ReturnFlights": return_flights_data
            })
            
            print(f"   -> Found {len(return_flights_data)} return flights.")

            # F. Reset the page state by clicking the close button
            try:
                close_button = await page.query_selector("button[aria-label='Close']")
                if close_button:
                    await close_button.click()
                    await page.wait_for_selector(RETURN_CONTAINER_SELECTOR, state='hidden', timeout=5000)
                else:
                    # Fallback if close button not found (slower)
                    await page.goto(round_trip_url)
                    await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=15000)
            except Exception as e:
                 print(f"Error resetting page state: {e}. Attempting full reload.")
                 await page.goto(round_trip_url)
                 await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=15000)
                 
        print(f"\nSuccessfully scraped {len(final_data)} complete round-trip options.")
        return final_data

    finally:
        await browser.close()
        await playwright.stop()


# The original one-way scraper is kept but not executed in __main__
async def scrape_flight_data(one_way_url):
    flight_data = []
    playwright, browser, page = await setup_browser()
    try:
        await page.goto(one_way_url)
        await page.wait_for_selector(".pIav2d")
        flights = await page.query_selector_all(".pIav2d")
        for flight in flights:
            flight_info = await scrape_flight_info(flight)
            flight_data.append(flight_info)
        save_to_csv(flight_data)
    finally:
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    # Define round trip parameters
    DEPARTURE = "JFK"
    DESTINATION = "CUN"
    DEP_DATE = "2025-09-25"
    RET_DATE = "2025-10-02"
    OUTPUT_FILE = "round_trip_options.json" # Use JSON for the nested structure

    round_trip_url = FlightURLBuilder.build_url(
        departure=DEPARTURE,
        destination=DESTINATION,
        departure_date=DEP_DATE,
        return_date=RET_DATE
    )
    print("Round-trip URL:", round_trip_url)

    # Run the round-trip scraper
    scraped_data = asyncio.run(scrape_round_trip_data(round_trip_url))
    
    # Save the complex structured data as JSON
    if scraped_data:
        try:
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(scraped_data, f, indent=4)
            print(f"Nested round-trip data saved to {OUTPUT_FILE}")
        except Exception as e:
            print(f"Error saving data to JSON: {e}")
    else:
        print("No data was scraped to save.")