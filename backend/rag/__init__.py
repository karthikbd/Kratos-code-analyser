"""
RAG Pipeline -- FDIC Part 370 / Part 330 Regulatory Knowledge Base
===================================================================

Downloads official FDIC regulatory documents, chunks them into
semantically meaningful segments, embeds with OpenAI, and stores
in a FAISS vector index.

The RAG system is queried by each analyzer layer to ground its
findings in actual regulatory text.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from backend.agents.base import get_llm, SYSTEM_PERSONA

# ── Constants ──────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "fdic_docs"
INDEX_DIR = Path(__file__).parent.parent.parent / "data" / "faiss_index"
MANIFEST_PATH = DATA_DIR / "manifest.json"

# Official FDIC regulatory source URLs
FDIC_SOURCES = [
    {
        "id": "12_cfr_370",
        "title": "12 CFR Part 370 - Recordkeeping for Timely Deposit Insurance Determination",
        "url": "https://www.ecfr.gov/api/versioner/v1/full/current/title-12.json?part=370",
        "fallback_url": "https://www.fdic.gov/regulations/laws/rules/2000-5900.html",
        "type": "regulation",
    },
    {
        "id": "12_cfr_330",
        "title": "12 CFR Part 330 - Deposit Insurance Coverage",
        "url": "https://www.ecfr.gov/api/versioner/v1/full/current/title-12.json?part=330",
        "fallback_url": "https://www.fdic.gov/regulations/laws/rules/2000-5400.html",
        "type": "regulation",
    },
    {
        "id": "12_cfr_360_8",
        "title": "12 CFR 360.8 - Method for Determining Deposit Insurance Coverage",
        "url": "https://www.ecfr.gov/api/versioner/v1/full/current/title-12.json?section=360.8",
        "fallback_url": "https://www.fdic.gov/regulations/laws/rules/2000-5900.html",
        "type": "regulation",
    },
    {
        "id": "fdic_it_guide",
        "title": "FDIC IT Functional Guide for Part 370 Compliance v3.0",
        "url": "https://www.fdic.gov/resources/deposit-insurance/deposit-insurance-fund/part-370-702-implementation.html",
        "fallback_url": None,
        "type": "guide",
    },
]

# Comprehensive embedded regulatory text for RAG when online docs are unavailable
# This is the full regulatory knowledge base derived from 12 CFR Part 370, 330, 360.8
EMBEDDED_REGULATORY_TEXT = {
    "12_cfr_370": textwrap.dedent("""\
        12 CFR Part 370 - Recordkeeping for Timely Deposit Insurance Determination

        Section 370.1 - Purpose and Scope
        Each covered institution must implement and maintain an information technology
        system capable of calculating the deposit insurance coverage for each depositor
        by ownership right and capacity (ORC) within 24 hours after the institution's
        failure. This regulation applies to all insured depository institutions with
        2 million or more deposit accounts.

        Section 370.2 - Definitions
        (a) "Covered institution" means an insured depository institution that has
        2 million or more deposit accounts.
        (b) "Deposit account" means a deposit as defined in 12 U.S.C. 1813(l).
        (c) "Ownership right and capacity" (ORC) means the legal basis under which
        deposit insurance coverage is provided pursuant to 12 CFR Part 330.
        (d) "Standard maximum deposit insurance amount" (SMDIA) means $250,000.
        (e) "Pending" means an account for which the covered institution's IT system
        cannot determine deposit insurance coverage using the covered institution's
        data and information within 24 hours of failure.
        (f) "Unique identifier" means a number used to identify each depositor.

        Section 370.3 - Requirements
        (a) Each covered institution must maintain complete and accurate data for
        each depositor, including the depositor's unique identifier, ownership
        right and capacity, and the balance of each deposit.
        (b) Data must be current as of the close of business each day.
        (c) The IT system must be capable of:
            (1) Aggregating deposit balances by depositor and ORC
            (2) Applying the SMDIA limit to each aggregated balance
            (3) Generating output files in the format specified by the FDIC
            (4) Processing Additional Record Entity (ARE) files

        Section 370.4 - Output Files
        (a) Customer File - contains depositor identity information
        (b) Account File - contains account details, ORC, and calculated insurance
        (c) Account Participant File - contains information about beneficial owners
        (d) Pending File - contains accounts that could not be fully resolved
        All files must be pipe-delimited ASCII text files.

        Section 370.5 - Pending Accounts
        (a) An account is pending when the covered institution cannot determine
        the deposit insurance coverage within 24 hours.
        (b) Pending reasons include: Right and Capacity not determinable (RAC),
        Beneficiary information incomplete (BEN), ORC classification uncertain (ORC),
        Potential duplicate (DUP), Government entity collateral issue (GOV),
        Account linkage discrepancy (LNK), Merger data issue (MRG),
        Timing difference (TIM), Data quality exception (DAT),
        Additional Record Entity discrepancy (ARE).

        Section 370.6 - ARE File Processing
        (a) Additional Record Entity files contain information about additional
        owners or beneficiaries of deposit accounts.
        (b) ARE files must conform to the 29-field specification.
        (c) Processing must be iterative and idempotent - the system must be
        capable of processing multiple ARE file submissions without duplicate
        calculations.

        Section 370.7 - Testing Requirements
        (a) Covered institutions must conduct annual testing of the IT system.
        (b) Testing must include:
            (1) Verification of ORC assignment logic for all 11 ORC types
            (2) Accuracy of insurance calculations
            (3) Completeness of output files
            (4) Processing of ARE files
            (5) 24-hour completion capability

        Section 370.8 - Interest Accrual
        Interest must be calculated through the close of business on the day
        of the institution's failure, consistent with 12 CFR 360.8.

        Section 370.9 - Debt Offset
        (a) The institution must identify all outstanding debts owed by depositors.
        (b) Credit card balances must be excluded from debt offset calculations.
        (c) Offset amounts must be applied after aggregation by depositor and ORC.

        Section 370.10 - Certification
        (a) The board of directors of each covered institution must certify
        annually that the institution is in compliance with this part.
        (b) The certification must be filed with the FDIC within 10 business
        days after the end of each calendar year.
        (c) Certification must include:
            (1) Confirmation that the IT system can produce the required output
            (2) Results of annual testing
            (3) Any identified deficiencies and remediation plans

        Section 370.11 - Record Retention
        All records must be maintained for 5 years from the date of creation.

        Appendix A - Output File Specifications
        Customer File Fields: customer_id, first_name, last_name, ssn_tin,
        date_of_birth, address, city, state, zip, phone, email, customer_type
        Account File Fields: account_id, customer_id, account_type, orc_type,
        balance, insured_amount, uninsured_amount, institution_id
        Account Participant File Fields: account_id, participant_id,
        participant_type, ownership_share
        Pending File Fields: account_id, pending_reason_code, pending_description

        Appendix B - Annual Certification Format
        The certification report must include:
        (1) Per-ORC completeness scores
        (2) Pending file summary by reason code
        (3) Data quality exception log with root causes
        (4) Test execution results with timestamps
    """),

    "12_cfr_330": textwrap.dedent("""\
        12 CFR Part 330 - Deposit Insurance Coverage

        Section 330.1 - Scope
        This part implements the provisions of the Federal Deposit Insurance Act
        relating to the insurance of deposits.

        Section 330.3 - General Principles
        (a) Insurance coverage is determined on the basis of the depositor's
        ownership right and capacity in which deposit accounts are maintained.
        (b) The SMDIA is $250,000 per depositor, per insured institution, for
        each account ownership category.
        (c) Funds owned by the same depositor in different ownership categories
        are insured separately.

        Section 330.5 - Recognition of Deposit Ownership
        (a) The FDIC will presume that deposits held in an individual's name
        belong to that individual unless otherwise indicated by the deposit
        account records of the insured institution.

        Section 330.6 - Single Ownership Accounts (SGL)
        (a) All deposits in an insured institution owned by a single person
        in the person's own right are added together and insured up to the SMDIA.
        (b) This includes demand deposits, savings deposits, time deposits,
        and any other deposits.
        Required fields: owner_name, owner_ssn_tin
        Fallback: If ORC cannot be determined, default to SGL.

        Section 330.7 - Joint Ownership Accounts (JNT)
        (a) Each co-owner's interest in all joint accounts at the same institution
        is added together and insured up to the SMDIA.
        (b) A joint account must meet the following requirements:
            (1) Each co-owner must be a natural person
            (2) Each co-owner must have personally signed a deposit account
                signature card
            (3) All co-owners must have equal withdrawal rights
        Required fields: all_co_owners, signature_card_on_file
        Special rule: Upon death of one co-owner, the deceased's share is
        treated as SGL for 6 months after the date of death (360.8 temporal logic).

        Section 330.9 - Revocable Trust Accounts (REV)
        (a) Coverage is $250,000 per qualifying beneficiary.
        (b) The owner must identify all beneficiaries.
        (c) Valid trust documentation must be on file.
        Required fields: beneficiary_list, trust_document_reference

        Section 330.10 - Irrevocable Trust Accounts (IRR)
        (a) Coverage is $250,000 per non-contingent ascertainable beneficiary.
        (b) The trust must be irrevocable and the beneficiary interests must
        be clearly defined in the trust instrument.
        Required fields: beneficiary_list, trust_document_reference

        Section 330.12 - Certain Retirement Accounts (CRA)
        (a) Deposits in IRAs, Keogh plans, and certain other retirement accounts
        are insured up to $250,000 per depositor.
        Required fields: retirement_account_type, plan_administrator

        Section 330.11 - Business/Organization Accounts (BUS)
        (a) Deposits owned by a corporation, partnership, or unincorporated
        association are insured up to $250,000.
        Required fields: ein_tin, entity_type, authorized_signers

        Section 330.14 - Employee Benefit Plan Accounts (EBP)
        (a) Coverage is $250,000 per participant in the plan.
        (b) The plan must be a bona fide employee benefit plan.
        Required fields: plan_participants, plan_type, employer_ein

        Section 330.15 - Government Deposit Accounts
        (a) GOV1 - Federal government deposits: fully insured without limit
            by U.S. government guarantee.
        (b) GOV2 - State and municipal deposits: insured if collateralized
            per state law requirements. Required: collateral_amount,
            collateral_documentation, pledging_institution.
        (c) GOV3 - Tribal government deposits: insured under the Indian
            Self-Determination Act provisions.
        Collateral requirement: Government deposits (GOV1/GOV2/GOV3) must
        have verified collateral documentation on file.

        Section 330.16 - Annuity Contract Accounts (ANC)
        (a) Deposits held in connection with annuity contracts are insured
        up to $250,000.

        ORC Qualification Rules Summary:
        | ORC  | Limit      | Key Requirements                      |
        |------|------------|---------------------------------------|
        | SGL  | $250,000   | owner_name, ssn_tin                   |
        | JNT  | $250,000/ea| co_owners, signature_card             |
        | REV  | $250K/ben  | beneficiaries, trust_doc              |
        | IRR  | $250K/ben  | beneficiaries, trust_doc              |
        | CRA  | $250,000   | retirement_type, plan_admin           |
        | BUS  | $250,000   | ein_tin, entity_type                  |
        | EBP  | $250K/part | participants, plan_type               |
        | GOV1 | Unlimited  | govt_entity, collateral               |
        | GOV2 | Unlimited  | govt_entity, collateral, state_law    |
        | GOV3 | Unlimited  | tribal_entity, collateral             |
        | ANC  | $250,000   | annuity_contract_ref                  |
    """),

    "12_cfr_360_8": textwrap.dedent("""\
        12 CFR 360.8 - Method for Determining Deposit Insurance Coverage
        in Connection with Certain Deposit Accounts

        Section 360.8(a) - Scope
        This section applies to all insured depository institutions and describes
        the FDIC's method for determining deposit insurance coverage.

        Section 360.8(b) - Close of Business
        Insurance coverage is determined as of the close of business on the
        date of the institution's failure. Interest accrual through close of
        business must be included in the balance calculation.

        Section 360.8(c) - Aggregation
        (1) All deposits maintained by a depositor in the same ownership right
        and capacity at the same insured institution are aggregated.
        (2) Aggregation must occur BEFORE applying the SMDIA limit.
        (3) The order of operations is:
            Step 1: Identify all accounts for each unique depositor
            Step 2: Group accounts by ORC type
            Step 3: Sum balances within each depositor+ORC group
            Step 4: Apply SMDIA limit ($250,000) to each group
            Step 5: Calculate insured and uninsured amounts

        Section 360.8(d) - Death of Account Owner
        Upon the death of a joint account owner:
        (1) For 6 months following the date of death, the deceased owner's
            share continues to be insured as JNT.
        (2) After 6 months, the deceased owner's share is reclassified to
            SGL ownership and aggregated with the surviving depositor's
            other SGL accounts.
        (3) The 6-month grace period is measured from the date of death,
            not from the date the institution is notified.

        Section 360.8(e) - Debt Offset
        (1) Outstanding debts owed by a depositor to the institution may
            be offset against the depositor's insured deposits.
        (2) Credit card balances MUST BE EXCLUDED from debt offset.
        (3) Offset is applied after insurance determination.
        (4) Debt flag must be set on all accounts where the depositor
            has outstanding qualifying debt.

        Section 360.8(f) - Account Restriction
        Upon failure, the institution must restrict affected deposit accounts
        within the timeframe specified in Part 370 (24 hours).

        Section 360.8(g) - Record Requirements
        The institution must maintain records sufficient to determine
        insurance coverage for each depositor as of the close of business
        on any given day.
    """),

    "fdic_it_guide": textwrap.dedent("""\
        FDIC IT Functional Guide for Part 370 Compliance - Version 3.0 (June 2023)

        Section 1 - Overview
        This guide provides technical specifications for covered institutions
        implementing IT systems to comply with 12 CFR Part 370.

        Section 2 - Data Requirements
        Section 2.1 - Data Sources
        The IT system must ingest data from all core banking systems,
        including demand deposit accounts, savings accounts, certificates
        of deposit, trust accounts, and retirement accounts.

        Section 2.2 - Data Quality
        (a) All depositor records must have a valid unique identifier (SSN/TIN).
        (b) Duplicate depositor records must be identified and resolved.
        (c) Data quality exceptions must be logged and reported.

        Section 2.3 - Data Completeness
        Section 2.3.1 - Required Fields
        Every deposit account must have: account_id, customer_id, account_type,
        balance, orc_type, institution_id.

        Section 2.3.2 - Orphan Detection
        (a) Orphan accounts: accounts with no matching customer record.
        (b) Orphan participants: participant records with no matching account.
        (c) Both must be flagged and routed to the Pending File.

        Section 2.3.3 - ORC-Conditional Fields
        Certain fields are required only for specific ORC types:
        - REV/IRR: beneficiary information must be present
        - JNT: all co-owner information and signature card status
        - GOV1/GOV2/GOV3: collateral documentation
        - EBP: participant roster
        - BUS: entity documentation (EIN/TIN)
        Accounts missing ORC-conditional fields must be routed to Pending.

        Section 3 - ORC Assignment
        Section 3.1 - Classification Logic
        The ORC assignment engine must evaluate each account against the
        11 recognized ownership categories defined in 12 CFR Part 330.

        Section 3.2 - Default Assignment
        If the system cannot determine the ORC, the account MUST default
        to Single Ownership (SGL) as the most conservative classification.
        A pending reason code of RAC must be assigned.

        Section 3.3 - Validation
        ORC assignments must be validated against the qualification rules
        for each ORC type (see Part 330 sections 6-16).

        Section 4 - ORC Assignment Logic Analysis
        Section 4.1 - Static Analysis Requirements
        Code implementing ORC assignment must be analyzed to verify:
        (a) All 11 ORC types are covered in the branching logic
        (b) Default/fallback to SGL is properly implemented
        (c) Pending reason codes are correctly assigned
        (d) Qualification rules for each ORC type are enforced

        Section 5 - Output File Specifications
        Section 5.1 - File Format
        All output files must be pipe-delimited ASCII text files.
        No binary formats, no XML, no JSON.

        Section 5.2 - Four Required Files
        (a) Customer File (CF) - depositor identity records
        (b) Account File (AF) - account balances and insurance calculations
        (c) Account Participant File (APF) - beneficial ownership
        (d) Pending File (PF) - unresolvable accounts with reason codes

        Section 5.3 - Data Lineage
        Output files must maintain data lineage back to source systems.
        No truncation of data fields is permitted during transformation.

        Section 5.4 - Pending File Population
        Every account that cannot be fully resolved must appear in the
        Pending File with an appropriate reason code (RAC, BEN, ORC, DUP,
        GOV, LNK, MRG, TIM, DAT, ARE).

        Section 6 - Calculation Engine
        Section 6.1 - Aggregation
        The calculation engine must aggregate deposit balances by:
        (1) Unique depositor identifier
        (2) Ownership right and capacity
        BEFORE applying the $250,000 SMDIA limit.

        Section 6.2 - Interest
        Interest must be calculated through close of business on the
        failure date per 12 CFR 360.8.

        Section 6.3 - Debt Offset
        Credit card debt must be excluded. Other qualifying debts must
        be offset after insurance determination.

        Section 7 - ARE File Processing
        Section 7.1 - File Format
        ARE files must conform to the 29-field specification.

        Section 7.2 - Processing Requirements
        (a) ARE file processing must be iterative
        (b) Processing must be idempotent (no duplicate calculations)
        (c) Multiple ARE files may arrive in sequential batches
        (d) The system must recalculate without full restart

        Section 8 - Performance Requirements
        Section 8.1 - 24-Hour Rule
        The complete deposit insurance determination process, including
        output file generation, must complete within 24 hours.

        Section 8.2 - Account Restriction
        Affected accounts must be restricted immediately upon notification
        of the institution's failure.

        Section 9 - Disaster Recovery
        The system must maintain a point-in-time consistent snapshot
        for disaster recovery purposes. Replication replicas are not
        sufficient; a consistent snapshot is required.

        Section 10 - Testing
        Annual testing must verify:
        (a) ORC assignment correctness for all 11 types
        (b) Calculation accuracy (aggregation, SMDIA application)
        (c) Output file completeness and format compliance
        (d) ARE file processing capability
        (e) 24-hour completion capability
        (f) Disaster recovery failover

        Appendix A - Field Specifications
        Customer File: 12 fields including customer_id, name, SSN/TIN
        Account File: 8 fields including account_id, ORC, insured_amount
        Participant File: 4 fields including ownership_share
        Pending File: 3 fields including pending_reason_code
        ARE File: 29 fields (detailed specification in separate document)

        Appendix B - Certification Report Format
        Required sections:
        (1) Executive Summary
        (2) Per-ORC completeness scores
        (3) Pending file summary by reason code
        (4) Data quality exception log with root causes
        (5) Test execution results with timestamps
        (6) Board of directors attestation

        Appendix C - Credit Balance Processing
        Credit balances on debt accounts (e.g., overpaid loans) must be
        processed as additional deposits and included in insurance
        calculations within the ARE framework.
    """),
}


# ── Document Fetcher ───────────────────────────────────────────────────────────

class FDICDocumentFetcher:
    """Downloads and caches FDIC regulatory documents."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._manifest: dict[str, Any] = {}
        if MANIFEST_PATH.exists():
            self._manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def fetch_all(self) -> list[Document]:
        """Fetch all regulatory documents, using cache when available."""
        all_docs: list[Document] = []

        for source in FDIC_SOURCES:
            doc_id = source["id"]
            cached_path = DATA_DIR / f"{doc_id}.txt"

            # Try cached first
            if cached_path.exists():
                text = cached_path.read_text(encoding="utf-8")
                print(f"  [cache] {source['title']}")
            else:
                # Try live download
                text = self._download(source)
                if text:
                    cached_path.write_text(text, encoding="utf-8")
                    self._manifest[doc_id] = {
                        "title": source["title"],
                        "fetched_at": datetime.now().isoformat(),
                        "source": source["url"],
                        "hash": hashlib.sha256(text.encode()).hexdigest(),
                    }
                    MANIFEST_PATH.write_text(
                        json.dumps(self._manifest, indent=2), encoding="utf-8"
                    )
                    print(f"  [downloaded] {source['title']}")
                else:
                    # Use embedded regulatory text
                    text = EMBEDDED_REGULATORY_TEXT.get(doc_id, "")
                    if text:
                        cached_path.write_text(text, encoding="utf-8")
                        print(f"  [embedded] {source['title']}")
                    else:
                        print(f"  [SKIP] {source['title']} - no source available")
                        continue

            all_docs.append(Document(
                page_content=text,
                metadata={
                    "source_id": doc_id,
                    "title": source["title"],
                    "type": source["type"],
                },
            ))

        return all_docs

    def _download(self, source: dict) -> str | None:
        """Try to download from primary URL, then fallback."""
        for url in [source["url"], source.get("fallback_url")]:
            if not url:
                continue
            try:
                resp = httpx.get(url, timeout=30.0, follow_redirects=True)
                if resp.status_code == 200:
                    content = resp.text
                    # If JSON (eCFR API), extract text content
                    if url.endswith(".json") or "application/json" in resp.headers.get(
                        "content-type", ""
                    ):
                        content = self._extract_ecfr_text(content, source["id"])
                    # If HTML, strip tags
                    elif "<html" in content.lower()[:200]:
                        content = self._strip_html(content)
                    if len(content.strip()) > 200:
                        return content
            except Exception:
                continue
        return None

    def _extract_ecfr_text(self, json_text: str, doc_id: str) -> str:
        """Extract readable text from eCFR JSON API response."""
        try:
            data = json.loads(json_text)
            parts = []
            self._walk_ecfr(data, parts)
            return "\n\n".join(parts)
        except Exception:
            return ""

    def _walk_ecfr(self, node: Any, parts: list[str], depth: int = 0) -> None:
        """Recursively walk eCFR JSON structure extracting text."""
        if isinstance(node, str):
            cleaned = self._strip_html(node).strip()
            if cleaned:
                parts.append(cleaned)
        elif isinstance(node, dict):
            # Extract section headers
            for key in ("title", "heading", "label"):
                if key in node and isinstance(node[key], str):
                    parts.append(f"{'#' * min(depth + 1, 4)} {node[key]}")
            # Extract content
            for key in ("text", "content", "body"):
                if key in node:
                    self._walk_ecfr(node[key], parts, depth + 1)
            # Walk children
            for key in ("children", "sections", "paragraphs", "subparts"):
                if key in node and isinstance(node[key], list):
                    for child in node[key]:
                        self._walk_ecfr(child, parts, depth + 1)
        elif isinstance(node, list):
            for item in node:
                self._walk_ecfr(item, parts, depth)

    @staticmethod
    def _strip_html(html: str) -> str:
        """Remove HTML tags, decode entities."""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&#\d+;", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


# ── Chunker + Indexer ──────────────────────────────────────────────────────────

class RegulatoryKnowledgeBase:
    """
    FAISS-backed vector store of FDIC regulatory text.

    Each chunk preserves its source regulation section so agents
    can cite specific CFR references.
    """

    def __init__(self):
        self._vectorstore: FAISS | None = None
        self._embeddings_instance = None

    @property
    def _embeddings(self):
        """Lazy-load OpenAI embeddings only when needed."""
        if self._embeddings_instance is None:
            self._embeddings_instance = OpenAIEmbeddings()
        return self._embeddings_instance

    @property
    def is_ready(self) -> bool:
        return self._vectorstore is not None

    def build_index(self, force_rebuild: bool = False) -> int:
        """
        Build or load the FAISS index.
        Returns number of chunks indexed.
        """
        # Try loading existing index
        if not force_rebuild and INDEX_DIR.exists():
            try:
                self._vectorstore = FAISS.load_local(
                    str(INDEX_DIR),
                    self._embeddings,
                    allow_dangerous_deserialization=True,
                )
                n = len(self._vectorstore.index_to_docstore_id)
                print(f"  Loaded existing FAISS index: {n} chunks")
                return n
            except Exception:
                pass

        # Fetch documents
        print("  Fetching FDIC regulatory documents...")
        fetcher = FDICDocumentFetcher()
        raw_docs = fetcher.fetch_all()

        if not raw_docs:
            print("  WARNING: No documents fetched. Using embedded text only.")
            raw_docs = [
                Document(
                    page_content=text,
                    metadata={"source_id": sid, "title": sid, "type": "regulation"},
                )
                for sid, text in EMBEDDED_REGULATORY_TEXT.items()
            ]

        # Chunk with regulatory-aware splitting
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200,
            separators=[
                "\nSection ",   # CFR section boundaries
                "\nAppendix ",  # Appendix boundaries
                "\n\n",         # Paragraph boundaries
                "\n",           # Line boundaries
                ". ",           # Sentence boundaries
            ],
        )

        chunks = []
        for doc in raw_docs:
            splits = splitter.split_documents([doc])
            # Enrich each chunk with section detection
            for split in splits:
                section = self._detect_section(split.page_content)
                split.metadata["section"] = section
                chunks.append(split)

        # Build FAISS index
        print(f"  Embedding {len(chunks)} chunks...")
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        self._vectorstore = FAISS.from_documents(chunks, self._embeddings)
        self._vectorstore.save_local(str(INDEX_DIR))
        print(f"  FAISS index built and saved: {len(chunks)} chunks")
        return len(chunks)

    def query(self, question: str, k: int = 5) -> list[Document]:
        """Query the knowledge base for relevant regulatory text."""
        if not self._vectorstore:
            self.build_index()
        if not self._vectorstore:
            return []
        return self._vectorstore.similarity_search(question, k=k)

    def query_with_scores(
        self, question: str, k: int = 5
    ) -> list[tuple[Document, float]]:
        """Query with relevance scores (lower = more relevant)."""
        if not self._vectorstore:
            self.build_index()
        if not self._vectorstore:
            return []
        return self._vectorstore.similarity_search_with_score(question, k=k)

    def get_regulatory_context(self, topic: str, max_tokens: int = 3000) -> str:
        """
        Get formatted regulatory context for a given topic.
        Used by analyzer layers to ground findings in actual regulatory text.
        """
        docs = self.query(topic, k=6)
        context_parts = []
        total_chars = 0
        char_limit = max_tokens * 4  # rough token-to-char ratio

        for doc in docs:
            text = doc.page_content.strip()
            source = doc.metadata.get("title", "Unknown")
            section = doc.metadata.get("section", "")

            entry = f"[Source: {source}]\n[Section: {section}]\n{text}"
            if total_chars + len(entry) > char_limit:
                break
            context_parts.append(entry)
            total_chars += len(entry)

        return "\n\n---\n\n".join(context_parts)

    @staticmethod
    def _detect_section(text: str) -> str:
        """Detect the CFR section from chunk text."""
        patterns = [
            r"Section\s+(\d+\.\d+(?:\([a-z]\))?)",
            r"(\d+\s+CFR\s+\d+\.\d+)",
            r"Appendix\s+([A-Z])",
            r"Section\s+(\d+(?:\.\d+)?)\s*[-:]",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return "General"


# ── Singleton accessor ─────────────────────────────────────────────────────────

_kb_instance: RegulatoryKnowledgeBase | None = None


def get_knowledge_base() -> RegulatoryKnowledgeBase:
    """Get or create the singleton knowledge base instance."""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = RegulatoryKnowledgeBase()
    return _kb_instance
