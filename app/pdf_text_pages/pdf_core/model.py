"""One-way typed records shared by conversion and Dify adapter."""

from dataclasses import dataclass, field


class ConversionError(ValueError):
    """Public errors contain only classification and input/page position."""


@dataclass(frozen=True)
class InputPDF:
    filename: str
    source_parameter: str
    source_index: int
    data: bytes


@dataclass(frozen=True)
class PageRecord:
    page_id: str
    page_number: int
    text: str
    image_index: int
    image_filename: str
    png: bytes


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    filename: str
    source_parameter: str
    source_index: int
    pages: list[PageRecord] = field(default_factory=list)


@dataclass(frozen=True)
class BatchRecord:
    batch_id: str
    documents: list[DocumentRecord]

    @property
    def pages(self) -> list[PageRecord]:
        return [p for doc in self.documents for p in doc.pages]

    def metadata(self) -> dict:
        return {
            "schema_version": "1.0",
            "batch_id": self.batch_id,
            "documents": [
                {
                    "document_id": d.document_id,
                    "filename": d.filename,
                    "source_parameter": d.source_parameter,
                    "source_index": d.source_index,
                    "page_count": len(d.pages),
                    "pages": [
                        {
                            "page_id": p.page_id,
                            "page_number": p.page_number,
                            "text_status": "extracted" if p.text else "empty",
                            "text_char_count": len(p.text),
                            "image_index": p.image_index,
                            "image_filename": p.image_filename,
                        }
                        for p in d.pages
                    ],
                }
                for d in self.documents
            ],
        }
