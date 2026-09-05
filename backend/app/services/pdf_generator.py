"""
PDF Generator Service — uses fpdf2 to produce downloadable feasibility report PDFs.
"""

import io
import logging
from datetime import datetime
from typing import Any

from fpdf2 import FPDF, XPos, YPos

from app.schemas.analysis import AnalysisResponse

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _inr(value: float) -> str:
    """Format as Indian Rupee string."""
    return f"Rs. {value:,.0f}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


# ─── PDF Document ─────────────────────────────────────────────────────────────

class UdyamReport(FPDF):
    """Custom FPDF subclass with branded header/footer."""

    BRAND_COLOR = (39, 86, 52)   # Deep moss green
    ACCENT_COLOR = (180, 120, 40)  # Ochre
    DANGER_COLOR = (160, 50, 40)   # Clay red
    TEXT_COLOR = (30, 30, 30)

    def header(self) -> None:
        self.set_fill_color(*self.BRAND_COLOR)
        self.rect(0, 0, 210, 18, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
        self.set_xy(10, 4)
        self.cell(0, 10, "UdyamAI  |  Local Business Feasibility Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*self.TEXT_COLOR)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 10,
            f"UdyamAI  |  Page {self.page_no()}  |  Indicative report — verify before applying",
            align="C",
        )

    def section_title(self, title: str) -> None:
        self.set_fill_color(*self.BRAND_COLOR)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 8, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_text_color(*self.TEXT_COLOR)
        self.ln(2)

    def key_value(self, label: str, value: str, width_label: int = 70) -> None:
        self.set_font("Helvetica", "B", 9)
        self.cell(width_label, 7, label + ":", new_x=XPos.RIGHT)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 7, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def small_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 8)
        self.set_text_color(90, 90, 90)
        self.multi_cell(0, 5, text)
        self.set_text_color(*self.TEXT_COLOR)
        self.ln(1)


# ─── Generator ────────────────────────────────────────────────────────────────

class PDFGenerator:
    """Generates a structured PDF feasibility report from AnalysisResponse."""

    def generate(self, report: AnalysisResponse) -> bytes:
        """Return PDF as bytes."""
        pdf = UdyamReport(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(12, 22, 12)
        pdf.add_page()

        # ── Cover / Summary ──────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"{report.business_category_display} Business Plan", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"{report.village_name}, {report.district_name}, {report.state_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}  |  Report ID: {report.report_id[:12]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        # Viability Score Banner
        pdf.set_fill_color(235, 245, 235)
        pdf.rect(12, pdf.get_y(), 186, 20, "F")
        pdf.set_xy(14, pdf.get_y() + 3)
        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(*UdyamReport.BRAND_COLOR)
        pdf.cell(40, 14, str(report.viability_score), new_x=XPos.RIGHT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*UdyamReport.TEXT_COLOR)
        pdf.cell(0, 14, f"/ 100  Business Viability Score     {report.recommendation.label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(6)

        # ── Section 1: Financial Summary ──────────────────────────────────────
        pdf.section_title("MODULE 2  |  FINANCIAL STRUCTURE")
        pdf.key_value("Available Capital (Your Contribution)", _inr(report.margin_capital))
        pdf.key_value("Total Project Cost", _inr(report.project_cost))
        pdf.key_value("Eligible Loan Amount", _inr(report.loan_amount))
        pdf.key_value("Selected Scheme", report.scheme_name or "N/A")
        pdf.key_value("Interest Rate", _pct(report.interest_rate or 0) + " per annum")
        pdf.key_value("Tenure", f"{report.tenure_years} years")
        pdf.key_value("Moratorium Period", f"{report.moratorium_months} months")
        pdf.key_value("Monthly EMI (after moratorium)", _inr(report.monthly_emi or 0))
        pdf.key_value("Total Repayment", _inr(report.total_repayment or 0))
        pdf.ln(4)

        # ── Section 2: Market Reach ───────────────────────────────────────────
        pdf.section_title("MODULE 1  |  MARKET REACH")
        pdf.key_value("Population within 5 km", f"{report.market.population_5km:,}")
        pdf.key_value("Population within 10 km", f"{report.market.population_10km:,}")
        pdf.key_value("Potential Customer Segment", f"{report.market.potential_segment:,}")
        pdf.key_value("Estimated Early Customers", f"{report.market.estimated_customers:,}")
        pdf.key_value("Distribution Channels", ", ".join(report.market.distribution_channels[:4]))
        pdf.ln(4)

        # ── Section 3: SWOT ───────────────────────────────────────────────────
        pdf.section_title("SWOT ANALYSIS")
        for quad in report.swot:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, quad.title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            for item in quad.items:
                pdf.cell(6, 5, "-")
                pdf.cell(0, 5, item, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

        # ── Section 4: Risk Radar ─────────────────────────────────────────────
        pdf.section_title("RISK RADAR")
        for risk in report.risks:
            color = {
                "Low": UdyamReport.BRAND_COLOR,
                "Medium": UdyamReport.ACCENT_COLOR,
                "High": UdyamReport.DANGER_COLOR,
            }.get(risk.level, UdyamReport.TEXT_COLOR)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*color)
            pdf.cell(60, 6, f"{risk.name}  [{risk.level}]", new_x=XPos.RIGHT)
            pdf.set_text_color(*UdyamReport.TEXT_COLOR)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(0, 6, risk.detail[:80], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

        # ── Section 5: Pricing Intelligence ──────────────────────────────────
        pdf.section_title("PRICING INTELLIGENCE")
        pdf.key_value("Recommended Price", f"{_inr(report.pricing.base)} {report.pricing.unit}")
        pdf.key_value("Low Scenario", _inr(report.pricing.low))
        pdf.key_value("Premium Scenario", _inr(report.pricing.premium))
        pdf.key_value("Estimated Gross Margin", _pct(report.pricing.margin_pct))
        pdf.small_text(report.pricing.rationale)
        pdf.ln(3)

        # ── Section 6: Recommendation & Checklist ─────────────────────────────
        pdf.section_title("RECOMMENDATION  &  ACTION CHECKLIST")
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, report.recommendation.title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.small_text(report.recommendation.detail)
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, "Before You Apply — Checklist:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        for i, item in enumerate(report.recommendation.checklist, 1):
            pdf.cell(6, 6, f"{i}.")
            pdf.cell(0, 6, item, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # ── Disclaimer ────────────────────────────────────────────────────────
        pdf.ln(6)
        pdf.set_fill_color(245, 245, 245)
        pdf.rect(12, pdf.get_y(), 186, 14, "F")
        pdf.set_xy(14, pdf.get_y() + 2)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(182, 4, (
            "DISCLAIMER: This report is generated by AI for informational purposes only. "
            "Scheme eligibility, loan approval, market conditions and repayment obligations "
            "are subject to verification by the relevant authority or financial institution. "
            "No loan is guaranteed. Data sources: Census 2011, SECC 2011, HCES 2023-24, LGD, PMGSY."
        ))

        output = io.BytesIO()
        pdf_bytes = pdf.output()
        return pdf_bytes if isinstance(pdf_bytes, bytes) else bytes(pdf_bytes)
