import vesper

@vesper.tool(description="Get the current stock price for a ticker symbol")
def get_stock_price(ticker: str) -> str:
    prices = {"AAPL": 187.42, "TSLA": 241.05, "MSFT": 419.13}
    price = prices.get(ticker.upper())
    if price is None:
        return f"No price found for {ticker}."
    return f"{ticker.upper()} is trading at ${price}"
