from __future__ import annotations

import re
import time
from urllib.parse import quote

import requests
from django.core.management.base import BaseCommand

from base.models import Compound


SKIP_NAME_TERMS = (
    " + ",
    "/",
    " route",
    " products",
    " product",
    "associated",
    "not resolved",
    "downstream",
    "cleavage",
    "derivatives",
)


class Command(BaseCommand):
    help = "Fill missing Compound SMILES values from PubChem CIDs or conservative name lookup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--role",
            default="PESTICIDE",
            help="Compound role to update. Use ALL to include metabolites.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of compounds to check. Default checks all matches.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.15,
            help="Delay between PubChem requests in seconds.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show proposed updates without saving.",
        )
        parser.add_argument(
            "--lookup-names",
            action="store_true",
            help="When no CID is stored, try conservative PubChem name lookup for single compounds.",
        )

    def handle(self, *args, **options):
        qs = Compound.objects.filter(smiles="").order_by("role", "name")
        if not options["lookup_names"]:
            qs = qs.filter(pubchem_cid__gt="")
        role = options["role"].strip().upper()
        if role != "ALL":
            qs = qs.filter(role=role)
        if options["limit"]:
            qs = qs[: options["limit"]]

        checked = 0
        updated = 0
        failed = 0
        skipped = 0
        session = requests.Session()

        for compound in qs:
            checked += 1
            cid = compound.pubchem_cid
            try:
                if not cid and options["lookup_names"]:
                    cid = self.lookup_cid(session, compound.name)
                if not cid:
                    skipped += 1
                    self.stdout.write(f"Skipped {compound.name}: no CID or conservative name match")
                    continue
                props = self.fetch_properties(session, cid)
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Could not fetch {compound.name} ({cid or 'no CID'}): {exc}")
                continue

            smiles = (
                props.get("CanonicalSMILES")
                or props.get("IsomericSMILES")
                or props.get("SMILES")
                or props.get("ConnectivitySMILES")
                or ""
            )
            inchikey = props.get("InChIKey") or ""
            if not smiles:
                failed += 1
                self.stderr.write(f"No SMILES returned for {compound.name} ({cid})")
                continue

            self.stdout.write(f"{compound.name}: {smiles}")
            if not options["dry_run"]:
                compound.smiles = smiles
                if cid and not compound.pubchem_cid:
                    compound.pubchem_cid = str(cid)
                if inchikey and not compound.inchikey:
                    compound.inchikey = inchikey
                compound.save(update_fields=["smiles", "pubchem_cid", "inchikey"])
            updated += 1
            if options["delay"]:
                time.sleep(options["delay"])

        self.stdout.write(
            self.style.SUCCESS(
                "PubChem SMILES fill complete | "
                f"checked={checked}, updated={updated}, skipped={skipped}, "
                f"failed={failed}, dry_run={options['dry_run']}"
            )
        )

    def fetch_properties(self, session, cid):
        url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
            f"{cid}/property/CanonicalSMILES,IsomericSMILES,InChIKey/JSON"
        )
        response = session.get(url, timeout=20)
        response.raise_for_status()
        return response.json()["PropertyTable"]["Properties"][0]

    def lookup_cid(self, session, name):
        for candidate in self.name_candidates(name):
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(candidate)}/cids/JSON"
            response = session.get(url, timeout=20)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            cids = response.json().get("IdentifierList", {}).get("CID", [])
            if cids:
                return str(cids[0])
        return ""

    def name_candidates(self, name):
        cleaned = re.sub(r"\s+", " ", name).strip()
        lowered = cleaned.lower()
        if any(term in lowered for term in SKIP_NAME_TERMS):
            return []

        candidates = [cleaned]
        without_parenthetical = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned).strip()
        if without_parenthetical and without_parenthetical != cleaned:
            candidates.append(without_parenthetical)
        return candidates
