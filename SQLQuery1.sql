-- Tạo Database
CREATE DATABASE StockDB;
GO

USE StockDB;
GO

-- Bảng người dùng
CREATE TABLE [User] (
    ID INT IDENTITY PRIMARY KEY,
    Name NVARCHAR(100),
    hash_pass NVARCHAR(255),
    email NVARCHAR(100),
    phone NVARCHAR(20),
    username NVARCHAR(50),
    birthday DATE,
    country NVARCHAR(50),
    sex BIT
);

-- Bảng cổ phiếu
CREATE TABLE Stock (
    ID VARCHAR(20) PRIMARY KEY,
    ma_co_phieu NVARCHAR(20),
    ten_cong_ty NVARCHAR(100),
    gia_tri_thi_truong DECIMAL(18,2),
    nganh NVARCHAR(100),
    linh_vuc NVARCHAR(100),
    loai_co_phieu NVARCHAR(50)
);

-- Giao dịch
CREATE TABLE Giao_dich (
    ID INT IDENTITY PRIMARY KEY,
    id_lien_ket_tai_khoan INT,
    userID INT FOREIGN KEY REFERENCES [User](ID),
    loai_giao_dich NVARCHAR(50),
    so_tien_giao_dich DECIMAL(18,2),
    ngay_giao_dich DATE
);

CREATE TABLE MarketData (
    Symbol VARCHAR(20) PRIMARY KEY,

    BidPrice1 FLOAT,
    BidVol1 FLOAT,
    BidPrice2 FLOAT,
    BidVol2 FLOAT,
    BidPrice3 FLOAT,
    BidVol3 FLOAT,

    AskPrice1 FLOAT,
    AskVol1 FLOAT,
    AskPrice2 FLOAT,
    AskVol2 FLOAT,
    AskPrice3 FLOAT,
    AskVol3 FLOAT,

    LastPrice FLOAT,
    LastVol FLOAT,

    Change FLOAT,
    RatioChange FLOAT,

    Ceiling FLOAT,
    Floor FLOAT,
    RefPrice FLOAT,

	High Float,
	Low float,
	TotalVol float

);


-- Quỹ người dùng
CREATE TABLE Quy_nguoi_dung (
    ID INT IDENTITY PRIMARY KEY,
    userID INT FOREIGN KEY REFERENCES [User](ID),
    so_tien DECIMAL(18,2),
);

CREATE TABLE Lich_su_khop_lenh (
    ID INT IDENTITY PRIMARY KEY,
    ID_user INT FOREIGN KEY REFERENCES [User](ID),
    ID_stock VARCHAR(20) FOREIGN KEY REFERENCES MarketData(Symbol),
    loai_lenh NVARCHAR(50),
    gia_khop FLOAT,
    so_luong INT,
    thoi_gian DATETIME
);



-- Chỉ số thị trường
CREATE TABLE Chi_so_thi_truong (
    ID INT IDENTITY PRIMARY KEY,
    ky_hieu_chi_so NVARCHAR(20),
    ten_chi_so NVARCHAR(100)
);

-- Thành phần chỉ số
CREATE TABLE Thanh_phan_chi_so (
    ID_chi_so_thi_truong INT FOREIGN KEY REFERENCES Chi_so_thi_truong(ID),
    ID_stock VARCHAR(20) FOREIGN KEY REFERENCES MarketData(Symbol),
    PRIMARY KEY (ID_chi_so_thi_truong, ID_stock)
);

-- Danh mục đầu tư
CREATE TABLE Danh_muc_dau_tu (
    ID INT IDENTITY PRIMARY KEY,
    ID_user INT FOREIGN KEY REFERENCES [User](ID),
    ID_stock VARCHAR(20) FOREIGN KEY REFERENCES MarketData(Symbol),
    so_luong_co_phieu_nam INT,
    gia_mua_trung_binh FLOAT
);

-- Đặt lệnh
CREATE TABLE Dat_lenh (
    ID INT IDENTITY PRIMARY KEY,
    ID_user INT FOREIGN KEY REFERENCES [User](ID),
    ID_stock VARCHAR(20) FOREIGN KEY REFERENCES MarketData(Symbol),
    loai_lenh NVARCHAR(50),
    thoi_diem_dat DATETIME,
    gia_lenh FLOAT,
    trang_thai NVARCHAR(50),
    so_luong_co_phieu INT,
    trading NVARCHAR(50)
);

-- Chứng quyền có đảm bảo
CREATE TABLE Chung_quyen_co_dam_bao (
    ID INT IDENTITY PRIMARY KEY,
    ten_chung_quyen NVARCHAR(100),
    underlyingAssetID VARCHAR(20) FOREIGN KEY REFERENCES MarketData(Symbol),
    ngay_het_han DATE,
    ngay_phat_hanh DATE,
    type NVARCHAR(50)
);

-- Dữ liệu thời gian thực
CREATE TABLE Du_lieu_thoi_gian_thuc (
    stockID VARCHAR(20) PRIMARY KEY FOREIGN KEY REFERENCES MarketData(Symbol),
    current_price DECIMAL(18,2),
    bien_dong_gia DECIMAL(5,2),
    ty_le_bien_dong_gia DECIMAL(5,2),
    gia_mo DECIMAL(18,2),
    gia_dong DECIMAL(18,2),
    gia_thap_nhat_trong_ngay DECIMAL(18,2),
    gia_cao_nhat_trong_ngay DECIMAL(18,2),
    khoi_luong_giao_dich BIGINT,
    thoi_gian_cap_nhat_du_lieu DATETIME
);



-- Thông báo
CREATE TABLE Thong_bao (
    ID INT IDENTITY PRIMARY KEY,
    ID_user INT FOREIGN KEY REFERENCES [User](ID),
    loai_thong_bao NVARCHAR(100),
    noi_dung NVARCHAR(MAX),
    trang_thai NVARCHAR(20),
    thoi_gian DATETIME
);

