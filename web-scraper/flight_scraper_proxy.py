import asyncio
import csv
import os
import base64
import json
from typing import List, Dict, Optional, Any
import pandas as pd
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

# --- TYPE DEFINITIONS ---
ReturnFlightInfo = Dict[str, str]
RoundTripOption = Dict[str, Any]
FinalFlightData = List[RoundTripOption]
# --- END TYPE DEFINITIONS ---

# ----------------------------
# 1. URL BUILDER CLASS (Fixed for Round Trip)
# ----------------------------

class FlightURLBuilder:
    """Class to handle round-trip flight URL creation with base64 encoding."""
    
    @staticmethod
    def _create_round_trip_bytes(departure: str, destination: str, departure_date: str, return_date: str) -> bytes:
        """Create bytes for round-trip flight."""
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
    def build_round_trip_url(cls, departure: str, destination: str, departure_date: str, return_date: str) -> str:
        """Build a round-trip Google Flights URL."""
        flight_bytes = cls._create_round_trip_bytes(departure, destination, departure_date, return_date)
        base64_str = base64.b64encode(flight_bytes).decode('utf-8')
        modified_str = cls._modify_base64(base64_str)
        return f'https://www.google.com/travel/flights/search?tfs={modified_str}'

# ----------------------------
# 2. PROXY AND SETUP FUNCTIONS
# ----------------------------

class ProxyConfig:
    """Class to handle proxy configuration from environment variables."""
    def __init__(self):
        self.server = os.getenv('PROXY_SERVER')
        self.username = os.getenv('PROXY_USERNAME')
        self.password = os.getenv('PROXY_PASSWORD')
        self.bypass = os.getenv('PROXY_BYPASS')
    
    def get_proxy_settings(self) -> Optional[Dict]:
        if not self.server: 
            return None
        proxy_settings = {"server": self.server}
        if self.username and self.password:
            proxy_settings.update({"username": self.username, "password": self.password})
        if self.bypass:
            proxy_settings["bypass"] = self.bypass
        return proxy_settings
    
    @property
    def is_configured(self) -> bool:
        return bool(self.server)

async def setup_browser():
    """Initialize and return browser and page objects with optional proxy."""
    p = await async_playwright().start()
    browser_settings = {"headless": False}
    proxy_config = ProxyConfig()
    if proxy_config.is_configured:
        proxy_settings = proxy_config.get_proxy_settings()
        if proxy_settings:
            browser_settings["proxy"] = proxy_settings
    browser = await p.chromium.launch(**browser_settings)
    page = await browser.new_page(viewport={"width": 1280, "height": 900})
    return p, browser, page

async def extract_flight_element_text(flight, selector: str, aria_label: Optional[str] = None) -> str:
    """Extract text from a flight element using selector and optional aria-label."""
    if aria_label:
        element = await flight.query_selector(f':scope {selector}[aria-label*="{aria_label}"]')
    else:
        element = await flight.query_selector(f':scope {selector}')
    return await element.inner_text() if element else "N/A"

async def scrape_flight_info(flight) -> Dict[str, str]:
    """Extract all relevant information from a single flight element."""
    departure_time = await extract_flight_element_text(flight, 'span', "Departure time")
    arrival_time = await extract_flight_element_text(flight, 'span', "Arrival time")
    airline = await extract_flight_element_text(flight, ".sSHqwe")
    duration = await extract_flight_element_text(flight, "div.gvkrdb")
    stops = await extract_flight_element_text(flight, "div.EfT7Ae span.ogfYpf")
    price = await extract_flight_element_text(flight, "div.FpEdX span")
    co2_emissions = await extract_flight_element_text(flight, "div.O7CXue")
    emissions_variation = await extract_flight_element_text(flight, "div.N6PNV")
    
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

# ----------------------------
# 3. MAIN SCRAPING LOGIC
# ----------------------------

async def scrape_round_trip_data(round_trip_url) -> FinalFlightData:
    """
    Scrapes round-trip data using a forced reload strategy for stability.
    Focuses on confirming selector reliability.
    """
    final_data: FinalFlightData = []
    playwright, browser, page = await setup_browser()
    
    # Define selectors
    OUTBOUND_FLIGHT_SELECTOR = ".pIav2d" 
    RETURN_FLIGHT_ITEM_SELECTOR = ".pIav2d" 

    try:
        # Initial navigation to get the count
        await page.goto(round_trip_url)
        await page.wait_for_load_state('networkidle', timeout=30000)
        
        await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=20000)
        outbound_flights_list = await page.query_selector_all(OUTBOUND_FLIGHT_SELECTOR)
        initial_outbound_count = len(outbound_flights_list)
        print(f"Found {initial_outbound_count} initial outbound flights to process...")

        # Loop using the total COUNT
        for i in range(initial_outbound_count):
            print(f"Processing outbound flight {i+1} of {initial_outbound_count}...")
            
            # CRITICAL: Reload to ensure a fresh state for the click
            await page.goto(round_trip_url)
            await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=20000)
            await page.wait_for_load_state('domcontentloaded')
            
            # Define the locator for the Nth flight
            outbound_locator = page.locator(OUTBOUND_FLIGHT_SELECTOR).nth(i)
            
            try:
                # A. Ensure the element is visible
                await outbound_locator.scroll_into_view_if_needed(timeout=5000)
                
                # B. Scrape the information for the current outbound flight
                outbound_element = await outbound_locator.element_handle()
                outbound_info = await scrape_flight_info(outbound_element)
                
                # C. Click the element (robust click)
                await outbound_locator.click(timeout=15000, force=True) 
                
                # D. Wait explicitly for the individual return flight item to appear 
                full_return_selector = RETURN_FLIGHT_ITEM_SELECTOR
                
                # Wait for at least one return flight element to be present
                await page.wait_for_selector(full_return_selector, timeout=15000) 
                
                # E. Scrape all visible return flights
                return_elements = await page.query_selector_all(full_return_selector)
                return_flights_data: List[ReturnFlightInfo] = []
                
                for return_element in return_elements:
                    return_info = await scrape_flight_info(return_element)
                    return_flights_data.append(return_info)
                
                # F. Store the combined data
                if return_flights_data:
                    final_data.append({
                        "OutboundFlight": outbound_info,
                        "ReturnFlights": return_flights_data
                    })
                    print(f"   -> SUCCESS: Found and saved {len(return_flights_data)} return flights.")
                else:
                    print(f"   -> Found container but **0** return flights. CHECK RETURN SELECTOR: {RETURN_FLIGHT_ITEM_SELECTOR}")

            except PlaywrightTimeoutError as e:
                print(f"Warning: TIMEOUT on flight {i+1}. Issue likely in selector or click stability. Error: {e}")
            except Exception as e:
                print(f"Warning: Failed to process flight {i+1}. General Error: {e}")
                
        print(f"\nSuccessfully scraped {len(final_data)} complete round-trip options.")
        return final_data

    finally:
        await browser.close()
        await playwright.stop()

# ----------------------------
# 4. DATA SAVING FUNCTIONS
# ----------------------------

def save_structured_data(data: FinalFlightData, filename: str) -> None:
    """Save the nested flight data structure as a JSON file."""
    if data:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Nested round-trip data saved to {filename}")
    else:
        print("No data was scraped to save.")

# ----------------------------
# 5. MAIN EXECUTION
# ----------------------------

if __name__ == "__main__":
    print("Starting Dynamic Round-Trip Scraper...")
    
    # Configure your flight search parameters here
    DEPARTURE = "LAX"           # Los Angeles
    DESTINATION = "SFO"         # New York City
    DEPARTURE_DATE = "2026-12-07"
    RETURN_DATE = "2026-12-12"
    
    # Generate dynamic round-trip URL
    round_trip_url = FlightURLBuilder.build_round_trip_url(
        departure=DEPARTURE,
        destination=DESTINATION,
        departure_date=DEPARTURE_DATE,
        return_date=RETURN_DATE
    )
    
    print(f"Searching flights from {DEPARTURE} to {DESTINATION}")
    print(f"Departure: {DEPARTURE_DATE}, Return: {RETURN_DATE}")
    print("Generated URL:", round_trip_url)
    
    # Run the scraper
    scraped_data = asyncio.run(scrape_round_trip_data(round_trip_url))
    
    # Save the structured data
    output_filename = f"round_trip_{DEPARTURE}_{DESTINATION}_{DEPARTURE_DATE.replace('-', '')}.json"
    save_structured_data(scraped_data, output_filename)