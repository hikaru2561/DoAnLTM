import json

def map_quote_data(raw_message):
    data = json.loads(raw_message["Content"]) if isinstance(raw_message["Content"], str) else raw_message["Content"]

    return {
        "symbol": data["Symbol"],
        "buy": [
            {"price": data["BidPrice3"], "vol": data["BidVol3"]},
            {"price": data["BidPrice2"], "vol": data["BidVol2"]},
            {"price": data["BidPrice1"], "vol": data["BidVol1"]},
        ],
        "sell": [
            {"price": data["AskPrice1"], "vol": data["AskVol1"]},
            {"price": data["AskPrice2"], "vol": data["AskVol2"]},
            {"price": data["AskPrice3"], "vol": data["AskVol3"]},
        ],
    }

def map_trade_data(raw_message):
    data = json.loads(raw_message["Content"]) if isinstance(raw_message["Content"], str) else raw_message["Content"]

    return {
        "symbol": data["Symbol"],
        "last_price": data["LastPrice"],
        "last_vol": data["LastVol"],
        "change": data["Change"],
        "ratio_change": data["RatioChange"],
        "ceiling": data["Ceiling"],
        "floor": data["Floor"],
        "ref_price": data["RefPrice"],
    }
