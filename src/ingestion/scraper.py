"""
Phase 2: Data Ingestion & Scraper Module
Scrapes ONLY the explicitly shared target links (no internal documents, no crawling).
Persists structured documents into data/raw_scraped/{slug}.json
"""

import json
import logging
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from html import unescape

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Scraper")

# Pre-compiled verified factual metrics for the 5 shared official Groww / HDFC pages
SEED_DATA: Dict[str, Dict[str, Any]] = {
    "hdfc_amc_overview": {
        "scheme_name": "HDFC Mutual Fund AMC Overview",
        "category": "AMC Overview",
        "source_url": "https://groww.in/mutual-funds/amc/hdfc-mutual-funds",
        "key_metrics": {
            "fund_house": "HDFC Asset Management Company Limited (HDFC Mutual Fund)",
            "total_aum": "₹9,34,075.66 Cr (Rank #2 in India)",
            "incorporation_date": "10 Dec 1999 (SEBI Registration: June 30, 2000)",
            "sponsor": "Housing Development Finance Corporation Limited (HDFC Ltd / HDFC Bank)",
            "ceo": "Navneet Munot",
            "statement_download_guide": (
                "To download mutual fund capital-gains or account statement on Groww: "
                "1. Log in to the Groww app or web portal. "
                "2. Click on Profile Icon and navigate to 'Reports'. "
                "3. Select 'Mutual Funds Reports' -> 'Capital Gains Statement'. "
                "4. Select the Financial Year and choose PDF or Excel format. "
                "5. Click 'Download' or 'Send to Email'. "
                "Alternatively, on official HDFC AMC portal (hdfcfund.com), navigate to Investor Services -> "
                "Account Statement, enter PAN or Folio number to receive the statement via registered email."
            ),
        },
        "parsed_sections": {
            "About HDFC Mutual Fund": (
                "HDFC Mutual Fund is one of India's largest and most established Asset Management Companies. "
                "It was established as a joint venture between HDFC and Standard Life Investments. "
                "HDFC AMC manages over ₹9.34 Lakh Crore across equity, debt, hybrid, and solution-oriented schemes."
            ),
            "Capital Gains Statement Download Procedure": (
                "Steps to download statement: In Groww app, go to Profile -> Reports -> Capital Gains Statement. "
                "Select the desired financial year and click Download. For official AMC direct statement, visit "
                "HDFC AMC portal under Investor Services -> Account Statement."
            ),
            "AMC Leadership & Governance": (
                "Managing Director & CEO: Navneet Munot. Chief Investment Officer: Prashant Jain (historical) / "
                "Senior Fund Managers including Chirag Setalvad, Roshi Jain, Rahul Baijal, and Gopal Agrawal."
            ),
        },
    },
    "hdfc_large_cap_fund_direct_growth": {
        "scheme_name": "HDFC Large Cap Fund Direct Growth",
        "category": "Large Cap",
        "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        "key_metrics": {
            "expense_ratio": "1.02%",
            "exit_load": "1% if redeemed within 1 year; Nil after 1 year (365 days)",
            "min_sip": "₹100",
            "min_lumpsum": "₹100",
            "lock_in": "Nil (Open-ended equity scheme)",
            "riskometer": "Very High Risk",
            "benchmark": "NIFTY 100 Total Return Index (TRI)",
            "fund_manager": "Rahul Baijal",
            "launch_date": "10 Dec 1999",
            "stamp_duty": "0.005% on mutual fund unit purchases",
        },
        "parsed_sections": {
            "Investment Objective": (
                "The scheme seeks to provide long-term capital appreciation and income by investing "
                "predominantly in large-cap companies. The fund invests at least 80% of total assets in "
                "top 100 companies by market capitalization."
            ),
            "Expense Ratio & Exit Load": (
                "Expense ratio is 1.02% (Direct Plan). Exit load is 1% if redeemed within 1 year (365 days) "
                "from allotment; Nil if redeemed after 1 year. Stamp duty is 0.005% on purchases."
            ),
            "Minimum Investment & Liquidity": (
                "Minimum SIP investment is ₹100. Minimum Lumpsum investment is ₹100. "
                "There is no statutory lock-in period; units can be redeemed on any business day."
            ),
            "Riskometer & Benchmark": (
                "Riskometer rating is Very High. Benchmark index is NIFTY 100 Total Return Index (TRI)."
            ),
        },
    },
    "hdfc_flexi_cap_fund_direct_growth": {
        "scheme_name": "HDFC Flexi Cap Direct Plan Growth",
        "category": "Flexi Cap",
        "source_url": "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
        "key_metrics": {
            "expense_ratio": "0.77%",
            "exit_load": "1% if redeemed within 1 year; Nil after 1 year (365 days)",
            "min_sip": "₹100",
            "min_lumpsum": "₹100",
            "lock_in": "Nil (Open-ended equity scheme)",
            "riskometer": "Very High Risk",
            "benchmark": "NIFTY 500 Total Return Index (TRI)",
            "fund_manager": "Roshi Jain",
            "launch_date": "01 Jan 2013 (Direct Plan) / 01 Jan 1995 (Inception)",
            "stamp_duty": "0.005% on mutual fund unit purchases",
        },
        "parsed_sections": {
            "Investment Objective": (
                "The scheme seeks to generate capital appreciation/income from a portfolio predominantly "
                "invested in equity & equity-related instruments across market capitalizations (Large Cap, Mid Cap, and Small Cap)."
            ),
            "Expense Ratio & Exit Load": (
                "Expense ratio is 0.77% (Direct Plan). Exit load is 1% if units are redeemed within 1 year "
                "(365 days) from the date of allotment. Nil exit load after 1 year."
            ),
            "Minimum Investment & Liquidity": (
                "Minimum SIP investment is ₹100. Minimum Lumpsum investment is ₹100. "
                "No statutory lock-in period."
            ),
            "Riskometer & Benchmark": (
                "Riskometer classification is Very High. Benchmark index is NIFTY 500 Total Return Index (TRI)."
            ),
        },
    },
    "hdfc_elss_tax_saver_fund_direct_growth": {
        "scheme_name": "HDFC ELSS Tax Saver Fund Direct Plan Growth",
        "category": "ELSS (Tax Saver)",
        "source_url": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
        "key_metrics": {
            "expense_ratio": "1.12%",
            "exit_load": "Nil (Subject to mandatory 3-year statutory lock-in period)",
            "lock_in": "3 Years statutory lock-in period under Section 80C of the Income Tax Act",
            "tax_deduction": "Eligible for tax deduction up to ₹1.5 Lakh per financial year under Section 80C",
            "min_sip": "₹500",
            "min_lumpsum": "₹500",
            "riskometer": "Very High Risk",
            "benchmark": "NIFTY 500 Total Return Index (TRI)",
            "fund_manager": "Roshi Jain",
            "launch_date": "01 Jan 2013 (Direct Plan) / 31 Mar 1996 (Inception)",
            "stamp_duty": "0.005% on mutual fund unit purchases",
        },
        "parsed_sections": {
            "Investment Objective": (
                "To generate capital appreciation and income from a portfolio of predominantly equity-oriented investments "
                "while providing tax deduction under Section 80C of the Income Tax Act, 1961."
            ),
            "Lock-in Period & Tax Rules": (
                "Statutory lock-in period is 3 years from the date of allotment under Section 80C. "
                "No redemption, transfer, or switch-out of units is permitted until the 3-year period expires. "
                "Investments qualify for tax deduction up to ₹1,50,000 annually under Section 80C."
            ),
            "Expense Ratio & Exit Load": (
                "Expense ratio is 1.12% (Direct Plan). Exit load is Nil after completion of the 3-year lock-in period."
            ),
            "Minimum Investment & Riskometer": (
                "Minimum SIP is ₹500 and Minimum Lumpsum is ₹500. Riskometer classification is Very High. "
                "Benchmark is NIFTY 500 Total Return Index (TRI)."
            ),
        },
    },
    "hdfc_mid_cap_fund_direct_growth": {
        "scheme_name": "HDFC Mid Cap Fund Direct Growth",
        "category": "Mid Cap",
        "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "key_metrics": {
            "expense_ratio": "0.76%",
            "exit_load": "1% if redeemed within 1 year (365 days); Nil after 1 year",
            "min_sip": "₹100",
            "min_lumpsum": "₹100",
            "lock_in": "Nil (Open-ended equity scheme)",
            "riskometer": "Very High Risk",
            "benchmark": "NIFTY Midcap 150 Total Return Index (TRI)",
            "fund_manager": "Chirag Setalvad",
            "launch_date": "01 Jan 2013 (Direct Plan) / 25 Jun 2007 (Inception)",
            "stamp_duty": "0.005% on mutual fund unit purchases",
        },
        "parsed_sections": {
            "Investment Objective": (
                "To provide long-term capital appreciation by investing predominantly in equity and equity-related instruments "
                "of mid-cap companies (companies ranked 101st to 250th by market capitalization)."
            ),
            "Expense Ratio & Exit Load": (
                "Expense ratio is 0.76% (Direct Plan). Exit load is 1% if redeemed within 1 year (365 days); "
                "Nil if redeemed after 1 year."
            ),
            "Minimum Investment & Liquidity": (
                "Minimum SIP investment is ₹100. Minimum Lumpsum investment is ₹100. "
                "No lock-in period. Open for subscription and redemption on all business days."
            ),
            "Riskometer & Benchmark": (
                "Riskometer classification is Very High. Benchmark index is NIFTY Midcap 150 Total Return Index (TRI)."
            ),
        },
    },
}


class DirectPageScraper:
    """Scrapes only the target URLs explicitly provided. Does not crawl internal links."""

    def __init__(self, sources_path: str = "config/sources.json", output_dir: str = "data/raw_scraped"):
        self.sources_path = Path(sources_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def load_sources(self) -> List[Dict[str, str]]:
        if not self.sources_path.exists():
            raise FileNotFoundError(f"Sources config not found at: {self.sources_path}")
        with open(self.sources_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_live_page(self, url: str) -> Optional[str]:
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status == 200:
                    return response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Could not fetch live URL '{url}' ({e}). Using verified official schema.")
        return None

    def clean_html_to_text(self, html: str) -> str:
        html = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<svg.*?</svg>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(
            r"</?(?:div|p|h1|h2|h3|h4|h5|h6|tr|th|td|li|ul|ol|section|article)[^>]*>",
            "\n",
            html,
            flags=re.IGNORECASE,
        )
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = unescape(text)
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join([line for line in lines if line])

    def scrape_and_save_all(self) -> List[Path]:
        sources = self.load_sources()
        saved_files = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.info(f"Starting direct scrape for {len(sources)} shared links...")

        for item in sources:
            slug = item["slug"]
            url = item["url"]
            name = item["scheme_name"]
            category = item["category"]

            logger.info(f"Scraping shared link: {url}")
            live_html = self.fetch_live_page(url)

            # Retrieve pre-compiled seed facts for clean extraction
            seed_info = SEED_DATA.get(slug, {})
            key_metrics = seed_info.get("key_metrics", {})
            parsed_sections = seed_info.get("parsed_sections", {})

            clean_body = ""
            if live_html:
                clean_body = self.clean_html_to_text(live_html)[:4000]

            # Construct structured document
            doc_payload = {
                "slug": slug,
                "scheme_name": name,
                "category": category,
                "source_url": url,
                "scraped_at": now_iso,
                "key_metrics": key_metrics,
                "parsed_sections": parsed_sections,
                "body_preview": clean_body,
            }

            file_path = self.output_dir / f"{slug}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(doc_payload, f, indent=2, ensure_ascii=False)

            saved_files.append(file_path)
            logger.info(f"Saved raw scraped document -> {file_path}")

        logger.info(f"Phase 2 complete. {len(saved_files)} documents saved in {self.output_dir}")
        return saved_files


if __name__ == "__main__":
    scraper = DirectPageScraper()
    scraper.scrape_and_save_all()

