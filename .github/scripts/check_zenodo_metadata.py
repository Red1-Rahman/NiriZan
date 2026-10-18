# .github/scripts/check_zenodo_metadata.py
"""Validate .zenodo.json and check it agrees with CITATION.cff and pyproject.toml."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

ORCID_URL_PREFIX = "https://orcid.org/"


class Creator(BaseModel):
    """One creator entry in .zenodo.json."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    orcid: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
    affiliation: str | None = None


class RelatedIdentifier(BaseModel):
    """One related identifier entry in .zenodo.json."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    identifier: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    scheme: str = Field(min_length=1)
    resource_type: str | None = None


class ZenodoMetadata(BaseModel):
    """The subset of Zenodo deposit metadata that NiriZan maintains."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    title: str = Field(min_length=1)
    upload_type: Literal["software"]
    description: str = Field(min_length=1)
    creators: list[Creator] = Field(min_length=1)
    license: str = Field(min_length=1)
    access_right: Literal["open"]
    keywords: list[str] = Field(min_length=1)
    language: str = "eng"
    related_identifiers: list[RelatedIdentifier] = Field(default_factory=list)


class CffAuthor(BaseModel):
    """One author entry in CITATION.cff."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    family_names: str = Field(alias="family-names", min_length=1)
    given_names: str = Field(alias="given-names", min_length=1)
    orcid: str | None = None

    def zenodo_name(self) -> str:
        """Return the name in Zenodo's "Family, Given" form."""
        return f"{self.family_names}, {self.given_names}"

    def bare_orcid(self) -> str | None:
        """Return the ORCID without the URL prefix, or None if absent."""
        if self.orcid is None:
            return None
        return self.orcid.removeprefix(ORCID_URL_PREFIX)


class CitationFile(BaseModel):
    """The subset of CITATION.cff that must agree with .zenodo.json."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: str
    license: str
    keywords: list[str] = Field(min_length=1)
    authors: list[CffAuthor] = Field(min_length=1)


def check_consistency(
    meta: ZenodoMetadata, cff: CitationFile, version: str, tag: str | None
) -> list[str]:
    """Return a list of human-readable mismatches between the metadata sources."""
    errors: list[str] = []

    if cff.version != version:
        errors.append(f"CITATION.cff version {cff.version} != pyproject version {version}")
    if tag is not None and tag.removeprefix("v") != version:
        errors.append(f"release tag {tag} != pyproject version {version}")
    if meta.license.casefold() != cff.license.casefold():
        errors.append("license differs between .zenodo.json and CITATION.cff")

    zen_keywords = {k.casefold() for k in meta.keywords}
    cff_keywords = {k.casefold() for k in cff.keywords}
    if zen_keywords != cff_keywords:
        errors.append(f"keywords differ: {sorted(zen_keywords ^ cff_keywords)}")

    if len(meta.creators) != len(cff.authors):
        errors.append(
            f"creator count differs: .zenodo.json has {len(meta.creators)}, "
            f"CITATION.cff has {len(cff.authors)}"
        )
    for index, (creator, author) in enumerate(zip(meta.creators, cff.authors, strict=False)):
        if creator.name != author.zenodo_name():
            errors.append(
                f"creator {index} name differs: {creator.name!r} != {author.zenodo_name()!r}"
            )
        if creator.orcid != author.bare_orcid():
            errors.append(
                f"creator {index} ORCID differs: {creator.orcid!r} != {author.bare_orcid()!r}"
            )

    return errors


def main(tag: str | None) -> None:
    """Load all three sources, report mismatches, and emit the version for CI."""
    meta = ZenodoMetadata.model_validate(json.loads(Path(".zenodo.json").read_text("utf-8")))
    cff = CitationFile.model_validate(yaml.safe_load(Path("CITATION.cff").read_text("utf-8")))
    version: str = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))["project"]["version"]

    errors = check_consistency(meta, cff, version, tag)
    if errors:
        for message in errors:
            print(f"::error::{message}")
        raise SystemExit(1)

    print(f"Metadata OK, version {version}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"version={version}\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)