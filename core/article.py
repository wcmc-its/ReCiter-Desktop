"""Article data model — represents a PubMed article."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Author:
    first_name: str = ""
    last_name: str = ""
    initials: str = ""
    affiliation: str = ""
    orcid: str = ""
    rank: int = 0
    is_target_author: bool = False

    @property
    def first_initial(self) -> str:
        if self.first_name:
            return self.first_name[0].upper()
        if self.initials:
            return self.initials[0].upper()
        return ""

    @property
    def middle_initial(self) -> str:
        if self.initials and len(self.initials) > 1:
            return self.initials[1].upper()
        return ""

    @property
    def full_name(self) -> str:
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts)


@dataclass
class MeshHeading:
    descriptor_name: str = ""
    qualifier_names: List[str] = field(default_factory=list)
    major_topic: bool = False


@dataclass
class Article:
    pmid: int = 0
    title: str = ""
    journal_title: str = ""
    journal_issn: List[str] = field(default_factory=list)
    pub_year: int = 0
    pub_date: str = ""
    authors: List[Author] = field(default_factory=list)
    mesh_headings: List[MeshHeading] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    grants: List[str] = field(default_factory=list)
    publication_types: List[str] = field(default_factory=list)
    doi: str = ""
    abstract: str = ""
    # Scoring metadata
    target_author_index: int = -1
    user_assertion: str = ""  # ACCEPTED, REJECTED, or empty

    @property
    def target_author(self) -> Optional[Author]:
        if 0 <= self.target_author_index < len(self.authors):
            return self.authors[self.target_author_index]
        return None

    @property
    def author_count(self) -> int:
        return len(self.authors)

    @property
    def non_target_authors(self) -> List[Author]:
        return [a for i, a in enumerate(self.authors) if i != self.target_author_index]

    @property
    def major_mesh_terms(self) -> List[str]:
        return [mh.descriptor_name for mh in self.mesh_headings if mh.major_topic]
