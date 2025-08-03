from sqlalchemy import Column, Integer, String, Date, DateTime, DECIMAL, Boolean, ForeignKey, BigInteger
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'User'

    ID = Column(Integer, primary_key=True)
    Name = Column(NVARCHAR(100))
    hash_pass = Column(NVARCHAR(255))
    email = Column(NVARCHAR(100))
    phone = Column(NVARCHAR(20))
    username = Column(NVARCHAR(50), unique=True)
    birthday = Column(Date)
    country = Column(NVARCHAR(50))
    sex = Column(Boolean)

    # Relationships
    giao_diches = relationship("GiaoDich", back_populates="user")
    quy_nguoi_dungs = relationship("QuyNguoiDung", back_populates="user")
    dat_lenhs = relationship("DatLenh", back_populates="user")
    danh_mucs = relationship("DanhMucDauTu", back_populates="user")
    thong_baos = relationship("ThongBao", back_populates="user")


class Stock(Base):
    __tablename__ = 'Stock'

    ID = Column(Integer, primary_key=True)
    ma_co_phieu = Column(NVARCHAR(20))
    ten_cong_ty = Column(NVARCHAR(100))
    gia_tri_thi_truong = Column(DECIMAL(18, 2))
    nganh = Column(NVARCHAR(100))
    linh_vuc = Column(NVARCHAR(100))
    loai_co_phieu = Column(NVARCHAR(50))

    # Relationships
    thanh_phan_chi_so = relationship("ThanhPhanChiSo", back_populates="stock")
    danh_mucs = relationship("DanhMucDauTu", back_populates="stock")
    dat_lenhs = relationship("DatLenh", back_populates="stock")
    chung_quyen = relationship("ChungQuyenCoDamBao", back_populates="stock")
    du_lieu_thoi_gian_thuc = relationship("DuLieuThoiGianThuc", back_populates="stock", uselist=False)


class GiaoDich(Base):
    __tablename__ = 'Giao_dich'

    ID = Column(Integer, primary_key=True)
    id_lien_ket_tai_khoan = Column(Integer)
    userID = Column(Integer, ForeignKey('User.ID'))
    loai_giao_dich = Column(NVARCHAR(50))
    so_tien_giao_dich = Column(DECIMAL(18, 2))
    ngay_giao_dich = Column(Date)

    user = relationship("User", back_populates="giao_diches")


class QuyNguoiDung(Base):
    __tablename__ = 'Quy_nguoi_dung'

    ID = Column(Integer, primary_key=True)
    id_lien_ket_tai_khoan = Column(Integer)
    userID = Column(Integer, ForeignKey('User.ID'))
    loai_giao_dich = Column(NVARCHAR(50))
    so_tien_giao_dich = Column(DECIMAL(18, 2))
    ngay_giao_dich = Column(Date)

    user = relationship("User", back_populates="quy_nguoi_dungs")


class ChiSoThiTruong(Base):
    __tablename__ = 'Chi_so_thi_truong'

    ID = Column(Integer, primary_key=True)
    ky_hieu_chi_so = Column(NVARCHAR(20))
    ten_chi_so = Column(NVARCHAR(100))

    thanh_phan_chi_so = relationship("ThanhPhanChiSo", back_populates="chi_so")


class ThanhPhanChiSo(Base):
    __tablename__ = 'Thanh_phan_chi_so'

    ID_chi_so_thi_truong = Column(Integer, ForeignKey('Chi_so_thi_truong.ID'), primary_key=True)
    ID_stock = Column(Integer, ForeignKey('Stock.ID'), primary_key=True)

    chi_so = relationship("ChiSoThiTruong", back_populates="thanh_phan_chi_so")
    stock = relationship("Stock", back_populates="thanh_phan_chi_so")


class DanhMucDauTu(Base):
    __tablename__ = 'Danh_muc_dau_tu'

    ID = Column(Integer, primary_key=True)
    ID_user = Column(Integer, ForeignKey('User.ID'))
    ID_stock = Column(Integer, ForeignKey('Stock.ID'))
    so_luong_co_phieu_nam = Column(Integer)
    gia_mua_trung_binh = Column(DECIMAL(18, 2))

    user = relationship("User", back_populates="danh_mucs")
    stock = relationship("Stock", back_populates="danh_mucs")


class DatLenh(Base):
    __tablename__ = 'Dat_lenh'

    ID = Column(Integer, primary_key=True)
    ID_user = Column(Integer, ForeignKey('User.ID'))
    ID_stock = Column(Integer, ForeignKey('Stock.ID'))
    loai_lenh = Column(NVARCHAR(50))
    thoi_diem_dat = Column(DateTime)
    gia_lenh = Column(DECIMAL(18, 2))
    trang_thai = Column(NVARCHAR(50))
    so_luong_co_phieu = Column(Integer)
    trading = Column(NVARCHAR(50))

    user = relationship("User", back_populates="dat_lenhs")
    stock = relationship("Stock", back_populates="dat_lenhs")


class ChungQuyenCoDamBao(Base):
    __tablename__ = 'Chung_quyen_co_dam_bao'

    ID = Column(Integer, primary_key=True)
    ten_chung_quyen = Column(NVARCHAR(100))
    underlyingAssetID = Column(Integer, ForeignKey('Stock.ID'))
    ngay_het_han = Column(Date)
    ngay_phat_hanh = Column(Date)
    type = Column(NVARCHAR(50))

    stock = relationship("Stock", back_populates="chung_quyen")


class DuLieuThoiGianThuc(Base):
    __tablename__ = 'Du_lieu_thoi_gian_thuc'

    stockID = Column(Integer, ForeignKey('Stock.ID'), primary_key=True)
    current_price = Column(DECIMAL(18, 2))
    bien_dong_gia = Column(DECIMAL(5, 2))
    ty_le_bien_dong_gia = Column(DECIMAL(5, 2))
    gia_mo = Column(DECIMAL(18, 2))
    gia_dong = Column(DECIMAL(18, 2))
    gia_thap_nhat_trong_ngay = Column(DECIMAL(18, 2))
    gia_cao_nhat_trong_ngay = Column(DECIMAL(18, 2))
    khoi_luong_giao_dich = Column(BigInteger)
    thoi_gian_cap_nhat_du_lieu = Column(DateTime)

    stock = relationship("Stock", back_populates="du_lieu_thoi_gian_thuc")


class ThongBao(Base):
    __tablename__ = 'Thong_bao'

    ID = Column(Integer, primary_key=True)
    ID_user = Column(Integer, ForeignKey('User.ID'))
    loai_thong_bao = Column(NVARCHAR(100))
    noi_dung = Column(NVARCHAR)  # NVARCHAR(MAX)
    trang_thai = Column(NVARCHAR(20))
    thoi_gian = Column(DateTime)

    user = relationship("User", back_populates="thong_baos")
