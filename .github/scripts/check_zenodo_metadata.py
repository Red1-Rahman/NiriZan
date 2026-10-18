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


class Creator(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    orcid: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
    affiliation: str | None = None


class RelatedIdentifier(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    identifier: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    scheme: str = Field(min_length=1)
    resource_type: str | None = None


class ZenodoMetadata(BaseModel):
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


def main(tag: str | None) -> None:
    meta = ZenodoMetadata.model_validate(json.loads(Path(".zenodo.json").read_text("utf-8")))
    cff = yaml.safe_load(Path("CITATION.cff").read_text("utf-8"))
    version: str = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))["project"]["version"]

    errors: list[str] = []
    if str(cff["version"]) != version:
        errors.append(f"CITATION.cff version {cff['version']} != pyproject version {version}")
    if tag is not None and tag.removeprefix("v") != version:
        errors.append(f"release tag {tag} != pyproject version {version}")
    if meta.license.casefold() != str(cff["license"]).casefold():
        errors.append("license differs between .zenodo.json and CITATION.cff")

    zen_keywords = {k.casefold() for k in meta.keywords}
    cff_keywords = {str(k).casefold() for k in cff["keywords"]}
    if zen_keywords != cff_keywords:
        errors.append(f"keywords differ: {sorted(zen_keywords ^ cff_keywords)}")

    cff_orcid = str(cff["authors"][0].get("orcid", "")).removeprefix("https://orcid.org/")
    if (meta.creators[0].orcid or "") != cff_orcid:
        errors.append("first author ORCID differs between .zenodo.json and CITATION.cff")

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