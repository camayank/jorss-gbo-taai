"""
Synthetic data generator for training document classifiers.

Generates realistic synthetic tax document text for training ML models.
"""

import random
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class SyntheticDocument:
    """A synthetic training document."""
    text: str
    document_type: str
    variations: List[str]


class SyntheticDataGenerator:
    """
    Generator for synthetic tax document training data.

    Creates realistic document text samples for each supported
    tax document type to train the TF-IDF classifier.
    """

    # Template components for each document type
    TEMPLATES: Dict[str, Dict] = {
        "w2": {
            "headers": [
                "Form W-2 Wage and Tax Statement",
                "W-2 Wage and Tax Statement",
                "Form W-2",
                "Department of the Treasury Internal Revenue Service",
            ],
            "fields": [
                "Employer's name, address, and ZIP code",
                "Employer identification number (EIN)",
                "Employee's social security number",
                "Employee's name",
                "Wages, tips, other compensation",
                "Federal income tax withheld",
                "Social security wages",
                "Social security tax withheld",
                "Medicare wages and tips",
                "Medicare tax withheld",
                "Social security tips",
                "Allocated tips",
                "Box 1 Wages tips other compensation",
                "Box 2 Federal income tax withheld",
                "Box 3 Social security wages",
                "Box 4 Social security tax withheld",
                "Box 5 Medicare wages and tips",
                "Box 6 Medicare tax withheld",
                "State wages tips",
                "State income tax",
                "Local wages tips",
                "Local income tax",
            ],
            "amounts": ["$", "wages", "withheld", "compensation"],
        },
        "w2g": {
            "headers": [
                "Form W-2G Certain Gambling Winnings",
                "W-2G Gambling Winnings",
                "Form W-2G",
                "Certain Gambling Winnings",
            ],
            "fields": [
                "Payer's name",
                "Payer's federal identification number",
                "Reportable winnings",
                "Date won",
                "Type of wager",
                "Federal income tax withheld",
                "State winnings",
                "State income tax withheld",
                "Winner's name",
                "Winner's TIN",
                "Box 1 Reportable winnings",
                "Box 2 Date won",
                "Box 3 Type of wager",
                "Box 4 Federal income tax withheld",
                "Transaction",
                "Race",
                "Cashier",
            ],
            "amounts": ["winnings", "withheld", "gambling", "payout"],
        },
        "1099-int": {
            "headers": [
                "Form 1099-INT Interest Income",
                "1099-INT Interest Income",
                "Form 1099-INT",
                "Interest Income Statement",
            ],
            "fields": [
                "Payer's name",
                "Payer's TIN",
                "Recipient's TIN",
                "Interest income",
                "Early withdrawal penalty",
                "Interest on U.S. Savings Bonds",
                "Federal income tax withheld",
                "Investment expenses",
                "Tax-exempt interest",
                "Private activity bond interest",
                "Box 1 Interest income",
                "Box 2 Early withdrawal penalty",
                "Box 3 Interest on US Savings Bonds",
                "Box 4 Federal income tax withheld",
                "Box 8 Tax-exempt interest",
            ],
            "amounts": ["interest", "penalty", "income"],
        },
        "1099-div": {
            "headers": [
                "Form 1099-DIV Dividends and Distributions",
                "1099-DIV Dividends and Distributions",
                "Form 1099-DIV",
                "Dividend Income Statement",
            ],
            "fields": [
                "Payer's name",
                "Total ordinary dividends",
                "Qualified dividends",
                "Total capital gain distributions",
                "Unrecap. Sec. 1250 gain",
                "Section 1202 gain",
                "Collectibles gain",
                "Nondividend distributions",
                "Federal income tax withheld",
                "Investment expenses",
                "Foreign tax paid",
                "Box 1a Total ordinary dividends",
                "Box 1b Qualified dividends",
                "Box 2a Total capital gain distr",
                "Box 3 Nondividend distributions",
            ],
            "amounts": ["dividends", "gain", "distributions"],
        },
        "1099-nec": {
            "headers": [
                "Form 1099-NEC Nonemployee Compensation",
                "1099-NEC Nonemployee Compensation",
                "Form 1099-NEC",
            ],
            "fields": [
                "Payer's name",
                "Payer's TIN",
                "Recipient's TIN",
                "Nonemployee compensation",
                "Payer made direct sales totaling",
                "Federal income tax withheld",
                "State tax withheld",
                "State/Payer's state no.",
                "State income",
                "Box 1 Nonemployee compensation",
                "Box 4 Federal income tax withheld",
            ],
            "amounts": ["compensation", "payment", "income"],
        },
        "1099-misc": {
            "headers": [
                "Form 1099-MISC Miscellaneous Information",
                "1099-MISC Miscellaneous Income",
                "Form 1099-MISC",
            ],
            "fields": [
                "Payer's name",
                "Rents",
                "Royalties",
                "Other income",
                "Fishing boat proceeds",
                "Medical and health care payments",
                "Substitute payments",
                "Crop insurance proceeds",
                "Gross proceeds paid to attorney",
                "Section 409A deferrals",
                "Golden parachute",
                "Nonqualified deferred compensation",
                "Box 1 Rents",
                "Box 2 Royalties",
                "Box 3 Other income",
            ],
            "amounts": ["rents", "royalties", "income", "proceeds"],
        },
        "1099-b": {
            "headers": [
                "Form 1099-B Proceeds From Broker and Barter Exchange",
                "1099-B Proceeds From Broker",
                "Form 1099-B",
                "Broker Transactions",
            ],
            "fields": [
                "Broker's name",
                "Proceeds",
                "Cost or other basis",
                "Accrued market discount",
                "Wash sale loss disallowed",
                "Type of gain or loss",
                "Short-term",
                "Long-term",
                "Date acquired",
                "Date sold",
                "CUSIP number",
                "Box 1d Proceeds",
                "Box 1e Cost or other basis",
                "Securities transactions",
            ],
            "amounts": ["proceeds", "basis", "gain", "loss"],
        },
        "1099-r": {
            "headers": [
                "Form 1099-R Distributions From Pensions, Annuities, Retirement",
                "1099-R Distributions From Pensions",
                "Form 1099-R",
                "Retirement Distributions",
            ],
            "fields": [
                "Payer's name",
                "Gross distribution",
                "Taxable amount",
                "Taxable amount not determined",
                "Total distribution",
                "Capital gain",
                "Federal income tax withheld",
                "Employee contributions",
                "Net unrealized appreciation",
                "Distribution code",
                "IRA/SEP/SIMPLE",
                "Box 1 Gross distribution",
                "Box 2a Taxable amount",
                "Box 4 Federal income tax withheld",
                "Box 7 Distribution code",
            ],
            "amounts": ["distribution", "pension", "annuity", "retirement"],
        },
        "1099-g": {
            "headers": [
                "Form 1099-G Certain Government Payments",
                "1099-G Government Payments",
                "Form 1099-G",
            ],
            "fields": [
                "Payer's name",
                "Unemployment compensation",
                "State or local income tax refunds",
                "Box 1 Unemployment compensation",
                "Box 2 State or local income tax refunds",
                "Taxable grants",
                "Agriculture payments",
                "Market gain",
                "Federal income tax withheld",
                "State income tax withheld",
            ],
            "amounts": ["unemployment", "refund", "grant", "payment"],
        },
        "1099-k": {
            "headers": [
                "Form 1099-K Payment Card and Third Party Network Transactions",
                "1099-K Payment Card Transactions",
                "Form 1099-K",
                "Third Party Network Transactions",
            ],
            "fields": [
                "Filer's name",
                "Payment settlement entity",
                "Payee's name",
                "Gross amount of payment card transactions",
                "Merchant card transactions",
                "Third party network transactions",
                "Card not present transactions",
                "Number of payment transactions",
                "Federal income tax withheld",
                "Box 1a Gross amount of payment card",
                "Box 1b Card not present transactions",
                "Box 2 Merchant category code",
                "Box 3 Number of payment transactions",
                "PSE's name and telephone number",
            ],
            "amounts": ["gross amount", "transactions", "payment", "merchant"],
        },
        "1099-sa": {
            "headers": [
                "Form 1099-SA Distributions From an HSA Archer MSA or Medicare Advantage MSA",
                "1099-SA HSA Distributions",
                "Form 1099-SA",
                "Distributions From an HSA",
            ],
            "fields": [
                "Trustee's name",
                "Distributions from HSA",
                "Gross distribution",
                "Earnings on excess contributions",
                "Distribution code",
                "FMV on date of death",
                "HSA",
                "Archer MSA",
                "Medicare Advantage MSA",
                "Box 1 Gross distribution",
                "Box 2 Earnings on excess contributions",
                "Box 3 Distribution code",
                "Health savings account",
            ],
            "amounts": ["distribution", "earnings", "HSA", "contribution"],
        },
        "1099-q": {
            "headers": [
                "Form 1099-Q Payments From Qualified Education Programs",
                "1099-Q Qualified Education Programs",
                "Form 1099-Q",
                "529 Plan Distribution",
            ],
            "fields": [
                "Payer's name",
                "Trustee's name",
                "Gross distribution",
                "Earnings",
                "Basis",
                "Trustee-to-trustee transfer",
                "Designated beneficiary",
                "Qualified tuition program",
                "Coverdell ESA",
                "Box 1 Gross distribution",
                "Box 2 Earnings",
                "Box 3 Basis",
                "529 plan",
                "Education savings account",
            ],
            "amounts": ["distribution", "earnings", "basis", "education"],
        },
        "1099-c": {
            "headers": [
                "Form 1099-C Cancellation of Debt",
                "1099-C Cancellation of Debt",
                "Form 1099-C",
                "Debt Cancellation",
            ],
            "fields": [
                "Creditor's name",
                "Creditor's federal identification number",
                "Amount of debt discharged",
                "Amount of debt canceled",
                "Date of identifiable event",
                "Interest if included in box 2",
                "Debt description",
                "Fair market value of property",
                "Box 1 Date of identifiable event",
                "Box 2 Amount of debt discharged",
                "Box 3 Interest if included",
                "Box 4 Debt description",
                "Debtor's identification number",
            ],
            "amounts": ["debt", "discharged", "canceled", "interest"],
        },
        "1099-s": {
            "headers": [
                "Form 1099-S Proceeds From Real Estate Transactions",
                "1099-S Real Estate Transactions",
                "Form 1099-S",
                "Real Estate Proceeds",
            ],
            "fields": [
                "Filer's name",
                "Transferor's name",
                "Transferor's identification number",
                "Date of closing",
                "Gross proceeds",
                "Address or legal description of property",
                "Address of property transferred",
                "Buyer's part of real estate tax",
                "Box 1 Date of closing",
                "Box 2 Gross proceeds",
                "Box 3 Address of property",
                "Real estate transaction",
                "Settlement statement",
            ],
            "amounts": ["proceeds", "gross", "real estate", "closing"],
        },
        "1099-oid": {
            "headers": [
                "Form 1099-OID Original Issue Discount",
                "1099-OID Original Issue Discount",
                "Form 1099-OID",
                "Original Issue Discount",
            ],
            "fields": [
                "Payer's name",
                "Original issue discount for period",
                "Other periodic interest",
                "Early withdrawal penalty",
                "Federal income tax withheld",
                "OID on U.S. Treasury obligations",
                "Investment expenses",
                "Bond premium",
                "Acquisition premium",
                "Box 1 Original issue discount",
                "Box 2 Other periodic interest",
                "Box 6 OID on US Treasury obligations",
                "Box 10 Bond premium",
                "Box 11 Acquisition premium",
            ],
            "amounts": ["discount", "OID", "interest", "premium"],
        },
        "1099-ltc": {
            "headers": [
                "Form 1099-LTC Long-Term Care and Accelerated Death Benefits",
                "1099-LTC Long-Term Care Benefits",
                "Form 1099-LTC",
                "Long-Term Care Benefits",
            ],
            "fields": [
                "Payer's name",
                "Policyholder's name",
                "Insured's name",
                "Gross long-term care benefits paid",
                "Accelerated death benefits paid",
                "Per diem or reimbursement",
                "Qualified contract",
                "Chronically ill",
                "Terminally ill",
                "Box 1 Gross LTC benefits paid",
                "Box 2 Accelerated death benefits paid",
                "Box 3 Per diem or reimbursement",
                "LTC insurance",
            ],
            "amounts": ["benefits", "LTC", "long-term care", "death benefits"],
        },
        "1099-patr": {
            "headers": [
                "Form 1099-PATR Taxable Distributions Received From Cooperatives",
                "1099-PATR Cooperative Distributions",
                "Form 1099-PATR",
                "Patronage Dividends",
            ],
            "fields": [
                "Payer's name",
                "Cooperative's name",
                "Patronage dividends",
                "Nonpatronage distributions",
                "Per-unit retain allocations",
                "Federal income tax withheld",
                "Redemption of nonqualified notices",
                "Section 199A(g) deduction",
                "Qualified payments",
                "Box 1 Patronage dividends",
                "Box 2 Nonpatronage distributions",
                "Box 3 Per-unit retain allocations",
                "Box 5 Redemption of nonqualified notices",
                "Cooperative distribution",
            ],
            "amounts": ["patronage", "dividends", "distributions", "cooperative"],
        },
        "1098": {
            "headers": [
                "Form 1098 Mortgage Interest Statement",
                "1098 Mortgage Interest Statement",
                "Form 1098",
            ],
            "fields": [
                "Recipient's name",
                "Mortgage interest received",
                "Outstanding mortgage principal",
                "Mortgage origination date",
                "Refund of overpaid interest",
                "Mortgage insurance premiums",
                "Points paid on purchase",
                "Address of property",
                "Number of properties",
                "Box 1 Mortgage interest received",
                "Box 2 Outstanding mortgage principal",
                "Box 5 Mortgage insurance premiums",
            ],
            "amounts": ["mortgage", "interest", "principal", "premium"],
        },
        "1098-e": {
            "headers": [
                "Form 1098-E Student Loan Interest Statement",
                "1098-E Student Loan Interest Statement",
                "Form 1098-E",
            ],
            "fields": [
                "Lender's name",
                "Student loan interest received",
                "Box 1 Student loan interest received",
                "Recipient's information",
                "Account number",
            ],
            "amounts": ["student loan", "interest", "education"],
        },
        "1098-t": {
            "headers": [
                "Form 1098-T Tuition Statement",
                "1098-T Tuition Statement",
                "Form 1098-T",
            ],
            "fields": [
                "Filer's name",
                "Student's name",
                "Payments received for qualified tuition",
                "Amounts billed for qualified tuition",
                "Adjustments made for a prior year",
                "Scholarships or grants",
                "Adjustments to scholarships",
                "Half-time student",
                "Graduate student",
                "Box 1 Payments received",
                "Box 5 Scholarships or grants",
                "Academic period",
            ],
            "amounts": ["tuition", "scholarship", "education", "qualified"],
        },
        "k1": {
            "headers": [
                "Schedule K-1 Partner's Share of Income",
                "Schedule K-1 Shareholder's Share",
                "Schedule K-1 Beneficiary's Share",
                "Schedule K-1 (Form 1065)",
                "Schedule K-1 (Form 1120-S)",
                "Schedule K-1 (Form 1041)",
            ],
            "fields": [
                "Partner's share of income",
                "Shareholder's share of income",
                "Beneficiary's share of income",
                "Ordinary business income",
                "Net rental real estate income",
                "Other net rental income",
                "Guaranteed payments",
                "Interest income",
                "Ordinary dividends",
                "Royalties",
                "Net short-term capital gain",
                "Net long-term capital gain",
                "Section 179 deduction",
                "Partner's capital account",
                "Part III Partner's Share",
                "Box 1 Ordinary business income",
            ],
            "amounts": ["share", "income", "gain", "partnership"],
        },
        "1095-a": {
            "headers": [
                "Form 1095-A Health Insurance Marketplace Statement",
                "1095-A Health Insurance Marketplace Statement",
                "Form 1095-A",
            ],
            "fields": [
                "Marketplace identifier",
                "Policy number",
                "Policy issuer name",
                "Recipient's name",
                "Coverage start date",
                "Monthly enrollment premium",
                "Monthly SLCSP premium",
                "Monthly advance payment of PTC",
                "Premium Tax Credit",
                "Box 21-32 Monthly amounts",
                "Annual totals",
            ],
            "amounts": ["premium", "credit", "marketplace", "coverage"],
        },
        "1095-b": {
            "headers": [
                "Form 1095-B Health Coverage",
                "1095-B Health Coverage",
                "Form 1095-B",
            ],
            "fields": [
                "Issuer name",
                "Employer name",
                "Origin of policy",
                "Covered individuals",
                "Months of coverage",
                "Minimum essential coverage",
                "Part III Covered Individuals",
                "SSN of covered individual",
                "Date of birth",
            ],
            "amounts": ["coverage", "health", "insurance"],
        },
        "1095-c": {
            "headers": [
                "Form 1095-C Employer-Provided Health Insurance Offer and Coverage",
                "1095-C Employer-Provided Health Insurance",
                "Form 1095-C",
            ],
            "fields": [
                "Employer's name",
                "Employee's name",
                "Offer of coverage",
                "Employee share of lowest cost",
                "Safe harbor code",
                "Line 14 Offer of coverage",
                "Line 15 Employee required contribution",
                "Line 16 Section 4980H Safe Harbor",
                "Part III Covered Individuals",
                "Months covered",
            ],
            "amounts": ["coverage", "contribution", "employer", "insurance"],
        },
        "ssa-1099": {
            "headers": [
                "SSA-1099 Social Security Benefit Statement",
                "Form SSA-1099",
                "Social Security Benefit Statement",
                "Social Security Administration",
            ],
            "fields": [
                "Beneficiary's name",
                "Beneficiary's social security number",
                "Benefits paid",
                "Benefits repaid to SSA",
                "Net benefits",
                "Federal income tax withheld",
                "Medicare premium deducted",
                "Description of amount in Box 3",
                "Box 3 Benefits paid",
                "Box 4 Benefits repaid to SSA",
                "Box 5 Net benefits",
                "Box 6 Voluntary federal income tax withheld",
                "Claim number",
            ],
            "amounts": ["benefits", "social security", "withheld", "Medicare premium"],
        },
        "rrb-1099": {
            "headers": [
                "RRB-1099 Payments by the Railroad Retirement Board",
                "Form RRB-1099",
                "Railroad Retirement Benefits",
                "Railroad Retirement Board",
            ],
            "fields": [
                "Recipient's name",
                "Claim number",
                "Social security equivalent benefit",
                "Tier 1 benefits",
                "Tier 2 benefits",
                "Vested dual benefit",
                "Supplemental annuity",
                "Total gross paid",
                "Repayments",
                "Federal income tax withheld",
                "Medicare premium",
                "Box 3 Social security equivalent benefit",
                "Box 4 Tier 1 tax",
                "Box 5 Net social security equivalent benefit",
            ],
            "amounts": ["benefits", "railroad retirement", "tier", "annuity"],
        },
        "5498": {
            "headers": [
                "Form 5498 IRA Contribution Information",
                "5498 IRA Contribution Information",
                "Form 5498",
                "IRA Contribution Information",
            ],
            "fields": [
                "Trustee's name",
                "Participant's name",
                "IRA contributions",
                "Rollover contributions",
                "Roth IRA conversion amount",
                "Recharacterized contributions",
                "Fair market value of account",
                "Required minimum distribution",
                "SEP contributions",
                "SIMPLE contributions",
                "Roth IRA contributions",
                "Box 1 IRA contributions",
                "Box 2 Rollover contributions",
                "Box 3 Roth IRA conversion amount",
                "Box 5 Fair market value of account",
                "Box 10 Roth IRA contributions",
                "RMD date",
            ],
            "amounts": ["contribution", "IRA", "rollover", "fair market value"],
        },
        "5498-sa": {
            "headers": [
                "Form 5498-SA HSA Archer MSA or Medicare Advantage MSA Information",
                "5498-SA HSA Information",
                "Form 5498-SA",
                "HSA Contribution Information",
            ],
            "fields": [
                "Trustee's name",
                "Participant's name",
                "HSA contributions",
                "Total contributions",
                "Total HSA contributions",
                "Archer MSA contributions",
                "Medicare Advantage MSA contributions",
                "Rollover contributions",
                "Fair market value of HSA",
                "Fair market value of MSA",
                "Box 1 Employee or self-employed contributions",
                "Box 2 Total contributions",
                "Box 3 Total HSA contributions",
                "Box 4 Rollover contributions",
                "Box 5 Fair market value of HSA",
                "Health savings account",
            ],
            "amounts": ["contribution", "HSA", "fair market value", "rollover"],
        },
    }

    def __init__(self, seed: int = 42):
        """
        Initialize the generator.

        Args:
            seed: Random seed for reproducibility.
        """
        self.random = random.Random(seed)

    def _generate_amount(self) -> str:
        """Generate a random dollar amount."""
        amount = self.random.uniform(100, 150000)
        return f"${amount:,.2f}"

    def _generate_ein(self) -> str:
        """Generate a random EIN."""
        return f"{self.random.randint(10, 99)}-{self.random.randint(1000000, 9999999)}"

    def _generate_ssn_masked(self) -> str:
        """Generate a masked SSN."""
        return f"XXX-XX-{self.random.randint(1000, 9999)}"

    def _generate_name(self) -> str:
        """Generate a random name."""
        first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Davis", "Miller", "Wilson"]
        return f"{self.random.choice(first_names)} {self.random.choice(last_names)}"

    def _generate_company(self) -> str:
        """Generate a random company name."""
        prefixes = ["Acme", "Global", "United", "First", "National", "American", "Pacific", "Atlantic"]
        suffixes = ["Corp", "Inc", "LLC", "Holdings", "Industries", "Group", "Services", "Financial"]
        return f"{self.random.choice(prefixes)} {self.random.choice(suffixes)}"

    def generate_document(self, document_type: str, num_variations: int = 1) -> SyntheticDocument:
        """
        Generate a synthetic document of the specified type.

        Args:
            document_type: Type of document to generate.
            num_variations: Number of text variations to generate.

        Returns:
            SyntheticDocument with text and variations.
        """
        if document_type not in self.TEMPLATES:
            raise ValueError(f"Unknown document type: {document_type}")

        template = self.TEMPLATES[document_type]

        # Generate main text
        main_text = self._generate_text(template)

        # Generate variations
        variations = []
        for _ in range(num_variations - 1):
            variations.append(self._generate_text(template))

        return SyntheticDocument(
            text=main_text,
            document_type=document_type,
            variations=variations,
        )

    def _generate_text(self, template: Dict) -> str:
        """Generate text from a template."""
        parts = []

        # Add headers
        num_headers = self.random.randint(1, min(3, len(template["headers"])))
        headers = self.random.sample(template["headers"], num_headers)
        parts.extend(headers)

        # Add tax year
        year = self.random.choice([2024, 2025])
        parts.append(f"Tax Year {year}")

        # Add some field labels with values
        num_fields = self.random.randint(5, min(12, len(template["fields"])))
        fields = self.random.sample(template["fields"], num_fields)

        for field_label in fields:
            if "name" in field_label.lower():
                if "employer" in field_label.lower() or "payer" in field_label.lower():
                    parts.append(f"{field_label}: {self._generate_company()}")
                else:
                    parts.append(f"{field_label}: {self._generate_name()}")
            elif "ein" in field_label.lower() or "tin" in field_label.lower():
                parts.append(f"{field_label}: {self._generate_ein()}")
            elif "social security" in field_label.lower() and "number" in field_label.lower():
                parts.append(f"{field_label}: {self._generate_ssn_masked()}")
            elif any(amt in field_label.lower() for amt in ["wage", "income", "tax", "amount", "interest", "dividend", "payment", "distribution", "premium", "compensation", "proceeds", "basis", "rents", "royalties"]):
                parts.append(f"{field_label}: {self._generate_amount()}")
            else:
                parts.append(field_label)

        # Shuffle to create more variation
        self.random.shuffle(parts)

        return "\n".join(parts)

    def generate_dataset(
        self,
        samples_per_type: int = 100,
        document_types: List[str] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Generate a complete training dataset.

        Args:
            samples_per_type: Number of samples to generate per document type.
            document_types: List of document types to include. If None, includes all.

        Returns:
            Tuple of (texts, labels) lists.
        """
        if document_types is None:
            document_types = list(self.TEMPLATES.keys())

        texts = []
        labels = []

        for doc_type in document_types:
            for _ in range(samples_per_type):
                doc = self.generate_document(doc_type)
                texts.append(doc.text)
                labels.append(doc.document_type)

                # Also add variations
                for var_text in doc.variations:
                    texts.append(var_text)
                    labels.append(doc.document_type)

        return texts, labels
