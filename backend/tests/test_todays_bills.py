"""
Tests for the Today's Bills automation feature (page parsing + calculator math).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.services.pages.anubandh_datewise_page import AnubandhDateWisePage as P  # noqa: E402


SAMPLE_ROW = {
    "AuctionId": "EM-20260731-00042",
    "AuctionDate": "31-07-2026",
    "CommGroupCode": "G01",
    "CommodityCode": "C01",
    "VarietyCode": "V01",
    "FarmerName": "राम प्रसाद साहू",
    "FarmerId": "1234",
    "MobileNo_Farmer": "9876543210",
    "VillageName": "Rewa",
    "CommGroup_Name": "दलहन",
    "Commodity_Name": "चना",
    "Variety_Name": "देसी",
    "ActualWeight": "43.000",
    "AuctionRate": "4230",
    "GatepassID": "GP-8877",
    "Gatepass_Date": "31-07-2026",
    "Grade": "A",
    "category": "1",
    "MandiName": "रिवा मंडी",
    "TraderID": "1000001",
    "Traders_ComName": "TEST TRADERS",
    "Tulavati_Id": "TL-55",
    "OperatorID": "OP1",
    "EmpName": "कर्मचारी",
}


def test_parse_row_fields():
    bills = P.parse_rows([SAMPLE_ROW])
    assert len(bills) == 1
    b = bills[0]
    assert b["auction_id"] == "EM-20260731-00042"
    assert b["farmer_name"] == "राम प्रसाद साहू"
    assert b["commodity"] == "चना"
    assert b["weight"] == 43.0
    assert b["rate"] == 4230.0
    assert b["gatepass_id"] == "GP-8877"


def test_parse_handles_commas_in_numbers():
    row = dict(SAMPLE_ROW, ActualWeight="1,200.000", AuctionRate="4,500.00")
    b = P.parse_rows([row])[0]
    assert b["weight"] == 1200.0
    assert b["rate"] == 4500.0


def test_manditax_math_defaults():
    bills = P.parse_rows([SAMPLE_ROW])
    b = P.annotate(bills[0], hammali_rate=12.05, toul_rate=5.0)
    assert b["gross_amount"] == 181890.0
    assert b["hammali_amount"] == 518.15
    assert b["toul_amount"] == 215.0
    assert b["payable"] == 181156.85


def test_manditax_zero_toul():
    bills = P.parse_rows([SAMPLE_ROW])
    b = P.annotate(bills[0], hammali_rate=12.05, toul_rate=0)
    assert b["payable"] == 181371.85


def test_gross_amount_rounding():
    row = dict(SAMPLE_ROW, ActualWeight="33.5", AuctionRate="4310")
    b = P.annotate(P.parse_rows([row])[0], hammali_rate=12.05)
    assert b["gross_amount"] == 144385.0
