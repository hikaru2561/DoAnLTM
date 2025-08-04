auth_type = 'Bearer'
consumerID = 'eac167fd0eea458dbe9bf955142c01e6'
consumerSecret = '7e10ffd69fb34db685450ae54b4fd14f'

url = 'https://fc-data.ssi.com.vn/'
stream_url = 'https://fc-datahub.ssi.com.vn/'


import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "mssql+pyodbc://LAPTOP-P38G42DU\\SQLEXPRESS/StockDB?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FINNHUB_API_KEY = "d25pal9r01qhge4dnq40d25pal9r01qhge4dnq4g"