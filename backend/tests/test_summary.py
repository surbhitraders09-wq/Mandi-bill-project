"""
Tests for the Summary feature: fee/stock HTML parsing + aggregation helpers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.services.pages.summary_scraper import (  # noqa: E402
    EMPTY_FEES,
    FEE_LABELS,
    SummaryScraper,
)
from app.services.pages.anubandh_datewise_page import (  # noqa: E402
    AnubandhDateWisePage,
)
from app.services.pages.cropwise_summary_page import (  # noqa: E402
    CropWiseSummaryPage,
)
from app.services.pages.trader_transaction_page import (  # noqa: E402
    TraderTransactionPage,
)
from app.services.summary_aggregator import (  # noqa: E402
    _cumulative_to_daily,
    base_crop,
    build_crop_trends,
    build_price_trend,
    group_crops,
    group_daily,
    is_soyabean,
    soyabean_row,
)


# --------------------------------------------------------------------------
# ASMX `d` payload decoding (double-encoded JSON string)
# --------------------------------------------------------------------------

def test_decode_response_payload_array():
    rows = [{"AuctionId": "1", "FarmerName": "राम"}]
    assert AnubandhDateWisePage.decode_response_payload({"d": rows}) == rows


def test_decode_response_payload_double_encoded_string():
    import json

    rows = [{"AuctionId": "1", "FarmerName": "राम"}]
    body = {"d": json.dumps(rows)}
    assert AnubandhDateWisePage.decode_response_payload(body) == rows


def test_decode_response_payload_empty_string():
    import json

    assert AnubandhDateWisePage.decode_response_payload({"d": json.dumps([])}) == []


def test_decode_response_payload_missing_d_returns_none():
    assert AnubandhDateWisePage.decode_response_payload({}) is None
    assert AnubandhDateWisePage.decode_response_payload(None) is None


def test_decode_response_payload_invalid_string_returns_none():
    assert AnubandhDateWisePage.decode_response_payload({"d": "not-json{["}) is None


# --------------------------------------------------------------------------
# Dashboard fee parsing (pure static method)
# --------------------------------------------------------------------------

def test_parse_money_parses_commas():
    assert SummaryScraper._parse_money("1,51,29,928.00") == 15129928.00
    assert SummaryScraper._parse_money("24,82,984.00") == 2482984.00
    assert SummaryScraper._parse_money("₹ 17,04,758.00") == 1704758.00


def test_parse_money_missing_returns_zero():
    assert SummaryScraper._parse_money("") == 0.0
    assert SummaryScraper._parse_money("लोड हो रहा है") == 0.0


def test_empty_fees_keys_match_labels():
    assert set(EMPTY_FEES) == set(FEE_LABELS)
    assert all(v == 0.0 for v in EMPTY_FEES.values())


def test_fee_labels_cover_required_fields():
    for key in ("total_mandi", "total_nirashrit", "cash_mandi", "cash_nirashrit", "rtgs_mandi", "rtgs_nirashrit"):
        assert key in FEE_LABELS


def test_fee_ids_cover_required_fields():
    from app.services.pages.summary_scraper import FEE_IDS

    assert set(FEE_IDS) == set(FEE_LABELS)
    assert FEE_IDS["total_mandi"] == "TotalMandiFees"
    assert FEE_IDS["total_nirashrit"] == "TotalN_MandiFees"
    assert FEE_IDS["cash_mandi"] == "DepositFee"
    assert FEE_IDS["cash_nirashrit"] == "N_DepositFee"
    assert FEE_IDS["rtgs_mandi"] == "TotalPaymentByOnline"
    assert FEE_IDS["rtgs_nirashrit"] == "TotalN_PaymentByOnline"


# --------------------------------------------------------------------------
# Tax-paid stock parsing helpers
# --------------------------------------------------------------------------

def test_is_soyabean_matches_hindi_and_english():
    assert is_soyabean("सोयाबीन")
    assert is_soyabean("Soyabean")
    assert is_soyabean("soybean")
    assert not is_soyabean("चना")
    assert not is_soyabean("")


# --------------------------------------------------------------------------
# Aggregation helpers
# --------------------------------------------------------------------------

def _bill(commodity, weight, rate, auction_date="31-07-2026"):
    return {
        "commodity": commodity,
        "weight": weight,
        "rate": rate,
        "gross_amount": round(weight * rate, 2),
        "auction_date": auction_date,
    }


SAMPLE_BILLS = [
    _bill("सोयाबीन", 100, 680, "30-07-2026"),
    _bill("सोयाबीन", 50, 700, "31-07-2026"),
    _bill("चना", 43, 4230, "31-07-2026"),
]


def test_group_crops_weight_amount_avg():
    crops = group_crops(SAMPLE_BILLS)
    by = {c["commodity"]: c for c in crops}
    assert by["सोयाबीन"]["total_weight"] == 150.0
    assert by["सोयाबीन"]["total_amount"] == round(100 * 680 + 50 * 700, 2)
    expected_avg = round(by["सोयाबीन"]["total_amount"] / 150.0, 2)
    assert by["सोयाबीन"]["avg_rate"] == expected_avg
    assert by["चना"]["total_weight"] == 43.0
    assert by["चना"]["avg_rate"] == 4230.0


def test_group_crops_zero_weight_avg_zero():
    crops = group_crops([{"commodity": "खाली", "weight": 0, "rate": 100, "gross_amount": 0}])
    assert crops[0]["avg_rate"] == 0.0
    assert crops[0]["total_weight"] == 0.0


def test_group_crops_empty():
    assert group_crops([]) == []


def test_group_crops_uses_gross_amount_when_present():
    b = {"commodity": "सोयाबीन", "weight": 10, "rate": 700, "gross_amount": 9000.0}
    crops = group_crops([b])
    assert crops[0]["total_amount"] == 9000.0


def test_group_daily():
    daily = group_daily(SAMPLE_BILLS)
    by = {d["date"]: d for d in daily}
    assert by["30-07-2026"]["total_weight"] == 100.0
    assert by["30-07-2026"]["bill_count"] == 1
    assert by["31-07-2026"]["total_weight"] == 93.0
    assert by["31-07-2026"]["bill_count"] == 2


def test_group_daily_empty():
    assert group_daily([]) == []


def test_soyabean_row_found():
    crops = group_crops(SAMPLE_BILLS)
    row = soyabean_row(crops)
    assert row is not None
    assert row["commodity"] == "सोयाबीन"


def test_soyabean_row_missing():
    crops = group_crops([_bill("चना", 43, 4230)])
    assert soyabean_row(crops) is None


# --------------------------------------------------------------------------
# Price-trend aggregation (per-day avg rate from daily-fasal page runs)
# --------------------------------------------------------------------------

def _daily_run(date_str, crops):
    return {"date": date_str, "crops": crops}


def _crop(commodity, weight, amount):
    return {
        "commodity": commodity,
        "total_weight": weight,
        "total_amount": amount,
        "avg_rate": round(amount / weight, 2) if weight > 0 else 0.0,
    }


def test_build_price_trend_two_days():
    runs = [
        _daily_run("20-07-2026", [_crop("सोयाबीन/Yellow", 100, 700_000.0)]),
        _daily_run("21-07-2026", [_crop("सोयाबीन/Yellow", 120, 840_000.0)]),
    ]
    trend = build_price_trend(runs)
    assert len(trend) == 2
    assert trend[0]["date"] == "20-07-2026"
    assert trend[0]["rates"]["सोयाबीन"] == 7_000.0
    assert trend[1]["date"] == "21-07-2026"
    assert trend[1]["rates"]["सोयाबीन"] == 7_000.0


def test_build_price_trend_mixed_crops_per_day():
    runs = [
        _daily_run("18-07-2026", [_crop("सोयाबीन", 100, 700_000.0)]),
        _daily_run("19-07-2026", [_crop("चना", 50, 300_000.0)]),
        _daily_run("20-07-2026", [_crop("चना", 40, 240_000.0)]),
    ]
    trend = build_price_trend(runs)
    assert len(trend) == 3
    assert trend[0]["rates"] == {"सोयाबीन": 7_000.0}
    assert trend[1]["rates"] == {"चना": 6_000.0}
    assert trend[2]["rates"] == {"चना": 6_000.0}


def test_build_price_trend_skips_zero_rate_day():
    runs = [
        _daily_run("20-07-2026", [_crop("सोयाबीन", 50, 350_000.0)]),
        _daily_run("21-07-2026", []),  # no purchases that day → gap
    ]
    trend = build_price_trend(runs)
    assert len(trend) == 1
    assert trend[0]["date"] == "20-07-2026"


def test_build_price_trend_empty():
    assert build_price_trend([]) == []
    assert build_price_trend([{"date": "20-07-2026", "crops": []}]) == []


def test_build_crop_trends_up_down_flat():
    points = [
        {"date": "20-07-2026", "rates": {"सोयाबीन": 7_000.0, "चना": 6_000.0}},
        {"date": "21-07-2026", "rates": {"सोयाबीन": 7_100.0, "चना": 5_900.0}},
        {"date": "22-07-2026", "rates": {"सोयाबीन": 7_210.0, "चना": 6_010.0}},
    ]
    trends = {t["commodity"]: t for t in build_crop_trends(points)}
    assert trends["सोयाबीन"]["direction"] == "up"
    assert round(trends["सोयाबीन"]["change_pct"], 2) == 3.0
    assert trends["चना"]["direction"] == "flat"  # 6010/6000 ≈ +0.17%
    assert trends["चना"]["change_pct"] < 0.5


def test_build_crop_trends_down():
    points = [
        {"date": "20-07-2026", "rates": {"सोयाबीन": 7_000.0}},
        {"date": "22-07-2026", "rates": {"सोयाबीन": 6_500.0}},
    ]
    trends = build_crop_trends(points)
    assert trends[0]["direction"] == "down"
    assert round(trends[0]["change_pct"], 2) == -7.14


def test_build_crop_trends_empty():
    assert build_crop_trends([]) == []


def test_base_crop_normalizes_names():
    assert base_crop("सोयाबीन/Yellow") == "सोयाबीन"
    assert base_crop("चना/चना") == "चना"
    assert base_crop("सोयाबीन") == "सोयाबीन"
    assert base_crop("ग्रुप - फसल") == "फसल"
    assert base_crop("  सोयाबीन  ") == "सोयाबीन"
    assert base_crop("") == ""


def test_build_price_trend_normalizes_variety_names():
    runs = [
        _daily_run("20-07-2026", [_crop("सोयाबीन/Yellow", 100, 700_000.0)]),
        _daily_run("21-07-2026", [_crop("सोयाबीन/Yellow", 60, 420_000.0)]),
    ]
    trend = build_price_trend(runs)
    assert "सोयाबीन" in trend[0]["rates"]
    assert trend[0]["rates"]["सोयाबीन"] == 7_000.0


# --------------------------------------------------------------------------
# Cumulative-to-daily conversion
# --------------------------------------------------------------------------

def test_cumulative_to_daily_basic():
    """Two cumulative runs → per-day via difference."""
    runs = [
        _daily_run("25-07-2026", [_crop("सोयाबीन", 200, 1_400_000.0)]),
        _daily_run("26-07-2026", [_crop("सोयाबीन", 120, 840_000.0)]),
    ]
    daily = _cumulative_to_daily(runs)
    assert len(daily) == 2
    # Day 1 = 200-120 = 80 quintal
    assert daily[0]["crops"][0]["total_weight"] == 80.0
    assert daily[0]["crops"][0]["total_amount"] == 560_000.0
    # Day 2 (oldest remaining) = 120 quintal (its own cumulative)
    assert daily[1]["crops"][0]["total_weight"] == 120.0


def test_cumulative_to_daily_three_days():
    runs = [
        _daily_run("24-07-2026", [_crop("सोयाबीन", 300, 2_100_000.0)]),
        _daily_run("25-07-2026", [_crop("सोयाबीन", 200, 1_400_000.0)]),
        _daily_run("26-07-2026", [_crop("सोयाबीन", 120, 840_000.0)]),
    ]
    daily = _cumulative_to_daily(runs)
    assert len(daily) == 3
    assert daily[0]["crops"][0]["total_weight"] == 100.0  # 300-200
    assert daily[1]["crops"][0]["total_weight"] == 80.0   # 200-120
    assert daily[2]["crops"][0]["total_weight"] == 120.0  # last = its own


def test_cumulative_to_daily_empty():
    assert _cumulative_to_daily([]) == []


def test_cumulative_to_daily_single():
    runs = [_daily_run("26-07-2026", [_crop("चना", 50, 300_000.0)])]
    daily = _cumulative_to_daily(runs)
    assert len(daily) == 1
    assert daily[0]["crops"][0]["total_weight"] == 50.0


# --------------------------------------------------------------------------
# Crop-wise summary report (RPT_BhugtanPatrak_CropwiseTD.aspx)
# --------------------------------------------------------------------------

def test_cropwise_decode_response_payload():
    rows = [{"Commodity_Name": "सोयाबीन/Yellow", "ActWeight": "97.0200", "TotalAmt": "689285.5000"}]
    assert CropWiseSummaryPage.decode_response_payload({"d": rows}) == rows


def test_cropwise_decode_response_payload_string():
    import json

    rows = [{"Commodity_Name": "सोयाबीन/Yellow", "ActWeight": "97.0200", "TotalAmt": "689285.5000"}]
    assert CropWiseSummaryPage.decode_response_payload({"d": json.dumps(rows)}) == rows


def test_cropwise_parse_rows_real_shape():
    rows = [
        {"Commodity_Name": "सोयाबीन/Yellow", "ActWeight": "97.0200", "TotalAmt": "689285.5000"},
        {"Commodity_Name": "चना/चना", "ActWeight": "31.5200", "TotalAmt": "190920.8000"},
    ]
    crops = CropWiseSummaryPage.parse_rows(rows)
    assert len(crops) == 2
    soy, chana = crops
    assert soy["commodity"] == "सोयाबीन/Yellow"
    assert soy["total_weight"] == 97.02
    assert soy["total_amount"] == 689285.50
    assert round(soy["avg_rate"], 2) == round(689285.50 / 97.02, 2)
    assert chana["commodity"] == "चना/चना"
    assert chana["total_weight"] == 31.52
    assert chana["total_amount"] == 190920.80


def test_cropwise_parse_rows_empty_and_missing():
    assert CropWiseSummaryPage.parse_rows([]) == []
    crops = CropWiseSummaryPage.parse_rows([{"Commodity_Name": "सरसों", "TotalAmt": "100.00"}])
    assert crops[0]["total_weight"] == 0.0
    assert crops[0]["avg_rate"] == 0.0


def test_cropwise_soyabean_flagging():
    rows = [
        {"Commodity_Name": "सोयाबीन/Yellow", "ActWeight": "97.0200", "TotalAmt": "689285.5000"},
        {"Commodity_Name": "चना/चना", "ActWeight": "31.5200", "TotalAmt": "190920.8000"},
    ]
    crops = CropWiseSummaryPage.parse_rows(rows)
    assert is_soyabean(crops[0]["commodity"])
    assert not is_soyabean(crops[1]["commodity"])


# --------------------------------------------------------------------------
# Home dashboard mandi-fee summary (#exampleMFNP)
# --------------------------------------------------------------------------

def test_parse_money_handles_mfnp_values():
    assert SummaryScraper._parse_money("29606.81") == 29606.81
    assert SummaryScraper._parse_money("3,947.57") == 3947.57


def test_to_float_variants():
    assert SummaryScraper._to_float("320.27") == 320.27
    assert SummaryScraper._to_float("1,207.02") == 1207.02
    assert SummaryScraper._to_float("62") == 62.0
    assert SummaryScraper._to_float(None) == 0.0
    assert SummaryScraper._to_float("") == 0.0


# --------------------------------------------------------------------------
# TraderTransactionRpt.aspx (mandi-fee account) parsing
# --------------------------------------------------------------------------

def test_parse_money_balance():
    assert TraderTransactionPage._parse_money("27548.99") == 27548.99
    assert TraderTransactionPage._parse_money("") == 0.0


def test_extract_xml_from_json_wrapper():
    xml = '<NewDataSet><BooksData><TRANS_DATE>30-Jul-2026</TRANS_DATE></BooksData></NewDataSet>'
    wrapped = '{"d":"' + xml.replace('"', '&quot;') + '"}'
    out = TraderTransactionPage._extract_xml(wrapped)
    assert out is not None
    assert "BooksData" in out


def test_extract_xml_direct():
    xml = '<NewDataSet><BooksData></BooksData></NewDataSet>'
    assert TraderTransactionPage._extract_xml(xml) == xml
    assert TraderTransactionPage._extract_xml("") is None


def test_parse_transactions_xml_real_shape():
    xml = (
        '<NewDataSet>'
        '<BooksData><TRANS_DATE>30-Jul-2026</TRANS_DATE><FeeTransactionID>1</FeeTransactionID>'
        '<ETransactionID>26280023007590812213</ETransactionID>'
        '<Variety_Name>सोयाबीन  -  सोयाबीन</Variety_Name>'
        '<MandiFee_Dr>271.87</MandiFee_Dr><MandiFee_Cr>0.00</MandiFee_Cr>'
        '<FLAG>भुगतान-पत्र</FLAG></BooksData>'
        '<BooksData><TRANS_DATE>30-Jul-2026</TRANS_DATE><FeeTransactionID>2</FeeTransactionID>'
        '<ETransactionID>26280023007003643749</ETransactionID>'
        '<Variety_Name>सोयाबीन  -  सोयाबीन</Variety_Name>'
        '<MandiFee_Dr>413.80</MandiFee_Dr><MandiFee_Cr>0.00</MandiFee_Cr>'
        '<FLAG>भुगतान-पत्र</FLAG></BooksData>'
        '</NewDataSet>'
    )
    txns = TraderTransactionPage.parse_transactions_xml(xml)
    assert len(txns) == 2
    first = txns[0]
    assert first["date"] == "30-Jul-2026"
    assert first["reference"] == "26280023007590812213"
    assert first["crop"] == "सोयाबीन  -  सोयाबीन"
    assert first["mandi_fee_dr"] == 271.87
    assert first["mandi_fee_cr"] == 0.0
    assert first["flag"] == "भुगतान-पत्र"
    assert txns[1]["mandi_fee_dr"] == 413.80


def test_parse_transactions_xml_namespaced():
    xml = (
        '<NewDataSet xmlns="http://tempuri.org/">'
        '<BooksData><TRANS_DATE>30-Jul-2026</TRANS_DATE><MandiFee_Dr>742.74</MandiFee_Dr>'
        '<MandiFee_Cr>0.00</MandiFee_Cr></BooksData>'
        '</NewDataSet>'
    )
    txns = TraderTransactionPage.parse_transactions_xml(xml)
    assert len(txns) == 1
    assert txns[0]["mandi_fee_dr"] == 742.74


def test_parse_transactions_xml_empty_invalid():
    assert TraderTransactionPage.parse_transactions_xml(None) == []
    assert TraderTransactionPage.parse_transactions_xml("") == []
    assert TraderTransactionPage.parse_transactions_xml("not xml") == []
