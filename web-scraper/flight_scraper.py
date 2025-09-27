import asyncio
import csv
import os
import base64
import json
import re
from typing import List, Dict, Optional, Any
import pandas as pd
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

# --- TYPE DEFINITIONS ---
ReturnFlightInfo = Dict[str, str]
RoundTripOption = Dict[str, Any]
FinalFlightData = List[RoundTripOption]
# --- END TYPE DEFINITIONS ---

# ----------------------------
# 1. PROXY AND SETUP FUNCTIONS
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
    
    # Create incognito context (equivalent to incognito mode)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    page = await context.new_page()
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
# 2. DYNAMIC FORM FILLING (Your Current Approach)
# ----------------------------

async def dynamic_form_fill(page: Page, departure: str, destination: str, departure_date: str, return_date: str, passengers: int = 2) -> bool:
    """Fill form using dynamic approach that works with any destination."""
    
    print(f"Using dynamic approach: {departure} to {destination}, {passengers} passengers")
    
    try:
        # Navigate to Google Flights
        await page.goto("https://www.google.com/travel/flights")
        await page.wait_for_load_state('networkidle', timeout=15000)
        print("✅ Navigated to Google Flights")
        
        # Set passengers (if more than 1)
        if passengers > 1:
            print(f"Setting {passengers} passengers...")
            await page.get_by_label("1 passenger, change number of").click()
            
            # Add adults (passengers - 1 since we start with 1)
            for i in range(passengers - 1):
                await page.get_by_role("button", name="Add adult").click()
                await page.wait_for_timeout(200)
            
            await page.get_by_role("button", name="Done").click()
            await page.wait_for_timeout(1000)
            print(f"✅ Set to {passengers} passengers")
        
        # Fill departure location
        print(f"Setting departure: {departure}")
        await page.get_by_role("combobox", name="Where from?").click()
        await page.wait_for_timeout(500)
        
        await page.get_by_role("combobox", name="Where else?").fill(departure)
        
        # Wait for suggestions to appear before trying to click
        try:
            await page.wait_for_selector("div[role='option']", timeout=5000)
            await page.wait_for_timeout(500)  # Small delay for suggestions to fully load
            await page.locator("div[role='option']").first.click()
            print("✅ Selected first departure suggestion")
        except:
            print("⚠️ No suggestions found, using Enter key for departure")
            await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)
        
        # Fill destination location  
        print(f"Setting destination: {destination}")
        await page.get_by_role("combobox", name="Where to?").click()
        await page.wait_for_timeout(500)
        
        await page.get_by_role("combobox", name="Where to?").fill(destination)
        
        # Wait for suggestions to appear before trying to click
        try:
            await page.wait_for_selector("div[role='option']", timeout=5000)
            await page.wait_for_timeout(500)  # Small delay for suggestions to fully load
            await page.locator("div[role='option']").first.click()
            print("✅ Selected first destination suggestion")
        except:
            print("⚠️ No suggestions found, using Enter key for destination")
            await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)
        
        # Set departure date
        print(f"Setting departure date: {departure_date}")
        departure_field = page.get_by_role("textbox", name="Departure")
        
        # Try multiple methods to set the date reliably
        for attempt in range(3):
            try:
                await departure_field.click()
                await page.wait_for_timeout(300)
                
                # Method 1: Clear and type
                await departure_field.fill("")
                await page.wait_for_timeout(200)
                await departure_field.type(departure_date, delay=50)
                await page.wait_for_timeout(500)
                
                # Check if field has any content (not empty)
                departure_value = await departure_field.input_value()
                if departure_value and len(departure_value.strip()) > 0:
                    print(f"✅ Set departure date (attempt {attempt + 1}): {departure_value}")
                    break
                else:
                    print(f"⚠️ Departure date empty after attempt {attempt + 1}, retrying...")
                    if attempt == 2:  # Last attempt, try keyboard method
                        await departure_field.click()
                        await page.keyboard.press("Control+a")
                        await page.keyboard.type(departure_date, delay=100)
                        await page.wait_for_timeout(500)
                        
            except Exception as e:
                print(f"⚠️ Error setting departure date attempt {attempt + 1}: {e}")
                if attempt == 2:
                    print("❌ Failed to set departure date after 3 attempts")
        
        # Set return date
        print(f"Setting return date: {return_date}")
        return_field = page.get_by_role("textbox", name="Return")
        
        # Try multiple methods to set the date reliably
        for attempt in range(3):
            try:
                await return_field.click()
                await page.wait_for_timeout(300)
                
                # Method 1: Clear and type
                await return_field.fill("")
                await page.wait_for_timeout(200)
                await return_field.type(return_date, delay=50)
                await page.wait_for_timeout(500)
                
                # Check if field has any content (not empty)
                return_value = await return_field.input_value()
                if return_value and len(return_value.strip()) > 0:
                    print(f"✅ Set return date (attempt {attempt + 1}): {return_value}")
                    break
                else:
                    print(f"⚠️ Return date empty after attempt {attempt + 1}, retrying...")
                    if attempt == 2:  # Last attempt, try keyboard method
                        await return_field.click()
                        await page.keyboard.press("Control+a")
                        await page.keyboard.type(return_date, delay=100)
                        await page.wait_for_timeout(500)
                        
            except Exception as e:
                print(f"⚠️ Error setting return date attempt {attempt + 1}: {e}")
                if attempt == 2:
                    print("❌ Failed to set return date after 3 attempts")
        
        # Wait a moment for any field validation
        await page.wait_for_timeout(1000)
        
        # Final verification - check both fields have content
        final_dep_value = await departure_field.input_value()
        final_ret_value = await return_field.input_value()
        
        if not final_dep_value or not final_ret_value:
            print(f"⚠️ Date field verification: Departure='{final_dep_value}', Return='{final_ret_value}'")
            return False  # Indicate form filling failed
        
        # Click Done for dates
        await page.get_by_role("button", name="Done. Search for one-way").click()
        await page.wait_for_timeout(500)
        print("✅ Clicked Done for dates")
        
        # Search for flights
        print("Searching for flights...")
        await page.get_by_role("button", name="Search").click()
        print("✅ Clicked Search button")
        
        # Wait for flight results
        await page.wait_for_load_state('networkidle', timeout=30000)
        
        # Check if we got flight results
        try:
            await page.wait_for_selector(".pIav2d", timeout=15000)
            print("✅ SUCCESS: Flight results found!")
            return True
        except:
            print("❌ No flight results found")
            current_url = page.url
            print(f"Current URL: {current_url}")
            return False
            
    except Exception as e:
        print(f"❌ Form filling failed: {e}")
        return False

# ----------------------------
# 3. ROUND-TRIP SCRAPING LOGIC (From Your GitHub - Fixed)
# ----------------------------

async def scrape_round_trip_data_dynamic(page: Page) -> FinalFlightData:
    """
    Scrapes round-trip data by clicking outbound flights and recording return options.
    Uses a more robust approach without excessive reloading.
    """
    final_data: FinalFlightData = []
    
    # Define selectors
    OUTBOUND_FLIGHT_SELECTOR = ".pIav2d" 
    RETURN_CONTAINER_SELECTOR = ".Rk10dc"  # Container that appears with return flights
    
    try:
        # Wait for the initial outbound flights to load
        await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=20000)
        await page.wait_for_load_state('domcontentloaded')
        
        # Get the count of outbound flights initially (limit to reasonable number)
        outbound_flights_list = await page.query_selector_all(OUTBOUND_FLIGHT_SELECTOR)
        initial_outbound_count = min(len(outbound_flights_list), 15)  # Limit to 15 for stability
        print(f"Found {len(outbound_flights_list)} outbound flights, processing first {initial_outbound_count}...")

        # Store the base URL for reloading
        base_url = page.url

        # Loop through outbound flights
        for i in range(initial_outbound_count):
            print(f"Processing outbound flight {i+1} of {initial_outbound_count}...")
            
            try:
                # Reload page for fresh state every few flights to prevent stale elements
                if i > 0 and i % 5 == 0:
                    print(f"   -> Refreshing page after {i} flights...")
                    await page.goto(base_url)
                    await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=15000)
                    await page.wait_for_load_state('domcontentloaded')
                
                # Get current flight elements (refresh the list)
                current_flights = await page.query_selector_all(OUTBOUND_FLIGHT_SELECTOR)
                if i >= len(current_flights):
                    print(f"   -> Flight {i+1} no longer available, skipping...")
                    continue
                
                # Get the specific outbound flight
                outbound_element = current_flights[i]
                
                # Scroll to element
                await outbound_element.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                
                # Scrape outbound flight info BEFORE clicking
                outbound_info = await scrape_flight_info(outbound_element)
                
                # Click to reveal return flights
                await outbound_element.click(force=True)
                
                # Wait for return flight container to appear
                try:
                    await page.wait_for_selector(RETURN_CONTAINER_SELECTOR, timeout=10000)
                    print(f"   -> Return flights container appeared")
                    
                    # Wait a bit for return flights to fully load
                    await page.wait_for_timeout(1000)
                    
                    # Find return flights within the container
                    return_flight_selector = f"{RETURN_CONTAINER_SELECTOR} .pIav2d"
                    return_elements = await page.query_selector_all(return_flight_selector)
                    
                    if not return_elements:
                        # Fallback: try broader selector
                        return_elements = await page.query_selector_all(".pIav2d")
                        # Filter to only get the new ones (return flights)
                        return_elements = return_elements[initial_outbound_count:]
                    
                    return_flights_data: List[ReturnFlightInfo] = []
                    
                    for return_element in return_elements:
                        try:
                            return_info = await scrape_flight_info(return_element)
                            # Simple check to avoid duplicating outbound flight data
                            if return_info != outbound_info:
                                return_flights_data.append(return_info)
                        except Exception as e:
                            print(f"     -> Error scraping return flight: {e}")
                            continue
                    
                    # Store the combined data
                    if return_flights_data:
                        final_data.append({
                            "OutboundFlight": outbound_info,
                            "ReturnFlights": return_flights_data
                        })
                        print(f"   -> SUCCESS: Found and saved {len(return_flights_data)} return flights.")
                    else:
                        print(f"   -> No valid return flights found")
                    
                    # Close the return flight selection (try to find close button)
                    try:
                        await page.goto(base_url)
                        await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=15000)
                        await page.wait_for_load_state('domcontentloaded')
                    except:
                        # Fallback: reload page
                        await page.goto(base_url)
                        await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=15000)
                        await page.wait_for_load_state('domcontentloaded')
                
                except PlaywrightTimeoutError:
                    print(f"   -> TIMEOUT waiting for return flights container")
                    continue
                    
            except Exception as e:
                print(f"   -> Error processing flight {i+1}: {e}")
                # Try to reload and continue
                try:
                    await page.goto(base_url)
                    await page.wait_for_selector(OUTBOUND_FLIGHT_SELECTOR, timeout=15000)
                    await page.wait_for_load_state('domcontentloaded')
                except:
                    print(f"   -> Could not recover from error, stopping")
                    break
                continue
                
        print(f"\nSuccessfully scraped {len(final_data)} complete round-trip options.")
        return final_data

    except Exception as e:
        print(f"Error in round-trip scraping: {e}")
        return final_data

# ----------------------------
# 4. MAIN SCRAPING LOGIC (Combined Approach)
# ----------------------------

async def scrape_complete_round_trip_flights(departure: str, destination: str, departure_date: str, return_date: str, passengers: int = 2) -> FinalFlightData:
    """
    Complete round-trip flight scraper that combines dynamic form filling with round-trip scraping.
    """
    
    flight_data = []
    playwright, browser, page = await setup_browser()
    
    try:
        # Step 1: Fill the form using dynamic approach
        success = await dynamic_form_fill(page, departure, destination, departure_date, return_date, passengers)
        
        if success:
            # Step 2: Use round-trip scraping logic from GitHub
            flight_data = await scrape_round_trip_data_dynamic(page)
        else:
            print("❌ Could not load flight results, skipping scraping")
        
        return flight_data

    finally:
        print("Keeping browser open for 10 seconds for inspection...")
        await page.wait_for_timeout(10000)
        await browser.close()
        await playwright.stop()

# ----------------------------
# 5. SIMPLIFIED FLIGHT SCRAPING (For One-Way or Flat Results)
# ----------------------------

async def scrape_all_visible_flights(page: Page) -> List[Dict[str, str]]:
    """
    Scrape all visible flights on the results page without opening individual modals.
    """
    flight_data = []
    
    try:
        # Wait for flights to load
        await page.wait_for_selector(".pIav2d", timeout=15000)
        
        # Get all flight elements
        flight_elements = await page.query_selector_all(".pIav2d")
        print(f"Found {len(flight_elements)} flights on the page")
        
        # Scrape each flight
        for i, flight_element in enumerate(flight_elements):
            try:
                flight_info = await scrape_flight_info(flight_element)
                flight_data.append(flight_info)
                print(f"  Flight {i+1}: {flight_info['Airline Company']} - {flight_info['Price']}")
            except Exception as e:
                print(f"  Error scraping flight {i+1}: {e}")
                
        return flight_data
        
    except Exception as e:
        print(f"Error scraping flights: {e}")
        return flight_data

async def scrape_simple_flights(departure: str, destination: str, departure_date: str, return_date: str, passengers: int = 2) -> List[Dict[str, str]]:
    """
    Simple flight scraper that gets all visible flights without opening modals.
    """
    
    flight_data = []
    playwright, browser, page = await setup_browser()
    
    try:
        # Step 1: Fill the form using dynamic approach
        success = await dynamic_form_fill(page, departure, destination, departure_date, return_date, passengers)
        
        if success:
            # Step 2: Scrape all visible flights on the page
            flight_data = await scrape_all_visible_flights(page)
        else:
            print("❌ Could not load flight results, skipping scraping")
        
        return flight_data

    finally:
        print("Keeping browser open for 10 seconds for inspection...")
        await page.wait_for_timeout(10000)
        await browser.close()
        await playwright.stop()

# ----------------------------
# 6. DATA SAVING FUNCTIONS
# ----------------------------

def save_structured_data(data: FinalFlightData, filename: str) -> None:
    """Save the nested flight data structure as a JSON file."""
    if data:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Nested round-trip data saved to {filename}")
    else:
        print("No data was scraped to save.")

def save_flight_data(data: List[Dict[str, str]], filename: str) -> None:
    """Save the flight data as a JSON file."""
    if data:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Flight data saved to {filename}")
    else:
        print("No data was scraped to save.")

# ----------------------------
# 7. MAIN EXECUTION
# ----------------------------

if __name__ == "__main__":
    print("Starting Complete Dynamic Flight Scraper...")
    
    # Configure your flight search parameters here
    DEPARTURE = "NYC"           
    DESTINATION = "CUN"         
    DEPARTURE_DATE = "12/07/2025"
    RETURN_DATE = "12/12/2025"
    PASSENGERS = 2
    
    # Choose scraping mode
    USE_ROUND_TRIP_SCRAPING = True  # Set to False for simple visible flights only
    
    print(f"Searching flights: {DEPARTURE} to {DESTINATION}")
    print(f"Departure: {DEPARTURE_DATE}, Return: {RETURN_DATE}")
    print(f"Passengers: {PASSENGERS}")
    print(f"Mode: {'Round-trip (detailed)' if USE_ROUND_TRIP_SCRAPING else 'Simple (visible only)'}")
    
    # Run the flight scraper
    try:
        if USE_ROUND_TRIP_SCRAPING:
            # Use the round-trip scraping logic from GitHub
            scraped_data = asyncio.run(scrape_complete_round_trip_flights(
                departure=DEPARTURE,
                destination=DESTINATION, 
                departure_date=DEPARTURE_DATE,
                return_date=RETURN_DATE,
                passengers=PASSENGERS
            ))
            
            # Save the structured results
            if scraped_data:
                output_filename = f"roundtrip_{DEPARTURE}_{DESTINATION}_{DEPARTURE_DATE.replace('/', '')}.json"
                save_structured_data(scraped_data, output_filename)
                print(f"Round-trip scraping completed! Found {len(scraped_data)} complete trip options.")
                
                # Print summary
                for i, trip in enumerate(scraped_data[:3]):  # Show first 3
                    outbound = trip['OutboundFlight']
                    return_count = len(trip['ReturnFlights'])
                    print(f"  Trip {i+1}: {outbound['Airline Company']} {outbound['Price']} outbound, {return_count} return options")
                
                if len(scraped_data) > 3:
                    print(f"  ... and {len(scraped_data) - 3} more trip options")
            else:
                print("No round-trip data was scraped.")
        
        else:
            # Use simple visible flights scraping
            scraped_data = asyncio.run(scrape_simple_flights(
                departure=DEPARTURE,
                destination=DESTINATION, 
                departure_date=DEPARTURE_DATE,
                return_date=RETURN_DATE,
                passengers=PASSENGERS
            ))
            
            # Save the results
            if scraped_data:
                output_filename = f"flights_{DEPARTURE}_{DESTINATION}_{DEPARTURE_DATE.replace('/', '')}.json"
                save_flight_data(scraped_data, output_filename)
                print(f"Simple scraping completed! Found {len(scraped_data)} flights.")
                
                # Print summary
                for i, flight in enumerate(scraped_data[:5]):  # Show first 5
                    print(f"  Flight {i+1}: {flight['Airline Company']} {flight['Price']} ({flight['Flight Duration']})")
                
                if len(scraped_data) > 5:
                    print(f"  ... and {len(scraped_data) - 5} more flights")
            else:
                print("No flight data was scraped.")
            
    except Exception as e:
        print(f"Scraping failed with error: {e}")
        import traceback
        traceback.print_exc()