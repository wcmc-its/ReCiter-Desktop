"""Identity data model — represents a researcher to be disambiguated."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Identity:
    person_id: str
    first_name: str
    last_name: str
    middle_name: str = ""
    primary_email: str = ""
    primary_institution: str = ""
    department: str = ""
    title: str = ""
    orcid: str = ""
    bachelor_year: int = 0
    doctoral_year: int = 0

    @property
    def first_initial(self) -> str:
        return self.first_name[0].upper() if self.first_name else ""

    @property
    def middle_initial(self) -> str:
        return self.middle_name[0].upper() if self.middle_name else ""

    @property
    def last_initial(self) -> str:
        return self.last_name[0].upper() if self.last_name else ""

    @property
    def email_domain(self) -> str:
        if "@" in self.primary_email:
            return self.primary_email.split("@")[1].lower()
        return ""

    @property
    def email_uid(self) -> str:
        if "@" in self.primary_email:
            return self.primary_email.split("@")[0].lower()
        return ""

    @classmethod
    def from_dict(cls, d: dict) -> "Identity":
        return cls(
            person_id=str(d.get("person_id", "")),
            first_name=str(d.get("first_name", "")),
            last_name=str(d.get("last_name", "")),
            middle_name=str(d.get("middle_name", "") or ""),
            primary_email=str(d.get("email", d.get("primary_email", "")) or ""),
            primary_institution=str(d.get("institution", d.get("primary_institution", "")) or ""),
            department=str(d.get("department", "") or ""),
            title=str(d.get("title", "") or ""),
            orcid=str(d.get("orcid", "") or ""),
            bachelor_year=int(d.get("bachelor_year", 0) or 0),
            doctoral_year=int(d.get("doctoral_year", 0) or 0),
        )
