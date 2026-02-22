"""
ADIVA - PDF Extractor (Digital PDFs)

Extracts text and structured data from digital (text-based) PDF files.
Supports multiple table extraction backends for better accuracy.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import pdfplumber
from extractors.base_extractor import BaseExtractor
from logger import logger, log_extraction, log_error
import time

try:
    import camelot

    HAS_CAMELOT = True
    logger.info("Camelot available for table extraction")
except ImportError:
    HAS_CAMELOT = False
    logger.info("Camelot not installed. Table extraction limited to pdfplumber.")

try:
    import tabula

    HAS_TABULA = True
    logger.info("Tabula available for table extraction")
except ImportError:
    HAS_TABULA = False
    logger.info("Tabula not installed.")


class PDFExtractor(BaseExtractor):
    """
    Extracts content from digital PDF files using multiple backends:
    - pdfplumber: Primary for digital PDFs (fast, accurate)
    - camelot: Fallback for scanned/complex PDFs
    - tabula: Additional fallback for tables
    """

    def __init__(self):
        """Initialize PDF extractor"""
        super().__init__()
        self.supported_extensions = {".pdf"}
        self.has_camelot = HAS_CAMELOT
        self.has_tabula = HAS_TABULA

    def can_extract(self, file_path: Path) -> bool:
        """Check if this can extract from the file"""
        return file_path.suffix.lower() in self.supported_extensions

    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from PDF

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text
        """
        start_time = time.time()

        try:
            full_text = []

            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text from page
                    text = page.extract_text()

                    if text:
                        # Add page marker
                        full_text.append(f"\n--- Page {page_num} ---\n")
                        full_text.append(text)
                    else:
                        logger.warning(
                            f"No text found on page {page_num} of {file_path.name}"
                        )

            result = "\n".join(full_text)

            # Log extraction
            extraction_time = time.time() - start_time
            log_extraction(file_path.name, len(result), extraction_time)

            return result

        except Exception as e:
            log_error("PDFExtraction", str(e), f"File: {file_path}")
            raise

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from PDF

        Args:
            file_path: Path to PDF file

        Returns:
            Metadata dictionary
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata = {
                    "num_pages": len(pdf.pages),
                    "pdf_metadata": pdf.metadata or {},
                    "table_backends": {
                        "pdfplumber": True,
                        "camelot": self.has_camelot,
                        "tabula": self.has_tabula,
                    },
                }

                # Add first page dimensions
                if pdf.pages:
                    first_page = pdf.pages[0]
                    metadata["page_width"] = first_page.width
                    metadata["page_height"] = first_page.height

                return metadata

        except Exception as e:
            log_error("PDFMetadataExtraction", str(e), f"File: {file_path}")
            return {}

    def _normalize_table(
        self,
        table: List[List],
        page_num: int,
        table_num: int,
        source: str = "pdfplumber",
    ) -> Dict[str, Any]:
        """Normalize table data to common format."""
        if not table or len(table) < 1:
            return None

        headers = [str(h) if h is not None else "" for h in table[0]]
        rows = []

        for row in table[1:]:
            normalized_row = [str(c) if c is not None else "" for c in row]
            rows.append(normalized_row)

        data = []
        for row in rows:
            if len(row) == len(headers):
                row_dict = {headers[i]: row[i] for i in range(len(headers))}
                data.append(row_dict)

        return {
            "page": page_num,
            "table_num": table_num,
            "headers": headers,
            "rows": rows,
            "data": data,
            "source": source,
            "row_count": len(rows),
            "col_count": len(headers),
        }

    def _validate_table(self, table_data: Dict[str, Any]) -> bool:
        """
        Validate table structure.
        Returns True if table is valid and useful.
        """
        if not table_data:
            return False

        min_rows = 1
        min_cols = 2

        if table_data["row_count"] < min_rows:
            return False

        if table_data["col_count"] < min_cols:
            return False

        empty_headers = sum(1 for h in table_data["headers"] if not h.strip())
        if empty_headers > len(table_data["headers"]) * 0.5:
            return False

        total_cells = table_data["row_count"] * table_data["col_count"]
        empty_cells = sum(
            1 for row in table_data["rows"] for cell in row if not cell.strip()
        )
        if total_cells > 0 and empty_cells / total_cells > 0.8:
            return False

        return True

    def _extract_tables_pdfplumber(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract tables using pdfplumber (primary method)."""
        tables = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    extracted = page.extract_tables()

                    for table_num, table in enumerate(extracted, 1):
                        table_data = self._normalize_table(
                            table, page_num, table_num, "pdfplumber"
                        )
                        if table_data and self._validate_table(table_data):
                            tables.append(table_data)
                            logger.info(
                                f"pdfplumber: Found table {table_num} on page {page_num} ({table_data['row_count']} rows)"
                            )
        except Exception as e:
            logger.warning(f"pdfplumber table extraction failed: {e}")

        return tables

    def _extract_tables_camelot(
        self, file_path: Path, pages: str = "all"
    ) -> List[Dict[str, Any]]:
        """Extract tables using camelot (fallback for scanned PDFs)."""
        if not self.has_camelot:
            return []

        tables = []

        try:
            try:
                camelot_tables = camelot.read_pdf(
                    str(file_path), pages=pages, flavor="lattice"
                )
                if len(camelot_tables) > 0:
                    for idx, table in enumerate(camelot_tables):
                        df = table.df
                        if len(df) > 0:
                            table_data = {
                                "page": table.page,
                                "table_num": idx + 1,
                                "headers": [str(h) for h in df.columns.tolist()],
                                "rows": [
                                    [str(c) for c in row] for row in df.values.tolist()
                                ],
                                "data": [],
                                "source": "camelot_lattice",
                                "row_count": len(df),
                                "col_count": len(df.columns),
                                "accuracy": table.accuracy,
                            }

                            for row in df.values.tolist():
                                row_dict = {
                                    df.columns[i]: str(row[i]) for i in range(len(row))
                                }
                                table_data["data"].append(row_dict)

                            if self._validate_table(table_data):
                                tables.append(table_data)
                                logger.info(
                                    f"camelot (lattice): Found table {idx + 1} on page {table.page} (accuracy: {table.accuracy:.1f}%)"
                                )
            except Exception as e:
                logger.debug(f"camelot lattice failed: {e}")

            if len(tables) == 0:
                try:
                    camelot_tables = camelot.read_pdf(
                        str(file_path), pages=pages, flavor="stream"
                    )
                    for idx, table in enumerate(camelot_tables):
                        df = table.df
                        if len(df) > 0:
                            table_data = {
                                "page": table.page,
                                "table_num": idx + 1,
                                "headers": [str(h) for h in df.columns.tolist()],
                                "rows": [
                                    [str(c) for c in row] for row in df.values.tolist()
                                ],
                                "data": [],
                                "source": "camelot_stream",
                                "row_count": len(df),
                                "col_count": len(df.columns),
                            }

                            for row in df.values.tolist():
                                row_dict = {
                                    df.columns[i]: str(row[i]) for i in range(len(row))
                                }
                                table_data["data"].append(row_dict)

                            if self._validate_table(table_data):
                                tables.append(table_data)
                                logger.info(
                                    f"camelot (stream): Found table {idx + 1} on page {table.page}"
                                )
                except Exception as e:
                    logger.debug(f"camelot stream failed: {e}")

        except Exception as e:
            logger.warning(f"camelot table extraction failed: {e}")

        return tables

    def _extract_tables_tabula(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract tables using tabula (additional fallback)."""
        if not self.has_tabula:
            return []

        tables = []

        try:
            dfs = tabula.read_pdf(str(file_path), pages="all", multiple_tables=True)

            for idx, df in enumerate(dfs):
                if len(df) > 0:
                    table_data = {
                        "page": 1,
                        "table_num": idx + 1,
                        "headers": [str(h) for h in df.columns.tolist()],
                        "rows": [[str(c) for c in row] for row in df.values.tolist()],
                        "data": [],
                        "source": "tabula",
                        "row_count": len(df),
                        "col_count": len(df.columns),
                    }

                    for row in df.values.tolist():
                        row_dict = {df.columns[i]: str(row[i]) for i in range(len(row))}
                        table_data["data"].append(row_dict)

                    if self._validate_table(table_data):
                        tables.append(table_data)
                        logger.info(
                            f"tabula: Found table {idx + 1} ({table_data['row_count']} rows)"
                        )

        except Exception as e:
            logger.warning(f"tabula table extraction failed: {e}")

        return tables

    def _deduplicate_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate tables from different sources."""
        if len(tables) <= 1:
            return tables

        unique_tables = []
        seen_signatures = set()

        for table in tables:
            signature = (
                table["row_count"],
                table["col_count"],
                tuple(table["headers"][:3]) if table["headers"] else (),
            )

            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_tables.append(table)
            else:
                logger.debug(f"Skipping duplicate table: {table['source']}")

        return unique_tables

    def extract_tables(self, file_path: Path) -> list:
        """
        Extract tables from PDF using multiple backends.

        Strategy:
        1. Try pdfplumber (fastest, best for digital PDFs)
        2. If no tables found or low quality, try camelot (good for scanned)
        3. If still no tables, try tabula (additional fallback)
        4. Deduplicate and validate results

        Args:
            file_path: Path to PDF file

        Returns:
            List of tables (each table is a list of rows)
        """
        all_tables = []

        tables_pdfplumber = self._extract_tables_pdfplumber(file_path)
        all_tables.extend(tables_pdfplumber)

        if len(tables_pdfplumber) == 0 and (self.has_camelot or self.has_tabula):
            logger.info("No tables found with pdfplumber, trying fallback methods...")

            if self.has_camelot:
                tables_camelot = self._extract_tables_camelot(file_path)
                all_tables.extend(tables_camelot)

            if len(all_tables) == 0 and self.has_tabula:
                tables_tabula = self._extract_tables_tabula(file_path)
                all_tables.extend(tables_tabula)

        all_tables = self._deduplicate_tables(all_tables)

        for i, table in enumerate(all_tables, 1):
            table["table_num"] = i

        logger.info(f"Total tables extracted: {len(all_tables)}")
        return all_tables

    def get_page_count(self, file_path: Path) -> int:
        """Get number of pages in PDF"""
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except:
            return 0
