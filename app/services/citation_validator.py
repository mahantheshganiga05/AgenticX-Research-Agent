"""Citation Validation and Evidence Traceability Service.

Ensures every claim in the final answer is traceable to a genuine fetched source.
Rejects hallucinated source IDs (e.g., [S99]) and coordinates controlled correction.
"""

import logging
import re
from typing import Optional, Set
from pydantic import BaseModel, Field

from app.models.schemas import SourceItem, ClaimCitation

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Result of citation validation checks."""
    is_valid: bool
    cited_ids: list[str] = Field(default_factory=list)
    valid_ids: list[str] = Field(default_factory=list)
    invalid_ids: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    claims_breakdown: list[ClaimCitation] = Field(default_factory=list)


class CitationValidator:
    """Validates citations against the current agent source registry."""

    # Matches inline citations like [S1], [S2], [S12]
    CITATION_PATTERN = re.compile(r"\[(S\d+)\]")

    @classmethod
    def extract_citations(cls, text: str) -> list[str]:
        """Extract all unique citation tags like 'S1', 'S2' from text."""
        if not text:
            return []
        matches = cls.CITATION_PATTERN.findall(text)
        # Preserve discovery order while deduplicating
        seen: Set[str] = set()
        deduped = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                deduped.append(m)
        return deduped

    @classmethod
    def validate(
        cls,
        answer_text: str,
        sources: dict[str, SourceItem],
    ) -> ValidationResult:
        """Validate that all citations in the answer map to successfully fetched sources.
        
        Args:
            answer_text: The synthesized text containing [S#] citations.
            sources: The source registry dictionary keyed by source_id.
            
        Returns:
            ValidationResult with detailed status and claims.
        """
        if not answer_text or not answer_text.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Answer text is empty.",
            )

        cited_ids = cls.extract_citations(answer_text)

        # Successful sources that can legitimately be cited
        successful_source_ids = {
            sid for sid, item in sources.items()
            if item.retrieval_status == "success"
        }

        # Check 1: Are there any sources at all in the registry?
        if not successful_source_ids:
            # If no sources were fetched, any factual citation is impossible
            if cited_ids:
                return ValidationResult(
                    is_valid=False,
                    cited_ids=cited_ids,
                    invalid_ids=cited_ids,
                    error_message="Answer cites sources, but no sources were successfully retrieved.",
                )
            return ValidationResult(
                is_valid=True,
                error_message="No sources available; non-factual or general response.",
            )

        # Check 2: Does the answer contain citations?
        if not cited_ids:
            return ValidationResult(
                is_valid=False,
                valid_ids=list(successful_source_ids),
                invalid_ids=[],
                error_message="The answer contains no citations. Factual claims must cite sources like [S1].",
            )

        # Check 3: Are any cited IDs missing from the registry (hallucinated citations)?
        invalid_ids = [cid for cid in cited_ids if cid not in successful_source_ids]

        if invalid_ids:
            return ValidationResult(
                is_valid=False,
                cited_ids=cited_ids,
                valid_ids=list(successful_source_ids),
                invalid_ids=invalid_ids,
                error_message=(
                    f"Answer cites invalid/unfetched source IDs: {', '.join(invalid_ids)}. "
                    f"Available sources are: {', '.join(sorted(successful_source_ids))}."
                ),
            )

        # Extract claims breakdown for UI inspectability
        claims = cls._extract_claim_breakdown(answer_text)

        return ValidationResult(
            is_valid=True,
            cited_ids=cited_ids,
            valid_ids=list(successful_source_ids),
            invalid_ids=[],
            claims_breakdown=claims,
        )

    @classmethod
    def _extract_claim_breakdown(cls, text: str) -> list[ClaimCitation]:
        """Parse sentences or paragraphs to extract which claims reference which sources."""
        breakdown = []
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            # Skip headers
            if line.startswith("#"):
                continue
            # Split line into sentences
            sentences = re.split(r"(?<=[.!?])\s+", line)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                citations = cls.extract_citations(sent)
                if citations:
                    # Clean citation tags from claim text
                    clean_claim = cls.CITATION_PATTERN.sub("", sent).strip()
                    # Remove leading list markers
                    clean_claim = re.sub(r"^[-*•\d\.]+\s*", "", clean_claim)
                    # Clean spacing before punctuation
                    clean_claim = re.sub(r"\s+([.,;:!?])", r"\1", clean_claim)
                    if clean_claim:
                        breakdown.append(ClaimCitation(claim=clean_claim, citations=citations))
        return breakdown

    @classmethod
    def build_sources_section(cls, sources: dict[str, SourceItem], cited_only: bool = True, cited_ids: Optional[list[str]] = None) -> str:
        """Format a markdown sources section to append to answers."""
        if not sources:
            return ""

        target_ids = cited_ids if (cited_only and cited_ids is not None) else list(sources.keys())
        if not target_ids:
            target_ids = list(sources.keys())

        # Sort by numerical ID
        def get_index(sid: str) -> int:
            try:
                return int(sid.replace("S", ""))
            except ValueError:
                return 999

        sorted_ids = sorted([sid for sid in target_ids if sid in sources], key=get_index)

        lines = ["\n\n### Sources\n"]
        for sid in sorted_ids:
            item = sources[sid]
            lines.append(f"- **[{item.source_id}]** [{item.title}]({item.url}) — *{item.domain}*")

        return "\n".join(lines)
