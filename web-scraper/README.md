# Google Flight Price Scraper ✈️

This repository contains a Python-based scraper designed to track and extract flight prices from Google Flights. By leveraging the power of Playwright and proxy rotation, the scraper automates the process of fetching flight details such as prices, departure times, and more, saving the data into a CSV file for easy analysis.

## 📖 Tutorial Reference

This project is based on the tutorial published on Rayobyte's community blog and video tutorial:

- [**Step-by-Step Guide: Create a Flight Price Tracker**](https://rayobyte.com/community/scraping-project/create-a-flight-price-tracker-scraping-airlines-ticket-prices-from-google-flights-using-python/)
- [**YouTube Video Tutorial**](https://youtu.be/8LZXeI7_OxE)

Refer to the tutorial for a detailed explanation of how the scraper works, setup instructions, and customization tips.

## 🚀 Features

- **Automated Flight Price Tracking**: Scrapes flight details (e.g., price, time) from Google Flights based on user-defined search criteria.
- **Dynamic Proxy Rotation**: Integrates proxy services for seamless and anonymous scraping.
- **Data Storage**: Saves flight details to a CSV file for easy tracking and analysis.

## 🛠️ Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/ainacodes/google_flight_scraper.git
   cd google_flight_scraper
   ```
2. Install the required dependencies:
3. [Optional] Configure proxy rotation: Update the proxy settings in the script if needed in `.env` file.

## 📝 Usage

1. Modify the [airport codes](https://en.wikipedia.org/wiki/List_of_airports_by_IATA_airport_code:_A) for `departure` and `destination` and also `departure_date`.

   ```
   if __name__ == "__main__":
   one_way_url = FlightURLBuilder.build_url(
       departure="SFO",
       destination="LAX",
       departure_date="2024-12-25"
   )
   print("One-way URL:", one_way_url)

   # Run the scraper
   asyncio.run(scrape_flight_data(one_way_url))
   ```

2. Run the scraper
   ```
   python flight_scraper.py
   ```

## 🧑‍💻 Contributions

Contributions are welcome! Feel free to fork this repository and submit pull requests for improvements or new features.

## 📧 Contact

For inquiries or suggestions, you can reach me on noraina.nordin16@gmail.com or open a [new issue](https://github.com/ainacodes/google_flight_scraper/issues/new)
