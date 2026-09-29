"""
Print service — handles printing bills.

On Windows uses win32print if available; otherwise falls back to
generating an HTML document in a print-output directory.
"""

import os
import platform
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.exceptions import PrintError


PRINT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "print_output",
)
os.makedirs(PRINT_OUTPUT_DIR, exist_ok=True)


def _detect_platform() -> str:
    return platform.system()


def _build_pdf_content(bill_data: Dict[str, Any]) -> str:
    """Portal-style भुगतान-पत्रक (Hindi) matching the e-Anugya print layout.

    Columns mirror `bill_print.html`: कुल मूल्य, कुल हम्माली, कुल तौल,
    किसान को भुगतान योग्य राशि, नीलामी दर, वास्तविक वजन.
    """
    farmer = bill_data.get("farmer_name") or bill_data.get("trader_name", "—")
    gross = float(bill_data.get("gross_amount") or 0)
    hammali = float(bill_data.get("hammali_amount") or 0)
    toul = float(bill_data.get("toul_amount") or 0)
    payable = float(bill_data.get("payable") or bill_data.get("total_amount") or 0)
    weight = bill_data.get("weight", "—")
    rate = bill_data.get("rate", "—")
    auction_date = bill_data.get("auction_date") or bill_data.get("date", "—")
    hammali_rate = bill_data.get("hammali_rate", 12.05)
    toul_rate = bill_data.get("toul_rate", 0)
    commodity = bill_data.get("commodity", "—")
    variety = bill_data.get("variety", "—")

    return f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<title>भुगतान-पत्रक</title>
<style>
  @page {{ size: A5 landscape; margin: 8mm; }}
  body {{ font-family: 'Noto Sans Devanagari', 'Mangal', Arial, sans-serif; margin: 0; color: #000; }}
  .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 6px; margin-bottom: 10px; }}
  .header h1 {{ font-size: 16px; margin: 2px 0; }}
  .header .sub {{ font-size: 11px; }}
  .firm {{ text-align: center; font-size: 12px; font-weight: bold; margin-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  th, td {{ border: 1px solid #000; padding: 4px 6px; text-align: left; }}
  th {{ background: #eee; }}
  .num {{ text-align: right; }}
  .totals td {{ font-weight: bold; }}
  .grand td {{ background: #ddd; font-weight: bold; font-size: 12px; }}
  .footer {{ margin-top: 12px; font-size: 10px; }}
  .sig {{ display: flex; justify-content: space-between; margin-top: 26px; font-size: 11px; }}
</style>
</head>
<body>
  <div class="header">
    <h1>भुगतान-पत्रक</h1>
    <div class="sub">(eMandi पोर्टल के अनुबंध पत्रक अनुसार)</div>
  </div>
  <div class="firm">व्यापारी: {bill_data.get("firm", "") or bill_data.get("trader_name", "")} &nbsp;|&nbsp; मंडी: {bill_data.get("mandi", "—")}</div>
  <table>
    <tr><th style="width:35%">विक्रेता / कृषक का नाम</th><td>{farmer}</td></tr>
    <tr><th>ग्राम</th><td>{bill_data.get("village", "—")}</td></tr>
    <tr><th>कृषि उपज</th><td>{commodity} — {variety}</td></tr>
    <tr><th>नीलामी दिनाँक</th><td>{auction_date}</td></tr>
    <tr><th>गेटपास आई.डी.</th><td>{bill_data.get("gatepass_id", "—")} &nbsp;&nbsp; तुलावटी: {bill_data.get("tulavati_id", "—")}</td></tr>
    <tr>
      <th>नीलामी दर (रु./क्विं.)</th><td class="num">{rate}</td>
      <th>वास्तविक वजन (क्विं.)</th><td class="num">{weight}</td>
    </tr>
  </table>
  <table class="totals">
    <tr>
      <th>कुल मूल्य</th><td class="num">₹ {gross:,.2f}</td>
      <th>कुल हम्माली ({hammali_rate:g}/क्विं.)</th><td class="num">₹ {hammali:,.2f}</td>
    </tr>
    <tr>
      <th>कुल तौल ({toul_rate:g}/क्विं.)</th><td class="num">₹ {toul:,.2f}</td>
      <th>अतिरिक्त भुगतान</th><td class="num">₹ 0.00</td>
    </tr>
    <tr class="grand">
      <td colspan="3">किसान को भुगतान योग्य राशि</td>
      <td class="num">₹ {payable:,.2f}</td>
    </tr>
  </table>
  <div class="footer">यह भुगतान-पत्रक {datetime.now().strftime("%d-%m-%Y %H:%M")} को मंडी ऑटोमेशन के द्वारा निर्गत किया गया।</div>
  <div class="sig"><div>व्यापारी के हस्ताक्षर</div><div>कृषक के हस्ताक्षर</div></div>
</body>
</html>"""


async def print_document(bill_data: Dict[str, Any]) -> bool:
    html = _build_pdf_content(bill_data)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bill_{bill_data.get('bill_number', 'unknown')}_{timestamp}"

    system = _detect_platform()

    if system == "Windows":
        try:
            import win32api
            import win32print
        except ImportError:
            return await _save_as_pdf(html, filename)

        try:
            temp_path = os.path.join(tempfile.gettempdir(), f"{filename}.html")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(html)
            printer_name = win32print.GetDefaultPrinter()
            win32api.ShellExecute(0, "print", temp_path, f'/d:"{printer_name}"', ".", 0)
            return True
        except Exception as exc:
            raise PrintError(f"Windows printing failed: {exc}") from exc

    elif system == "Linux":
        try:
            temp_path = os.path.join(tempfile.gettempdir(), f"{filename}.html")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(html)
            result = subprocess.run(
                ["lp", temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True
            return await _save_as_pdf(html, filename)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return await _save_as_pdf(html, filename)

    else:
        return await _save_as_pdf(html, filename)


async def _save_as_pdf(html: str, filename: str) -> bool:
    try:
        pdf_path = os.path.join(PRINT_OUTPUT_DIR, f"{filename}.html")
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write(html)
        return True
    except OSError as exc:
        raise PrintError(f"Failed to save PDF: {exc}") from exc


async def get_printer_status() -> Dict[str, Any]:
    system = _detect_platform()

    if system == "Windows":
        try:
            import win32print
            printer_name = win32print.GetDefaultPrinter()
            handle = win32print.OpenPrinter(printer_name)
            status = win32print.GetPrinter(handle, 2)
            win32print.ClosePrinter(handle)
            return {
                "name": printer_name,
                "status": status["Status"],
                "online": status["Status"] == 0,
            }
        except ImportError:
            return {"name": "unknown", "status": "win32print not available", "online": False}
        except Exception as exc:
            return {"name": "unknown", "status": str(exc), "online": False}

    elif system == "Linux":
        try:
            result = subprocess.run(["lpstat", "-p", "-d"], capture_output=True, text=True, timeout=10)
            return {"name": result.stdout.strip(), "status": "available", "online": True}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"name": "unknown", "status": "lpstat not available", "online": False}

    return {"name": "unknown", "status": "unsupported platform", "online": False}


async def list_printers() -> List[str]:
    system = _detect_platform()

    if system == "Windows":
        try:
            import win32print
            return [p[2] for p in win32print.EnumPrinters(2)]
        except ImportError:
            return []

    elif system == "Linux":
        try:
            result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split("\n")
            printers = []
            for line in lines:
                if line.startswith("printer "):
                    parts = line.split()
                    if len(parts) > 1:
                        printers.append(parts[1])
            return printers
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

    return []
