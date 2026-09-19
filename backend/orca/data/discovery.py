"""Dynamic dataset discovery for INCOIS THREDDS OpenDAP data services."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Literal

import httpx

from orca.data.adapters.base import BaseMarineAdapter, SourceUnavailableError

DEFAULT_SST_CATALOG_URL = "https://incois.gov.in/thredds/catalog/osf/sst/catalog.xml"
DEFAULT_CHL_CATALOG_URL = "https://incois.gov.in/thredds/catalog/osf/chl/catalog.xml"

OPENDAP_SST_BASE = "https://incois.gov.in/thredds/dodsC/osf/sst/"
OPENDAP_CHL_BASE = "https://incois.gov.in/thredds/dodsC/osf/chl/"


def parse_thredds_catalog_xml(
    xml_content: bytes | str,
    *,
    dataset_prefix: str,
    opendap_base: str,
    variable_name: str,
    catalog_url: str = "",
) -> str:
    """Parse THREDDS InvCatalog XML content and extract the latest matching NetCDF OpenDAP URL."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise SourceUnavailableError(
            f"INCOIS {variable_name} THREDDS catalog XML parse error: {exc}"
        ) from exc

    matched_files: list[str] = []
    for elem in root.iter():
        name = elem.attrib.get("name", "")
        if name.startswith(dataset_prefix) and name.endswith(".nc"):
            matched_files.append(name)

    if not matched_files:
        raise SourceUnavailableError(
            f"No matching datasets with prefix '{dataset_prefix}' found in catalog {catalog_url}"
        )

    matched_files.sort()
    latest_file = matched_files[-1]
    return f"{opendap_base.rstrip('/')}/{latest_file}"


class INCOISTHREDDSCatalogDiscovery(BaseMarineAdapter):
    """Dynamic dataset catalog crawler for INCOIS THREDDS OpenDAP services."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        verify_ssl: bool = True,
    ):
        super().__init__(timeout_seconds=timeout_seconds, verify_ssl=verify_ssl)

    async def discover_latest_sst_url(
        self,
        catalog_url: str | None = None,
        region_prefix: str = "SST_IO_",
    ) -> str:
        """Fetch SST catalog.xml and discover the latest operational NetCDF dataset URL asynchronously."""
        url = catalog_url or os.getenv("INCOIS_SST_CATALOG_URL", DEFAULT_SST_CATALOG_URL)
        return await self._discover_latest_url(
            catalog_url=url,
            dataset_prefix=region_prefix,
            opendap_base=OPENDAP_SST_BASE,
            variable_name="SST",
        )

    def discover_latest_sst_url_sync(
        self,
        catalog_url: str | None = None,
        region_prefix: str = "SST_IO_",
    ) -> str:
        """Fetch SST catalog.xml and discover the latest operational NetCDF dataset URL synchronously."""
        url = catalog_url or os.getenv("INCOIS_SST_CATALOG_URL", DEFAULT_SST_CATALOG_URL)
        return self._discover_latest_url_sync(
            catalog_url=url,
            dataset_prefix=region_prefix,
            opendap_base=OPENDAP_SST_BASE,
            variable_name="SST",
        )

    async def discover_latest_chl_url(
        self,
        catalog_url: str | None = None,
        dataset_prefix: str = "VIIRS-SNPP-Roll-",
    ) -> str:
        """Fetch CHL catalog.xml and discover the latest operational NetCDF dataset URL asynchronously."""
        url = catalog_url or os.getenv("INCOIS_CHL_CATALOG_URL", DEFAULT_CHL_CATALOG_URL)
        return await self._discover_latest_url(
            catalog_url=url,
            dataset_prefix=dataset_prefix,
            opendap_base=OPENDAP_CHL_BASE,
            variable_name="Chlorophyll",
        )

    def discover_latest_chl_url_sync(
        self,
        catalog_url: str | None = None,
        dataset_prefix: str = "VIIRS-SNPP-Roll-",
    ) -> str:
        """Fetch CHL catalog.xml and discover the latest operational NetCDF dataset URL synchronously."""
        url = catalog_url or os.getenv("INCOIS_CHL_CATALOG_URL", DEFAULT_CHL_CATALOG_URL)
        return self._discover_latest_url_sync(
            catalog_url=url,
            dataset_prefix=dataset_prefix,
            opendap_base=OPENDAP_CHL_BASE,
            variable_name="Chlorophyll",
        )

    async def _discover_latest_url(
        self,
        catalog_url: str,
        dataset_prefix: str,
        opendap_base: str,
        variable_name: str,
    ) -> str:
        try:
            self.validate_target_url(catalog_url)
        except Exception as exc:
            raise SourceUnavailableError(
                f"INCOIS {variable_name} THREDDS catalog request failed (security policy violation): {exc}"
            ) from exc

        try:
            async with self.create_client() as client:
                response = await client.get(catalog_url)
                if response.status_code != 200:
                    raise SourceUnavailableError(
                        f"INCOIS {variable_name} THREDDS catalog returned HTTP {response.status_code}"
                    )
                xml_content = response.content
        except httpx.TimeoutException as exc:
            raise SourceUnavailableError(
                f"INCOIS {variable_name} THREDDS catalog request timed out: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise SourceUnavailableError(
                f"INCOIS {variable_name} THREDDS catalog request failed: {exc}"
            ) from exc

        return parse_thredds_catalog_xml(
            xml_content,
            dataset_prefix=dataset_prefix,
            opendap_base=opendap_base,
            variable_name=variable_name,
            catalog_url=catalog_url,
        )

    def _discover_latest_url_sync(
        self,
        catalog_url: str,
        dataset_prefix: str,
        opendap_base: str,
        variable_name: str,
    ) -> str:
        try:
            self.validate_target_url(catalog_url)
        except Exception as exc:
            raise SourceUnavailableError(
                f"INCOIS {variable_name} THREDDS catalog request failed (security policy violation): {exc}"
            ) from exc

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                verify=self.verify_ssl,
                headers={"User-Agent": "ORCA-Marine-Intelligence/1.0 (Government-Research)"},
            ) as client:
                response = client.get(catalog_url)
                if response.status_code != 200:
                    raise SourceUnavailableError(
                        f"INCOIS {variable_name} THREDDS catalog returned HTTP {response.status_code}"
                    )
                xml_content = response.content
        except httpx.TimeoutException as exc:
            raise SourceUnavailableError(
                f"INCOIS {variable_name} THREDDS catalog request timed out: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise SourceUnavailableError(
                f"INCOIS {variable_name} THREDDS catalog request failed: {exc}"
            ) from exc

        return parse_thredds_catalog_xml(
            xml_content,
            dataset_prefix=dataset_prefix,
            opendap_base=opendap_base,
            variable_name=variable_name,
            catalog_url=catalog_url,
        )
